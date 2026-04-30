from datetime import datetime
import re

from discord.ext import commands
from discord import Color, Embed, Interaction, Member, Message, app_commands
from pytz import UTC

from bot import PoxBot
from logger import logger
from src.models import (
    FilterConfig,
    WordFilter,
    AntiSpamFilter,
    BlacklistEntry,
    BlacklistEntryMatchType
)
from src.translator import translator_instance as i18n

class ModerationCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.user_message_timestamps: dict[int, list[float]] = {}
    
    group = app_commands.Group(name="moderation", description=app_commands.locale_str("command.moderation.description"))
    blacklist = app_commands.Group(name="blacklist", description=app_commands.locale_str("command.moderation.blacklist.description"), parent=group)
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.guild_db:
            return
        
        config = await self.bot.guild_db.get_config(message.guild.id)
        filtering = config.filtering
        
        if not filtering.enabled:
            return
        
        me = message.guild.me
        has_permission = message.channel.permissions_for(me).manage_messages
        is_author_lower = message.author.top_role < me.top_role if isinstance(message.author, Member) else True
        
        if not (has_permission and is_author_lower):
            return
        
        word_cfg = filtering.filters.get("word")
        if isinstance(word_cfg, WordFilter) and word_cfg.enabled:
            content = message.content
            
            for entry in word_cfg.blacklists:
                pattern = entry.trigger
                flags = re.IGNORECASE if entry.case_insensitive else 0
                detected = False
                
                match (entry.type):
                    case BlacklistEntryMatchType.regex:
                        if re.search(pattern, content, flags):
                            detected = True
                    case BlacklistEntryMatchType.exact:
                        if entry.case_insensitive:
                            detected = (pattern.lower() == content.lower())
                        else:
                            detected = (pattern == content)
                    case BlacklistEntryMatchType.whole_word:
                        regex_pattern = rf"\b{re.escape(pattern)}\b"
                        if re.search(regex_pattern, content, flags):
                            detected = True
                    case _:
                        if entry.case_insensitive:
                            detected = (pattern.lower() in content.lower())
                        else:
                            detected = (pattern in content)
                
                if detected:
                    await message.delete()
                    return
        
        spam_cfg = filtering.filters.get("anti_spam")
        if isinstance(spam_cfg, AntiSpamFilter) and spam_cfg.enabled:
            user_id = message.author.id
            now = datetime.now(UTC).timestamp()
            
            user_times = self.user_message_timestamps.get(user_id, [])
            user_times = [t for t in user_times if t > now - spam_cfg.window_length]
            user_times.append(now)
            self.user_message_timestamps[user_id] = user_times
            
            if len(user_times) > spam_cfg.messages_per_window:
                try:
                    await message.delete()
                    logger.warning(f"[AntiSpam] Deleted message from {message.author} ({user_id})")
                except Exception as e:
                    logger.error(f"Failed to delete spam: {e}")
        
    @group.command(name="togglefeature", description=app_commands.locale_str("command.moderation.togglefeature.description"))
    @app_commands.describe(
        feature=app_commands.locale_str("command.moderation.togglefeature.parameters.feature.description"),
        state=app_commands.locale_str("command.moderation.togglefeature.parameters.state.description")
    )
    async def toggle_feature(self, interaction: Interaction, feature: str, state: bool):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        success = await self.bot.guild_db.toggle_feature(
            interaction.guild.id,
            feature,
            state,
            interaction.user.id
        )
        
        if success:
            embed.color = Color.green()
            embed.description = i18n.T(
                "command.moderation.togglefeature.embeds.default.description",
                loc,
                {
                    "feature_name": feature,
                    "state": state
                }
            )
        else:
            embed.color = Color.red()
            embed.title = i18n.T(
                "error.embeds.server_feature_not_found.title",
                loc
            )
            embed.description = i18n.T(
                "error.embeds.server_feature_not_found.description",
                loc,
                {
                    "feature": feature
                }
            )
        
        return await interaction.followup.send(embed=embed)
    
    @blacklist.command(name="add", description=app_commands.locale_str("command.moderation.blacklist.add.description"))
    async def add_word(
        self,
        interaction: Interaction,
        trigger: str,
        match_type: BlacklistEntryMatchType = BlacklistEntryMatchType.default,
        case_insensitive: bool = True,
        reason: str | None = None
    ):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        config = await self.bot.guild_db.get_config(interaction.guild.id)
        
        word_filter = config.filtering.filters.get("word")
        if not isinstance(word_filter, WordFilter):
            word_filter = WordFilter(enabled=True)
            config.filtering.filters["word"] = word_filter
        
        if any(entry.trigger == trigger for entry in word_filter.blacklists):
            embed.title = i18n.T("error.embeds.confliction.title", loc)
            embed.description = i18n.T("error.embeds.confliction.description", loc, {"value": trigger})
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        new_entry = BlacklistEntry(
            trigger=trigger.lower(),
            reason=reason,
            executed_by=interaction.user.id,
            timestamp=datetime.now(UTC).timestamp()
        )
        word_filter.blacklists.append(new_entry)
        
        await self.bot.guild_db.update_config(interaction.guild.id, config)
        
        embed.title = i18n.T('command.moderation.blacklist.add.embeds.default.title', loc)
        embed.description = i18n.T('command.moderation.blacklist.add.embeds.default.description', loc, {"entry": new_entry.trigger, "id": new_entry.id, "type": new_entry.type})
        
        return await interaction.followup.send(embed=embed)
    
    @blacklist.command(name="remove", description=app_commands.locale_str("command.moderation.blacklist.remove.description"))
    async def remove_word(self, interaction: Interaction, query: str):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        config = await self.bot.guild_db.get_config(interaction.guild.id)
        
        wf = config.filtering.filters.get("word")
        if not isinstance(wf, WordFilter):
            embed.title = i18n.T("error.embeds.blacklist_not_configured.title", loc)
            embed.description = i18n.T("error.embeds.blacklist_not_configured.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
        
        original_count = len(wf.blacklists)
        wf.blacklists = [e for e in wf.blacklists if e.id != query and e.trigger != query]
        
        if len(wf.blacklists) < original_count:
            await self.bot.guild_db.update_config(interaction.guild.id, config)
            
            embed.title = i18n.T('command.moderation.blacklist.remove.embeds.default.title', loc)
            embed.description = i18n.T('command.moderation.blacklist.remove.embeds.default.description', loc, {'query': query})
            return await interaction.followup.send(embed=embed)
        else:
            embed.title = i18n.T('command.moderation.blacklist.remove.embeds.not_found.title', loc)
            embed.description = i18n.T('command.moderation.blacklist.remove.embeds.not_found.description', loc, {'query': query})
            return await interaction.followup.send(embed=embed)
    
    @blacklist.command(name="list", description=app_commands.locale_str("command.moderation.blacklist.list.description"))
    async def list_words(self, interaction: Interaction):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        config = await self.bot.guild_db.get_config(interaction.guild.id)
        
        wf = config.filtering.filters.get("word")
        if not isinstance(wf, WordFilter) or not wf.blacklists:
            embed.title = i18n.T("error.embeds.blacklist_not_configured.title", loc)
            embed.description = i18n.T("error.embeds.blacklist_not_configured.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        embed.title = i18n.T('command.moderation.blacklist.list.embeds.default.title', loc)
        
        if len(wf.blacklists) != 0:
            lines = [f"`{e.id}`: **{e.trigger}** ({e.type.name})" for e in wf.blacklists[:20]]
            embed.description = "\n".join(lines)
        else:
            embed.description = i18n.T("command.moderation.blacklist.list.embeds.no_blacklist.description", loc)
        
        if len(wf.blacklists) > 20:
            embed.set_footer(text=i18n.T("command.moderation.blacklist.list.embeds.default.footer", loc, {"remaining": len(wf.blacklists) - 20}))
        
        await interaction.followup.send(embed=embed)
        
async def setup(bot):
    await bot.add_cog(ModerationCog(bot))