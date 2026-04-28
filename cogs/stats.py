from datetime import datetime
import random
from typing import Optional

from discord.ext import commands
from discord import Color, Embed, Interaction, Message, app_commands
from pytz import UTC

from bot import PoxBot
from src.database.modules import StatsDatabase

from src.translator import translator_instance as i18n

class StatsCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot
        self.db: Optional[StatsDatabase] = bot.stats_db
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild:
            return
        
        if self.bot.guild_db and self.db:
            config = await self.bot.guild_db.get_config(message.guild.id)
            if not config.leveling_enabled:
                return
            
            xp_gain = int(random.randint(5, 15) * config.xp_rate)
            
            result = await self.db.add_xp(message.author.id, xp_gain)
            
            if result and result['leveled_up']:
                loc = message.guild.preferred_locale.value if message.guild else "en"
                embed = Embed(color=Color.gold())
                
                embed.description = i18n.T("messages.level_up", loc, {"mention": message.author.mention, "level": result['new_level']})
                
                await message.channel.send(embed=embed)
            
    group = app_commands.Group(name="stats", description=app_commands.locale_str("Leveling system.", message="command.stats.description"))
    
    @group.command(name="top", description=app_commands.locale_str("Show the top users.", message="command.stats.top.description"))
    async def leaderboard(self, interaction: Interaction):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        embed = Embed()
        
        await interaction.response.defer()
        
        if self.db:
            rows = await self.db.get_leaderboard(sort_by="xp", limit=25)
            
            embed = Embed(title=i18n.T("command.stats.top.embeds.default.title", loc), color=Color.gold())
            description = ""
            
            if rows:
                for i, row in enumerate(rows, 1):
                    user = self.bot.get_user(row['user_id']) or f"User({row['user_id']})"
                    description += f"**{i}.** {user} • Lvl {row['level']} ({row['xp']} XP)\n"
            else:
                description = "Wow, there's no one inside here."
            
            embed.description = description
            await interaction.followup.send(embed=embed)
        else:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))