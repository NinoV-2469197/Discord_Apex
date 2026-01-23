import discord
from discord.ext import tasks
import aiohttp
import asyncio
import logging
import os
import sys
import io
import time
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageEnhance

# ================= CONFIGURATION =================
BRIGHTNESS_FACTOR = 2.5

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

if not DISCORD_BOT_TOKEN or not APEX_API_KEY:
    logging.fatal("Missing keys! Check your .env file.")
    raise ValueError("Missing keys")

URL = f"https://api.mozambiquehe.re/maprotation?auth={APEX_API_KEY}&version=2"

class ApexMapBot(discord.Client):
    def __init__(self):
        # We need 'guilds' intent to change nicknames
        intents = discord.Intents.default()
        intents.guilds = True 
        super().__init__(intents=intents)
        
        # Internal Memory
        self.last_map = None
        self.rotation_end_time = 0 
        self.next_map_name = "Unknown"
        self.current_map_name = "Unknown"
        self.last_status_message = None

    async def setup_hook(self):
        self.update_presence_task.start()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info(f'Connected to {len(self.guilds)} servers.')

    def get_time_remaining(self, reference_time: int = None):
        """Calculates minutes remaining."""
        if reference_time is None:
            reference_time = int(time.time())
        remaining_seconds = self.rotation_end_time - reference_time
        if remaining_seconds < 0:
            return 0
        return remaining_seconds // 60

    @tasks.loop(seconds=60)
    async def update_presence_task(self):
        try:
            now = int(time.time())
            
            # Fetch API if we have no data OR map has expired
            should_fetch = (self.rotation_end_time == 0) or (now >= self.rotation_end_time - 60)

            if should_fetch:
                await self.fetch_and_update_api()

            # === 1. UPDATE STATUS (Bottom Line) ===
            minutes_left = self.get_time_remaining(reference_time=now)
            
            # Status: "Ends in 1h 15m » Next: Storm Point"
            hours, minutes = divmod(minutes_left, 60)
            if hours > 0:
                status_message = f"Ends in {hours}h {minutes}m » Next: {self.next_map_name}"
            else:
                status_message = f"Ends in {minutes}m » Next: {self.next_map_name}"

            if status_message != self.last_status_message:
                await self.change_presence(activity=discord.Game(name=status_message))
                logging.info(f"Status Updated: {status_message}")
                self.last_status_message = status_message

        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)

    async def fetch_and_update_api(self):
        """Fetches data, updates Avatar and Nicknames."""
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    ranked = data.get('ranked', {})
                    current_data = ranked.get('current', {})
                    next_data = ranked.get('next', {})

                    self.current_map_name = current_data.get('map', 'Unknown')
                    self.rotation_end_time = current_data.get('end', 0)
                    self.next_map_name = next_data.get('map', 'Unknown')
                    
                    # === CHECK FOR ROTATION ===
                    if self.current_map_name != self.last_map:
                        logging.info(f"ROTATION: {self.last_map} -> {self.current_map_name}")
                        
                        # 1. Update Avatar
                        map_image_url = current_data.get('asset', None)
                        if map_image_url:
                            await self.update_avatar(session, map_image_url)
                        
                        # 2. Update Nicknames (Top Line)
                        # Nickname: "Ranked: Olympus"
                        new_nickname = f"Ranked: {self.current_map_name}"
                        await self.update_all_nicknames(new_nickname)

                        self.last_map = self.current_map_name
                else:
                    logging.error(f"API Failed: {response.status}")

    async def update_all_nicknames(self, new_nick):
        """Loops through all servers and updates the bot's nickname."""
        logging.info(f"Updating nickname to '{new_nick}' in all servers...")
        for guild in self.guilds:
            try:
                # 'me' refers to the bot member in that guild
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
                    image = Image.open(io.BytesIO(raw_data))
                    enhancer = ImageEnhance.Brightness(image)
                    bright_image = enhancer.enhance(BRIGHTNESS_FACTOR)

                    # Crop
                    width, height = bright_image.size
                    new_edge = min(width, height)
                    left = (width - new_edge)/2
                    top = (height - new_edge)/2
                    right = (width + new_edge)/2
                    bottom = (height + new_edge)/2
                    cropped_image = bright_image.crop((left, top, right, bottom))

                    output_buffer = io.BytesIO()
                    cropped_image.save(output_buffer, format='PNG')
                    
                    await self.user.edit(avatar=output_buffer.getvalue())
                    logging.info("Avatar updated.")
        except Exception as e:
            logging.error(f"Failed to update avatar: {e}")

    @update_presence_task.before_loop
    async def before_update_presence_task(self):
        await self.wait_until_ready()

if __name__ == '__main__':
    bot = ApexMapBot()
    bot.run(DISCORD_BOT_TOKEN)