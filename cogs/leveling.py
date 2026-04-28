from collections import defaultdict
from datetime import datetime, timedelta
import random
import time
from typing import Optional
from discord.ext import commands
from discord import Color, Embed, Interaction, Member, Message, app_commands
from pytz import UTC
from bot import PoxBot
from src.translator import translator_instance as i18n
from logger import logger

class LevelingCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.cooldowns = {}
    
    group = app_commands.Group(name="leveling", description=app_commands.locale_str("command.leveling.description"))
    
    def calculate_xp(self, message: Message) -> int:
        content = message.content
        if not content: return random.randint(5, 10)
        
        words = content.split()
        word_count = len(words)
        char_count = len(content)
        
        base_xp = random.randint(5, 10)
        
        word_bonus = min(word_count // 2, 24)
        char_bonus = min(char_count // 10, 24)
        
        total_xp = base_xp + word_bonus + char_bonus
        
        return min(total_xp, 50)
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild: return
        
        user_id = message.author.id
        current_time = datetime.now(UTC)
        if user_id in self.cooldowns:
            cooldown_duration = current_time - self.cooldowns[user_id]
            if cooldown_duration < timedelta(seconds=60):
                return
        
        xp_to_add = self.calculate_xp(message)
        
        if not self.bot.stats_db:
            return
        
        result = await self.bot.stats_db.add_xp(user_id, xp_to_add)
        
        if result:
            self.cooldowns[user_id] = current_time
            
            if result["leveled_up"]:
                loc = message.guild.preferred_locale.value
                msg = i18n.T("messages.level_up", loc, {"mention": message.author.mention, "new_level": result["new_level"]})
                
                await message.channel.send(msg)
    
    @group.command(name="rank", description=app_commands.locale_str("command.leveling.rank.description"))
    async def show_rank(self, interaction: Interaction, member: Optional[Member] = None):
        await interaction.response.defer()
        
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        
        embed = Embed()
        
        if not self.bot.stats_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        target = member or interaction.user
        stats = await self.bot.stats_db.get_user_stats(target.id)
        
        if not stats:
            embed.title = i18n.T("error.embeds.user_data_not_found.title", loc)
            embed.description = i18n.T("error.embeds.user_data_not_found.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        level = stats.level
        xp = stats.xp
        
        current_lvl_base = int(pow(level, 4))
        next_lvl_base = int(pow(level + 1, 4))
        progress = xp - current_lvl_base
        needed = next_lvl_base - current_lvl_base
        
        filled = int((progress / max(needed, 1)) * 20)
        bar = f"[{'#' * filled}{' ' * (20 - filled)}]"
        
        embed.color = Color.blue()
        embed.title = i18n.T("command.leveling.rank.embeds.default.title", loc, {"user": target.display_name})
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name=i18n.T("command.leveling.rank.embeds.default.fields.level.name", loc), value=str(level), inline=True)
        embed.add_field(name=i18n.T("command.leveling.rank.embeds.default.fields.total.name", loc), value=f"{xp:,}", inline=True)
        embed.add_field(name=i18n.T("command.leveling.rank.embeds.default.fields.progress.name", loc), value=f"{bar} ({progress}/{needed} XP)", inline=False)
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))