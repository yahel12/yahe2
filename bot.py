import logging
import logging.config
from datetime import date, datetime
from typing import Union, Optional, AsyncGenerator

from pyrogram import Client, __version__, types
from pyrogram.raw.all import layer
from pymongo.errors import OperationFailure

from database.ia_filterdb import Media, Media2, choose_mediaDB, db as clientDB
from database.users_chats_db import db
from info import SESSION, API_ID, API_HASH, BOT_TOKEN, LOG_STR, LOG_CHANNEL, PORT, SECONDDB_URI, DATABASE_URI
from utils import temp
from plugins import web_server
from sample_info import tempDict
from Script import script

import pytz
from aiohttp import web

class Bot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=10,
        )
        self.setup_logging()  # Initialize logging configuration

    def setup_logging(self):
        """Setup logging configuration."""
        logging.config.fileConfig('logging.conf')  # Load logging configuration from file
        logging.getLogger().setLevel(logging.INFO)  # Set global logging level to INFO
        logging.getLogger("pyrogram").setLevel(logging.ERROR)  # Set logging level for pyrogram library to ERROR
        logging.getLogger("imdbpy").setLevel(logging.ERROR)  # Set logging level for imdbpy library to ERROR

    async def db_stats(self):
        """Fetch database statistics asynchronously."""
        try:
            stats = await clientDB.command('dbStats')
            return stats
        except OperationFailure as e:
            logging.error(f"Error fetching dbStats: {e}")
            return None

    async def start(self):
        """Start the bot asynchronously."""
        await self.setup_bot_context()  # Setup bot context including banned users/chats

        # Fetch dbStats for the primary DB
        stats = await self.db_stats()
        if not stats:
            logging.error("Failed to get dbStats from primary DB.")
            return
        
        # Calculate the free db space from bytes to MB
        free_db_size = round(512 - ((stats['dataSize'] / (1024 * 1024)) + (stats['indexSize'] / (1024 * 1024))), 2)
        logging.info(f"Primary DB free space: {free_db_size} MB")
        
        # Choose the right DB by checking the free space
        if SECONDDB_URI and free_db_size < 100:  # If the primary DB has less than 100MB left, use the second DB.
            tempDict["indexDB"] = SECONDDB_URI
            logging.info(f"Using Secondary DB due to low space in Primary DB ({free_db_size} MB left).")
        elif SECONDDB_URI is None:
            logging.error("Missing second DB URI! Add SECONDDB_URI now! Exiting...")
            exit()
        else:
            tempDict["indexDB"] = DATABASE_URI
            logging.info(f"Using Primary DB with sufficient space ({free_db_size} MB left).")

        await choose_mediaDB()  # Choose media database based on tempDict configuration

        await self.send_startup_message()  # Send startup message to log channel

        await self.setup_web_server()  # Setup and start the web server

    async def setup_bot_context(self):
        """Setup bot context including banned users and chats."""
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        await super().start()  # Start the bot's main client
        await Media.ensure_indexes()  # Ensure indexes are created for Media database
        await Media2.ensure_indexes()  # Ensure indexes are created for Media2 database

        me = await self.get_me()  # Get bot's own information
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username  # Set bot's username
        
        logging.info(f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")  # Log bot start information
        logging.info(LOG_STR)  # Log additional configuration or status information
        logging.info(script.LOGO)  # Log script logo or additional startup information

    async def send_startup_message(self):
        """Send startup message to a designated log channel."""
        tz = pytz.timezone('Asia/Kolkata')  # Set timezone for timestamp
        today = date.today()  # Get current date
        now = datetime.now(tz)  # Get current time with timezone
        time = now.strftime("%H:%M:%S %p")  # Format time as HH:MM:SS AM/PM
        
        await self.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time))  # Send formatted startup message

    async def setup_web_server(self):
        """Setup and start the web server for handling HTTP requests."""
        app = web.AppRunner(await web_server())  # Create an app runner instance with web server configuration
        await app.setup()  # Setup the app runner
        bind_address = "0.0.0.0"  # Bind web server to all available network interfaces
        await web.TCPSite(app, bind_address, PORT).start()  # Start TCP web server on specified port

    async def stop(self, *args):
        """Stop the bot and perform cleanup tasks."""
        await super().stop()  # Stop the bot's main client
        logging.info("Bot stopped. Bye.")  # Log bot stop message

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through messages in a chat."""
        current = offset
        while True:
            new_diff = min(200, limit - current)  # Calculate message batch size
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))  # Fetch messages in batch
            for message in messages:
                yield message  # Yield each message in the batch
                current += 1  # Increment message counter

# Entry point of the script
if __name__ == "__main__":
    app = Bot()
    app.run()  # Run the bot
