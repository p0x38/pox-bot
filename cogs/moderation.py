from datetime import datetime

from discord.ext import commands
from discord import Color, Embed, Interaction, Member, Message, app_commands
from pytz import UTC

from bot import PoxBot
from logger import logger
from src.models import ServerFeatureType

from src.translator import translator_instance as i18n

class ModerationCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.user_message_timestamps = {}
    
    group = app_commands.Group(name="moderation", description=app_commands.locale_str("Moderation management.", message="command.moderation.description"))
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild:
            return
        
        if self.bot.guild_db:
            config = await self.bot.guild_db.get_config(message.guild.id)
            
            me = message.guild.me
            has_permission = message.channel.permissions_for(me).manage_messages
            is_author_lower = message.author.top_role < me.top_role if isinstance(message.author, Member) else True
            
            if not (has_permission and is_author_lower):
                return
            
            if config.blacklist_enabled:
                content = message.content.lower()
                banned_words = [e.data for e in config.blacklists if e.entry_type == "word"]
                
                if any(word in content for word in banned_words):
                    logger.debug(f"Blacklisted word found; deleting")
                    return await message.delete()
            
            is_anti_spam = await self.bot.guild_db.get_feature(
                message.guild.id,
                ServerFeatureType.anti_spam
            )
            if is_anti_spam:
                user_id = message.author.id
                current_time = datetime.now(UTC).timestamp()
                
                user_times = self.user_message_timestamps.get(user_id, [])
                user_times = [t for t in user_times if t > current_time - 5]
                user_times.append(current_time)
                self.user_message_timestamps[user_id] = user_times
                
                if len(user_times) > 5:
                    await message.delete()
                    logger.warning(f"Spam detected from {message.author}")
    
    @group.command(name="togglefeature", description=app_commands.locale_str("Toggle server features.", message="command.moderation.togglefeature.description"))
    @app_commands.describe(
        feature=app_commands.locale_str("The feature to toggle.", message="command.moderation.togglefeature.parameters.feature.description"),
        state=app_commands.locale_str("On or Off", message="command.moderation.togglefeature.parameters.state.description")
    )
    async def toggle_feature(self, interaction: Interaction, feature: ServerFeatureType, state: bool):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embed.guild_only.title", loc)
            embed.description = i18n.T("error.embed.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if self.bot.guild_db:
            await self.bot.guild_db.set_feature(
                interaction.guild.id,
                feature,
                state,
                interaction.user.id
            )
            
            embed.description = i18n.T("command.moderation.togglefeature.embeds.default.description", loc, {"feature_name": feature.name, "state": state})
            
            return await interaction.followup.send(embed=embed)
        else:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
    
async def setup(bot):
    await bot.add_cog(ModerationCog(bot))