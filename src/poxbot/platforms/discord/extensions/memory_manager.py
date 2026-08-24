import gc

from discord.ext import commands, tasks

from ....application.bot import PoxBot
from ....infrastructure.logger import get_logger


class MemoryManagerCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.logger = get_logger(__name__, prefix='MemoryManager')
        self.bot = bot
        self.cleanup_loop.start()

    async def cog_unload(self) -> None:
        self.cleanup_loop.cancel()

    @tasks.loop(minutes=30)
    async def cleanup_loop(self):
        collected = gc.collect()
        
        if collected > 0:
            self.logger.debug(
                'Cleared %d unreachable objects', collected,
            )


async def setup(bot: PoxBot):
    await bot.add_cog(MemoryManagerCog(bot))
