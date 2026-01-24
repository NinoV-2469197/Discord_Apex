import discord
from discord.ext import tasks
import aiohttp
import asyncio
import logging
import os
import sys
import io
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image

# ================= CONFIGURATION =================
# How often to check stats (in seconds)
STATS_CHECK_INTERVAL = 3600  # 1 hour (good balance between freshness and API rate limits)

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Load Keys
load_dotenv()
APEX_API_KEY = os.getenv('APEX_API_KEY')

if not APEX_API_KEY:
    logging.fatal("Missing APEX_API_KEY in .env")
    raise ValueError("Missing APEX_API_KEY")

@dataclass
class PlayerConfig:
    """Configuration for a single player bot."""
    name: str
    discord_token: str
    player_uid: str
    startup_delay: int = 0

class ApexPlayerBot(discord.Client):
    def __init__(self, config: PlayerConfig, shared_session: aiohttp.ClientSession):
        # We need 'guilds' intent to change nicknames
        intents = discord.Intents.default()
        intents.guilds = True 
        super().__init__(intents=intents)
        
        self.config = config
        self.shared_session = shared_session
        self.api_url = f"https://api.mozambiquehe.re/bridge?auth={APEX_API_KEY}&player={config.player_uid}&platform=PC"
        
        # Internal Memory
        self.last_known_name = None
        self.last_known_score = None

    async def setup_hook(self):
        self.update_stats_task.start()

    async def on_ready(self):
        logging.info(f'[{self.config.name}] Logged in as {self.user} (ID: {self.user.id})')
        logging.info(f'[{self.config.name}] Tracking UID: {self.config.player_uid}')

    @tasks.loop(seconds=STATS_CHECK_INTERVAL)
    async def update_stats_task(self):
        try:
            async with self.shared_session.get(self.api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # === 1. PARSE DATA ===
                    # Based on interface: global -> name / rank -> rankScore / rankImg
                    global_info = data.get('global', {})
                    rank_info = global_info.get('rank', {})
                    
                    player_name = global_info.get('name', 'Unknown')
                    rank_score = rank_info.get('rankScore', 0)
                    rank_name = rank_info.get('rankName', 'Rookie')
                    rank_div = rank_info.get('rankDiv', 0)
                    rank_img_url = rank_info.get('rankImg', None)

                    # === 2. UPDATE STATUS (Description) ===
                    # Description: "Master 1 - 15000 RP"
                    status_text = f"{rank_name} {rank_div} - {rank_score:,} RP"
                    
                    # Only update if score changed to avoid spamming Discord API
                    score_changed = status_text != self.last_known_score
                    if score_changed:
                        await self.change_presence(activity=discord.Game(name=status_text))
                        logging.info(f"[{self.config.name}] Status Updated: {status_text}")
                        self.last_known_score = status_text

                    # === 3. UPDATE NICKNAME (Bot Name) ===
                    # Only update if name is different
                    if player_name != self.last_known_name:
                        await self.update_all_nicknames(player_name)
                        self.last_known_name = player_name

                    # === 4. UPDATE AVATAR (Rank Badge) ===
                    # Update avatar when the score changes so rank badge stays in sync
                    if rank_img_url and score_changed:
                        logging.info(f"[{self.config.name}] Score changed; updating avatar to current rank badge...")
                        await self.update_avatar(rank_img_url)

                elif response.status == 429:
                    logging.warning(f"[{self.config.name}] Rate Limit Hit (429). Waiting...")
                else:
                    error_text = await response.text()
                    logging.error(f"[{self.config.name}] API Failed: {response.status} - {error_text}")

        except Exception as e:
            logging.error(f"[{self.config.name}] Error in main loop: {e}", exc_info=True)

    async def update_all_nicknames(self, new_nick):
        """Loops through all servers and updates the bot's nickname."""
        logging.info(f"[{self.config.name}] Updating nickname to '{new_nick}'...")
        for guild in self.guilds:
            try:
                # 'me' refers to the bot member in that guild
                if guild.me.nick != new_nick:
                    await guild.me.edit(nick=new_nick)
            except discord.Forbidden:
                logging.warning(f"[{self.config.name}] Missing permissions to change nickname in guild: {guild.name}")
            except Exception as e:
                logging.error(f"[{self.config.name}] Failed to change nickname in {guild.name}: {e}")

    async def update_avatar(self, url):
        try:
            async with self.shared_session.get(url) as resp:
                if resp.status == 200:
                    raw_data = await resp.read()
                    
                    # Pillow Processing
                    # We convert to PNG and resize if necessary, but we avoid cropping
                    # because Rank Badges have irregular shapes.
                    image = Image.open(io.BytesIO(raw_data))
                    
                    # Convert to RGBA to preserve transparency
                    if image.mode != 'RGBA':
                        image = image.convert('RGBA')

                    output_buffer = io.BytesIO()
                    image.save(output_buffer, format='PNG')
                    
                    await self.user.edit(avatar=output_buffer.getvalue())
                    logging.info(f"[{self.config.name}] Profile Image updated to Ranked Badge.")
                else:
                    logging.error(f"[{self.config.name}] Failed to download image: {resp.status}")
        except Exception as e:
            logging.error(f"[{self.config.name}] Failed to update avatar: {e}")

    @update_stats_task.before_loop
    async def before_update_stats_task(self):
        await self.wait_until_ready()
        # Add startup delay to stagger API calls and avoid rate limits
        if self.config.startup_delay > 0:
            logging.info(f"[{self.config.name}] Waiting {self.config.startup_delay} seconds before first API call to avoid rate limits...")
            await asyncio.sleep(self.config.startup_delay)

def parse_player_configs() -> list[PlayerConfig]:
    """Parse all player configurations from environment variables."""
    configs = []
    
    # Look for all DISCORD_BOT_TOKEN_* and PLAYER_UID_* pairs
    env_vars = dict(os.environ)
    
    # Find all player tokens
    player_tokens = {k: v for k, v in env_vars.items() if k.startswith('DISCORD_BOT_TOKEN_') and k != 'DISCORD_BOT_TOKEN_MAP'}
    
    for token_key, token_value in player_tokens.items():
        # Extract player name from token key (e.g., DISCORD_BOT_TOKEN_DAAN -> DAAN)
        player_name = token_key.replace('DISCORD_BOT_TOKEN_', '').upper()
        
        # Find corresponding UID
        uid_key = f'PLAYER_UID_{player_name}'
        player_uid = env_vars.get(uid_key)
        
        if not player_uid:
            logging.warning(f"Missing {uid_key} for player {player_name}, skipping...")
            continue
        
        # Get startup delay (optional, defaults to 0)
        delay_key = f'STARTUP_DELAY_{player_name}'
        startup_delay = int(env_vars.get(delay_key, '0'))
        
        configs.append(PlayerConfig(
            name=player_name,
            discord_token=token_value,
            player_uid=player_uid,
            startup_delay=startup_delay
        ))
        logging.info(f"Loaded config for player: {player_name} (UID: {player_uid}, delay: {startup_delay}s)")
    
    if not configs:
        logging.fatal("No player configurations found! Ensure DISCORD_BOT_TOKEN_* and PLAYER_UID_* are set in .env")
        raise ValueError("No player configurations found")
    
    return configs

async def run_bot(config: PlayerConfig, shared_session: aiohttp.ClientSession):
    """Run a single bot instance."""
    bot = ApexPlayerBot(config, shared_session)
    try:
        await bot.start(config.discord_token)
    except Exception as e:
        logging.error(f"[{config.name}] Bot crashed: {e}", exc_info=True)
    finally:
        await bot.close()

async def main():
    """Main entry point - runs all player bots concurrently."""
    # Parse all player configurations
    player_configs = parse_player_configs()
    
    # Create shared HTTP session for better connection pooling
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=30)
    shared_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    
    try:
        # Run all bots concurrently
        tasks = [run_bot(config, shared_session) for config in player_configs]
        await asyncio.gather(*tasks)
    finally:
        await shared_session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)