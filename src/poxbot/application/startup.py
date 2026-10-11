from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import nltk

if TYPE_CHECKING:
    from .bot import PoxBot


def _download_nltk_data() -> None:
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)


async def startup(bot: PoxBot) -> None:
    await asyncio.to_thread(_download_nltk_data)

    await bot.counter_manager.load_async()

    try:
        await bot.tree.set_translator(bot.discord_translator)
    except TypeError:
        bot.logger.exception('Failed to set command translator')

    await bot.quake_manager.start()

    await bot.git_info.load()
    await bot.resources.initialize()
    await bot.database.connect()
    await bot.load_extensions()
    await bot.sync_commands()

    if bot.metrics is not None:
        bot.metrics.start_server()
        bot.logger.info(
            'Metrics pipeline is enabled.',
        )
