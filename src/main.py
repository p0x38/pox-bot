import asyncio
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv

from src.managers.i18n import I18nManager
from src.utils.number_format import format_duration

from .config.manager import ConfigManager
from .core import PoxBot
from .logger_factory.logger import setup_logger

__version__ = version("pox-bot")

logger = setup_logger(__name__)


async def main():
    base_path = Path(__file__).parent.parent
    load_dotenv()

    config = await ConfigManager.get_settings()
    logger.info("Config data:\n%s", config.model_dump_json(indent=4))
    bot_logger = setup_logger("pox-bot")

    manager = I18nManager(locales_path="src/assets/locales")
    await manager.initialize()
    
    token = config.token_config.discord_token
    if not token or not token.get_secret_value().strip():
        logger.critical("No DISCORD_TOKEN found in .env!")
        return
    
    secret_token = token.get_secret_value().strip()
    
    keep_running = True

    while keep_running:
        bot_start_time = perf_counter()

        async with PoxBot(
            config=config,
            logger=bot_logger,
            translation_manager=manager,
            internal_translator=manager.internal,
            discord_translator=manager.discord,
            intents=Intents.all(),
            command_prefix=commands.when_mentioned_or(config.bot_prefix),
            root_path=base_path,
        ) as bot:
            bot.should_restart = False
            
            try:
                logger.info("Starting bot...")
                await bot.start(token.get_secret_value().strip())
            except Exception:
                logger.exception("Exception occurred while running the bot.")
                keep_running = False
                break
            finally:
                keep_running = getattr(bot, "should_restart", False)
        
        if keep_running:
            logger.info("Bot instance will restart in 5 seconds...")
            await asyncio.sleep(5)


def run():
    try:
        logger.info("Starting main framework...")
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Uncaught Exception thrown!")
    finally:
        logger.info("Bot has been closed")
