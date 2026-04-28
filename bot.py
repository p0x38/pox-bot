import datetime
import os
import random
import re
import subprocess
from time import time
from typing import Optional
import uuid
import aiomysql
import discord
from discord.ext import commands
from gtts.lang import tts_langs
import psutil
from src.utils.cache import Cache
from classes import EmoticonGenerator, MyTranslator
from src.database import EconomyDatabase, GuildSettingsDatabase, SettingsDatabase, StatsDatabase
import stuff
import data
import aiosqlite
import profanityfilter
import roblox
from logger import logger
from discord import Color, Embed, Forbidden, HTTPException, MissingApplicationID, app_commands
import aiofiles
import json
from src.translator import discord_translator

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': stuff.get_mysql_credentials()[0],
    'password': stuff.get_mysql_credentials()[1],
    'db': 'discord-bot',
    'autocommit': True
}

class PoxBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args,**kwargs)
        self.launch_time = datetime.datetime.now(datetime.UTC)
        self.launch_time2 = time()
        self.handled_messages = 0
        self.db_connection = None
        self.settings_db: Optional[SettingsDatabase] = None
        self.stats_db: Optional[StatsDatabase] = None
        self.economy_db: Optional[EconomyDatabase] = None
        self.guild_db: Optional[GuildSettingsDatabase] = None
        self.mysql = None
        self.commit_hash = ""
        self.session_uuid = uuid.uuid4()
        self.name_signature = stuff.generate_namesignature()
        self.last_commit = stuff.get_latest_commit_message()
        self.processed_interactions = 0
        self.failed_interactions = 0
        self.gtts_cache_langs = tts_langs()
        self.received_chunks = 0
        self.already_said = False
        self.swears_in_row = 0
        self.active_games = {}
        self.activity_messages = []
        self.invites = []
        self.cache = Cache(60*60*24)
        self.roblox_client = roblox.Client()
        self.profanity_filter = profanityfilter.ProfanityFilter()
        self.blacklisted_words = {}
        self.servers_data = {}
        self.root_path = os.path.dirname(os.path.abspath(__file__))
        self.available_togglers = [
            "delete_message_with_swears",
            "enable_level_notify",
            "anti_spam_message",
            "enable_bot_predefined_autoreply"
        ]
        self.spam_time_window = 5
        self.max_messages_per_window = 5
        self.user_message_timestamps = {}
        self.emoticon_generator = EmoticonGenerator()
        self.custom_activity = os.path.join(self.root_path, "resources/what_2.txt")
        self.server_data2 = {}
        self.server_data2_loaded = False
        self.auth_code = str(random.randint(10000000,99999999))
        self.EXCLUDE_EXTENSIONS = [
            "chat", "chatbot",
            "log",
            "others", "websockets"
        ]
        self.bot_servers_limit = 90
        self.pid = stuff.get_pid()
        self.proc = psutil.Process(self.pid)
    
    def _(self, s): return s
    
    async def setup_hook(self):
        stuff.setup_database("./leaderboard.db")
        
        dsn = stuff.get_postgresql_dsn()
        
        if not dsn:
            raise Exception("No DSN specified.")
        
        self.settings_db = SettingsDatabase(dsn)
        self.stats_db = StatsDatabase(dsn)
        self.economy_db = EconomyDatabase(dsn)
        self.guild_db = GuildSettingsDatabase(dsn)
        
        await self.settings_db.connect()
        
        self.stats_db.pool = self.settings_db.pool
        self.economy_db.pool = self.settings_db.pool
        self.guild_db.pool = self.settings_db.pool
        
        await self.settings_db.setup()
        await self.stats_db.setup()
        await self.economy_db.setup()
        await self.guild_db.setup()
        
        try:
            await self.tree.set_translator(discord_translator)
        except Exception:
            logger.exception("Failed to set command translator")
        
        self.db_connection = await aiosqlite.connect("./leaderboard.db")

        self.mysql = await aiomysql.create_pool(**DB_CONFIG)
        logger.debug("Database initialized")

        async with self.mysql.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS reaction_roles (
                        message_id BIGINT, emoji VARCHAR(255), role_id BIGINT, PRIMARY KEY (message_id, emoji)
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS globalchannels (
                        channel BIGINT PRIMARY KEY,
                        guild BIGINT
                    )
                """)

        try:
            async with aiofiles.open('data/blacklisted_words.json', 'r+') as f:
                content = await f.read()
                self.blacklisted_words = json.loads(content)
                logger.debug(self.blacklisted_words)
        except FileNotFoundError:
            self.blacklisted_words = {}
        except json.JSONDecodeError:
            logger.error("blacklisted_words.json is empty or invalid.")
            self.blacklisted_words = {}

        try:
            async with aiofiles.open('data/server_data.json', 'r+') as f:
                content = await f.read()
                self.servers_data = json.loads(content)
                logger.debug(self.servers_data)
                self.servers_data_loaded = True
        except FileNotFoundError:
            self.servers_data = {}
            self.servers_data_loaded = True
        except json.JSONDecodeError:
            logger.error("server_data.json is empty or invalid.")
            self.servers_data = {}
            self.servers_data_loaded = False
        
        try:
            async with aiofiles.open('data/server_data2.json', 'r+') as f:
                content = await f.read()
                self.server_data2 = json.loads(content)
                logger.debug("server_data2 loaded")
        except FileNotFoundError:
            self.server_data2 = {}
        except json.JSONDecodeError:
            logger.error("server_data2.json is empty or invalid.")
            self.server_data2 = {}

        try:
            async with self.db_connection.execute("SELECT total FROM counts WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    self.handled_messages = row[0]
        except Exception as e:
            logger.exception(e)
        
        """
        try:
            if self.custom_activity is not None:
                with open(self.custom_activity, 'r') as f:
                    self.activity_messages = f.read().splitlines()
            else:
                with open("resources/what.txt",'r') as f:
                    self.activity_messages = f.read().splitlines()
        except Exception as e:
            logger.exception(f"Error occured while trying to get activity message list: {e}")
        """
        try:
            output = subprocess.run(['git','rev-parse','--short','HEAD'], capture_output=True, text=True, check=True)
            self.commit_hash = output.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Error occured: {e}")
        except FileNotFoundError:
            logger.error("Git command not found. make sure to check if Git is installed.")
        
        for fname in os.listdir('./cogs'):
            if fname.endswith('.py'):
                logger.debug(f"Loading extension {fname[:-3]}.")

                if fname[:-3] in self.EXCLUDE_EXTENSIONS:
                    logger.warning("This extension has excluded from loading.")
                    continue

                try:
                    await self.load_extension(f"cogs.{fname[:-3]}")
                    logger.debug(f"Successfully loaded {fname[:-3]}.")
                except commands.ExtensionNotLoaded as e:
                    logger.exception(f"Extension {fname[:-3]} was not loaded due to {e}.")
                except commands.ExtensionNotFound:
                    logger.exception(f"Extension {fname[:-3]} was not found from cogs folder.")
                except commands.NoEntryPointError:
                    logger.exception(f"Extension {fname[:-3]} has no entrypoint to load.")
                except commands.ExtensionFailed as e:
                    logger.exception(f"Extension {fname[:-3]} has failed to load due to {e}.")
                except Exception as e:
                    logger.exception(f"Uncaught exception thrown while reloading, due to {e}.")

    async def on_ready(self):
        logger.info("Auth-code is {}".format(self.auth_code))
        if self.user:
            logger.info("\n".join((
                "The client is logged into a bot!",
                f"User ID: {self.user.id}",
                f"Username: {self.user.name}",
                f"Connected Guilds: {len(self.guilds)}",
                f"Guilds: {', '.join([guild.name for guild in self.guilds])}",
                f"Users: {len(self.users)}",
                f"Commit Hash: {self.commit_hash}",
                f"Session UUID: {self.session_uuid}",
                f"Launch Time: {self.launch_time.isoformat()}",
            )))
        else:
            logger.info("It seems client is connected with bot, but no user object found.")

        try:
            synced = await self.tree.sync()
            logger.info(f"Synchronized {len(synced)} commands.")
        except app_commands.CommandSyncFailure:
            logger.exception("CommandSyncFailure: Invalid command data")
        except Forbidden:
            logger.error("Forbidden: The bot doesn't have permission to use `application.commands`")
        except MissingApplicationID:
            logger.error("MissingApplicationID: The application ID is empty or missing")
        except app_commands.TranslationError as e:
            logger.exception(f"TranslationError: Error thrown while translating key {str(e.string)} in {e.locale} ({e.context.location.name})")
        except HTTPException:
            logger.error("HTTPException: Failed to sync commands")

    async def on_message(self,message: discord.Message):
        if message.author == self.user or message.mention_everyone: return
        
        if message.content.startswith("pox!"):
            self.handled_messages += 1
            logger.info(f"{message.author.id}, {message.content.replace('pox!','')}")
            await self.process_commands(message)
    
    async def on_command_error(self,ctx: commands.Context, e: commands.CommandError):
        try:
            logger.exception(f"Exception thrown: {e}!")

            embed = Embed(title="Error thrown while processing this command",
                          timestamp=datetime.datetime.now(),
                          color=Color.red())
            
            await ctx.reply(embed=embed)
        except Exception as e2:
            logger.exception(f"Couldn't send error embed: {e2}")
    
    async def on_interaction(self,inter: discord.Interaction):
        if inter.type == discord.InteractionType.application_command:
            self.processed_interactions += 1
            if inter.command_failed:
                self.failed_interactions += 1
                logger.error("The requested command thrown error!")

    async def close(self) -> None:
        async with aiofiles.open("data/blacklisted_words.json", 'w+') as f:
            await f.write(json.dumps(self.blacklisted_words, indent=4))
        
        async with aiofiles.open("data/server_data.json", 'w+') as f:
            await f.write(json.dumps(self.servers_data, indent=4))
        
        if self.server_data2_loaded:
            async with aiofiles.open("data/server_data2.json", 'w+') as f:
                await f.write(json.dumps(self.server_data2, indent=4))

        if self.settings_db:
            await self.settings_db.close()

        if self.stats_db:
            await self.stats_db.close()

        if self.economy_db:
            await self.economy_db.close()

        if self.mysql:
            self.mysql.close()
            await self.mysql.wait_closed()
            logger.debug("MySQL connection pool closed")
        
        if self.db_connection:
            await self.db_connection.commit()
            await self.db_connection.close()
            logger.debug("Database closed")
        
        return await super().close()
        
    def get_launch_time(self) -> datetime.datetime:
        return self.launch_time
    