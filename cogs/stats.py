from discord.ext import commands
from discord import Message, app_commands

from bot import PoxBot

class StatsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: PoxBot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot: return
        
        if self.bot.stats_db:
            await self.bot.stats_db.increment_message(message.author.id)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))