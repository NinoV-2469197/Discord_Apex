import discord
from discord.ext import tasks
import aiohttp
import logging
import os
import sys
import io
import time
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image

# ================= CONFIGURATION =================
# How often to check stats (in seconds)
STATS_CHECK_INTERVAL = 3600  # 1 hour

# How often to update the Avatar (in seconds)
# Discord has strict rate limits on profile pic changes. 
# 86400 seconds = 24 Hours.
AVATAR_UPDATE_INTERVAL = 86400 

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Load Keys
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
APEX_API_KEY = os.getenv('APEX_API_KEY')
PLAYER_UID = os.getenv('PLAYER_UID')

if not DISCORD_BOT_TOKEN or not APEX_API_KEY or not PLAYER_UID:
    logging.fatal("Missing keys! Ensure DISCORD_BOT_TOKEN, APEX_API_KEY, and PLAYER_UID are in .env")
    raise ValueError("Missing keys")

# URL based on the Interface provided (The 'bridge' endpoint returns the global/realtime/legends structure)
URL = f"https://api.mozambiquehe.re/bridge?auth={APEX_API_KEY}&player={PLAYER_UID}&platform=PC"

class ApexPlayerBot(discord.Client):
    def __init__(self):
        # We need 'guilds' intent to change nicknames
        intents = discord.Intents.default()
        intents.guilds = True 
        super().__init__(intents=intents)
        
        # Internal Memory
        self.last_avatar_update = 0
        self.last_known_name = None
        self.last_known_score = None

    async def setup_hook(self):
        self.update_stats_task.start()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info(f'Tracking UID: {PLAYER_UID}')

    @tasks.loop(seconds=STATS_CHECK_INTERVAL)
    async def update_stats_task(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL) as response:
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
                        if status_text != self.last_known_score:
                            await self.change_presence(activity=discord.Game(name=status_text))
                            logging.info(f"Status Updated: {status_text}")
                            self.last_known_score = status_text

                        # === 3. UPDATE NICKNAME (Bot Name) ===
                        # Only update if name is different
                        if player_name != self.last_known_name:
                            await self.update_all_nicknames(player_name)
                            self.last_known_name = player_name

                        # === 4. UPDATE AVATAR (Rank Badge) ===
                        # Checked every loop, but only executed if AVATAR_UPDATE_INTERVAL passed
                        now = time.time()
                        if rank_img_url and (now - self.last_avatar_update > AVATAR_UPDATE_INTERVAL):
                            logging.info("Daily Avatar Update Triggered...")
                            await self.update_avatar(session, rank_img_url)
                            self.last_avatar_update = now

                    elif response.status == 429:
                        logging.warning("Rate Limit Hit (429). Waiting...")
                    else:
                        logging.error(f"API Failed: {response.status} - {await response.text()}")

        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)

    async def update_all_nicknames(self, new_nick):
        """Loops through all servers and updates the bot's nickname."""
        logging.info(f"Updating nickname to '{new_nick}'...")
        for guild in self.guilds:
            try:
                # 'me' refers to the bot member in that guild
                if guild.me.nick != new_nick:
                    await guild.me.edit(nick=new_nick)
            except discord.Forbidden:
                logging.warning(f"Missing permissions to change nickname in guild: {guild.name}")
            except Exception as e:
                logging.error(f"Failed to change nickname in {guild.name}: {e}")

    async def update_avatar(self, session, url):
        try:
            async with session.get(url) as resp:
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
                    logging.info("Profile Image updated to Ranked Badge.")
                else:
                    logging.error(f"Failed to download image: {resp.status}")
        except Exception as e:
            logging.error(f"Failed to update avatar: {e}")

    @update_stats_task.before_loop
    async def before_update_stats_task(self):
        await self.wait_until_ready()

if __name__ == '__main__':
    bot = ApexPlayerBot()
    bot.run(DISCORD_BOT_TOKEN)