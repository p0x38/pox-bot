import asyncio
from importlib.metadata import version
from logging import getLogger
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

setup_logger("pox-bot")
logger = getLogger("pox-bot")


async def main():
    bot_start_time = perf_counter()
    load_dotenv()
    config = await ConfigManager.get_settings()

    manager = I18nManager(locales_path="src/assets/locales")
    await manager.initialize()

    init_duration = perf_counter() - bot_start_time
    logger.info(f"Pre-Initialization completed in {format_duration(init_duration)}")

    async with PoxBot(
        config=config,
        logger=logger,
        translation_manager=manager,
        internal_translator=manager.internal,
        discord_translator=manager.discord,
        intents=Intents.all(),
        command_prefix=commands.when_mentioned_or(config.bot_prefix)
    ) as bot:
        token = config.token_config.discord_token
        if not token or not token.strip():
            logger.critical("No DISCORD_TOKEN found in .env!")
            return

        logger.info("Starting bot...")
        await bot.start(token)


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
