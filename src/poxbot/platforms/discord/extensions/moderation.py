import re
from datetime import datetime

from discord import Color, Embed, Interaction, Member, Message, app_commands, utils
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....persistence.models import (
    AntiSpamFilter,
    BlacklistEntryMatchType,
    WordFilter,
)
from ....persistence.models.orm.moderation import ModerationEntry


class ModerationCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.user_message_timestamps: dict[int, list[float]] = {}

    @staticmethod
    def _match_type(entry: ModerationEntry) -> BlacklistEntryMatchType:
        try:
            return BlacklistEntryMatchType((entry.extras or {}).get('match_type', 0))
        except (TypeError, ValueError):
            return BlacklistEntryMatchType.default

    group = app_commands.Group(
        name='moderation',
        description=app_commands.locale_str('command.moderation.description'),
    )
    blacklist = app_commands.Group(
        name='blacklist',
        description=app_commands.locale_str('command.moderation.blacklist.description'),
        parent=group,
    )

    word_blacklist = app_commands.Group(
        name='word',
        description=app_commands.locale_str(
            'command.moderation.blacklist.word.description'
        ),
        parent=blacklist,
    )

    user_blacklist = app_commands.Group(
        name='user',
        description=app_commands.locale_str(
            'command.moderation.blacklist.user.description'
        ),
        parent=blacklist,
    )

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.database.guild:
            return

        config = await self.bot.database.guild.get_config(message.guild.id)
        filtering = config.filtering

        if not filtering.enabled:
            return

        me = message.guild.me
        has_permission = message.channel.permissions_for(me).manage_messages
        is_author_lower = (
            message.author.top_role < me.top_role
            if isinstance(message.author, Member)
            else True
        )

        if not (has_permission and is_author_lower):
            return

        word_cfg = filtering.filters.get('word')
        if isinstance(word_cfg, WordFilter) and word_cfg.enabled:
            content = message.content
            now = datetime.now(UTC).timestamp()
            entries = await self.bot.database.guild.get_moderation_entries(
                item_type='word',
                item_scope=message.guild.id,
            )

            for entry in entries:
                if entry.expires_at is not None and entry.expires_at <= now:
                    continue

                pattern = entry.value
                case_insensitive = bool(
                    (entry.extras or {}).get('case_insensitive', True)
                )
                flags = re.IGNORECASE if case_insensitive else 0
                match_type = self._match_type(entry)
                detected = False

                match match_type:
                    case BlacklistEntryMatchType.regex:
                        if re.search(pattern, content, flags):
                            detected = True
                    case BlacklistEntryMatchType.exact:
                        detected = (
                            pattern.lower() == content.lower()
                            if case_insensitive
                            else pattern == content
                        )
                    case BlacklistEntryMatchType.whole_word:
                        regex_pattern = rf'\b{re.escape(pattern)}\b'
                        if re.search(regex_pattern, content, flags):
                            detected = True
                    case _:
                        detected = (
                            pattern.lower() in content.lower()
                            if case_insensitive
                            else pattern in content
                        )

                if detected:
                    await message.delete()
                    return

        spam_cfg = filtering.filters.get('anti_spam')
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
                    self.bot.logger.warning(
                        '[AntiSpam] Deleted message from %s (%s)',
                        message.author,
                        user_id,
                    )
                except Exception:
                    self.bot.logger.exception('Failed to delete spam')

    @word_blacklist.command(
        name='add',
        description=app_commands.locale_str(
            'command.moderation.blacklist.word.add.description',
        ),
    )
    async def add_word(
        self,
        interaction: Interaction,
        trigger: str,
        match_type: BlacklistEntryMatchType = BlacklistEntryMatchType.default,
        case_insensitive: bool = True,
        reason: str | None = None,
    ):
        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer()

        embed = Embed()

        if not interaction.guild:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.guild_only.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.guild_only.description',
                loc,
            )
            return await interaction.followup.send(embed=embed)

        if not self.bot.database.guild:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.database_not_available.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.database_not_available.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

        config = await self.bot.database.guild.get_config(interaction.guild.id)

        normalized_trigger = trigger.lower()
        entries = await self.bot.database.guild.get_moderation_entries(
            item_type='word',
            item_scope=interaction.guild.id,
        )

        if any(entry.value.lower() == normalized_trigger for entry in entries):
            embed.title = self.bot.internal_translator.T(
                'error.embeds.confliction.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.confliction.description',
                loc,
                {'value': trigger},
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()
            return await interaction.followup.send(embed=embed)

        word_filter = config.filtering.filters.get('word')
        if not isinstance(word_filter, WordFilter):
            word_filter = WordFilter(enabled=True)
            config.filtering.filters['word'] = word_filter

            await self.bot.database.guild.update_config(interaction.guild.id, config)

        new_entry = await self.bot.database.guild.add_moderation_entry(
            item_type='word',
            value=trigger.lower() if case_insensitive else trigger,
            item_scope=interaction.guild.id,
            reasons=[reason] if reason else [],
            moderator=interaction.user.id,
            extras={
                'match_type': int(match_type),
                'case_insensitive': case_insensitive,
            },
        )

        embed.title = self.bot.internal_translator.T(
            'command.moderation.blacklist.word.add.embeds.default.title',
            loc,
        )
        embed.description = self.bot.internal_translator.T(
            'command.moderation.blacklist.word.add.embeds.default.description',
            loc,
            {
                'entry': new_entry.value,
                'id': str(new_entry.item_id)[:8],
                'type': self._match_type(new_entry).name,
            },
        )

        return await interaction.followup.send(embed=embed)

    @word_blacklist.command(
        name='remove',
        description=app_commands.locale_str(
            'command.moderation.blacklist.word.remove.description',
        ),
    )
    async def remove_word(self, interaction: Interaction, query: str):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer()

        embed = Embed()

        if not interaction.guild:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.guild_only.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.guild_only.description',
                loc,
            )
            return await interaction.followup.send(embed=embed)

        if not self.bot.database.guild:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.database_not_available.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.database_not_available.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

        config = await self.bot.database.guild.get_config(interaction.guild.id)

        wf = config.filtering.filters.get('word')
        if not isinstance(wf, WordFilter):
            embed.title = self.bot.internal_translator.T(
                'error.embeds.blacklist_not_configured.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.blacklist_not_configured.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

        removed = await self.bot.database.guild.remove_moderation_entries(
            item_type='word',
            item_scope=interaction.guild.id,
            query=query,
        )

        if removed:
            embed.title = self.bot.internal_translator.T(
                'command.moderation.blacklist.word.remove.embeds.default.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'command.moderation.blacklist.word.remove.embeds.default.description',
                loc,
                {'query': query},
            )
            return await interaction.followup.send(embed=embed)
        embed.title = self.bot.internal_translator.T(
            'command.moderation.blacklist.word.remove.embeds.not_found.title',
            loc,
        )
        embed.description = self.bot.internal_translator.T(
            'command.moderation.blacklist.word.remove.embeds.not_found.description',
            loc,
            {'query': query},
        )
        return await interaction.followup.send(embed=embed)

    @word_blacklist.command(
        name='list',
        description=app_commands.locale_str(
            'command.moderation.blacklist.word.list.description',
        ),
    )
    async def list_words(self, interaction: Interaction):
        loc = interaction.guild.preferred_locale if interaction.guild else 'en'
        await interaction.response.defer()

        embed = Embed()

        if not interaction.guild:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.guild_only.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.guild_only.description',
                loc,
            )
            return await interaction.followup.send(embed=embed)

        if not self.bot.database.guild:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.database_not_available.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.database_not_available.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)

        config = await self.bot.database.guild.get_config(interaction.guild.id)

        entries = await self.bot.database.guild.get_moderation_entries(
            item_type='word',
            item_scope=interaction.guild.id,
        )

        wf = config.filtering.filters.get('word')
        if not isinstance(wf, WordFilter) or not entries:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.blacklist_not_configured.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.blacklist_not_configured.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)

        embed.title = self.bot.internal_translator.T(
            'command.moderation.blacklist.word.list.embeds.default.title',
            loc,
        )

        lines = [
            f'`{str(e.item_id)[:8]}`: **{e.value}** ({self._match_type(e).name})'
            for e in entries[:20]
        ]
        embed.description = '\n'.join(lines)

        if len(entries) > 20:
            embed.set_footer(
                text=self.bot.internal_translator.T(
                    'command.moderation.blacklist.word.list.embeds.default.footer',
                    loc,
                    {'remaining': len(entries) - 20},
                ),
            )

        await interaction.followup.send(embed=embed)

    @word_blacklist.command(
        name='serverban',
        description=app_commands.locale_str(
            'command.moderation.user.serverban.description',
        ),
    )
    async def add_user_item(
        self,
        interaction: Interaction,
        user: Member,
        until: app_commands.Timestamp,
        reason: str | None,
    ):
        loc = await self.bot.get_locale(interaction, prefer_guild=True)
        await interaction.response.defer()

        now = utils.utcnow()
        remaining = until - now

        if remaining.total_seconds() <= 0:
            await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.moderation.user.serverban.texts.already_passed',
                    loc,
                ),
                ephemeral=True,
            )
            return


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
