import re
from datetime import datetime

from discord import (
    Color,
    Embed,
    Forbidden,
    HTTPException,
    Interaction,
    Member,
    Message,
    NotFound,
    User,
    app_commands,
    utils,
)
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....persistence.models import (
    AntiSpamFilter,
    BlacklistEntryMatchType,
    WordFilter,
)
from ....persistence.models.guild_settings_v2 import (
    AntiMessageFilter,
    GuildConfigV2,
    ProfanityFilter,
)
from ....persistence.models.orm.moderation import ModerationEntry
from ..checks.is_owner import is_bot_owner


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

    async def _add_user_restriction(
        self,
        interaction: Interaction,
        user: User | Member,
        *,
        scope: int,
        command_name: str,
        until: app_commands.Timestamp | None,
        reason: str | None,
    ) -> None:
        loc = await self.bot.get_locale(interaction, prefer_guild=True)
        await interaction.response.defer(ephemeral=True)

        database = self.bot.database.guild

        if not database:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.description',
                        loc,
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        now = utils.utcnow()
        if until is not None and until <= now:
            await interaction.followup.send(
                self.bot.internal_translator.T(
                    f'command.moderation.user.{command_name}.texts.already_passed',
                    loc,
                ),
                ephemeral=True,
            )
            return

        now_timestamp = now.timestamp()
        expires_at = until.timestamp() if until is not None else None
        target_id = str(user.id)

        entries = await database.get_moderation_entries(
            item_type='user',
            item_scope=scope,
        )

        already_restricted = any(
            entry.value == target_id
            and (entry.expires_at is None or entry.expires_at > now_timestamp)
            for entry in entries
        )

        if already_restricted:
            await interaction.followup.send(
                self.bot.internal_translator.T(
                    f'command.moderation.user.{command_name}.texts.already_banned',
                    loc,
                ),
                ephemeral=True,
            )
            return

        await database.add_moderation_entry(
            item_type='user',
            value=target_id,
            item_scope=scope,
            reasons=[reason] if reason else [],
            expires_at=expires_at,
            moderator=interaction.user.id,
        )

        kick_reason = (
            f'{command_name}: {reason}' if reason else f'{command_name} restriction'
        )
        failed_guilds: list[str] = []

        if command_name == 'serverban' and interaction.guild is not None:
            target_guild = interaction.guild
            target = (
                user if isinstance(user, Member) else target_guild.get_member(user.id)
            )

            if target is not None:
                try:
                    await target.kick(reason=kick_reason)
                except (Forbidden, HTTPException):
                    failed_guilds.append(target_guild.name)
                    self.bot.logger.exception(
                        'Failed to kick restricted user %s from guild %s',
                        user.id,
                        target_guild.id,
                    )

        until_text = (
            f'<t:{int(expires_at)}:F>' if expires_at is not None else 'permanently'
        )

        response = self.bot.internal_translator.T(
            f'command.moderation.user.{command_name}.texts.success',
            loc,
            {
                'user': user.mention,
                'until': until_text,
            },
        )

        if failed_guilds:
            response += '\n' + self.bot.internal_translator.T(
                f'command.moderation.user.{command_name}.texts.kick_failed',
                loc,
                {'guilds': ', '.join(failed_guilds)},
            )

        await interaction.followup.send(response, ephemeral=True)

    group = app_commands.Group(
        name='moderation',
        description=app_commands.locale_str('command.moderation.description'),
    )
    blacklist = app_commands.Group(
        name='blacklist',
        description=app_commands.locale_str('command.moderation.blacklist.description'),
        parent=group,
    )
    word_group = app_commands.Group(
        name='word',
        description=app_commands.locale_str(
            'command.moderation.blacklist.word.description'
        ),
        parent=group,
    )
    user_group = app_commands.Group(
        name='user',
        description=app_commands.locale_str(
            'command.moderation.blacklist.user.description'
        ),
        parent=group,
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

        message_cfg = filtering.filters.get('anti_message')
        if (
            isinstance(message_cfg, AntiMessageFilter)
            and message_cfg.enabled
            and message.author.id in message_cfg.blocked_user_ids
        ):
            try:
                await message.delete()
            except (Forbidden, NotFound, HTTPException):
                self.bot.logger.exception(
                    '[AntiMessage] Failed to delete message %s',
                    message.id,
                )
            else:
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

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        database = self.bot.database.guild
        if database is None:
            return

        now = utils.utcnow().timestamp()
        entries = await database.get_moderation_entries(
            item_type='user',
            item_scope=member.guild.id,
        )

        entry = next(
            (
                item
                for item in entries
                if item.value == str(member.id)
                and (item.expires_at is None or item.expires_at > now)
            ),
            None,
        )

        if entry is None:
            return

        reason = '; '.join(entry.reasons) or 'Active join restriction'

        try:
            await member.kick(
                reason=f'Active moderation restriction: {reason}',
            )
        except (Forbidden, HTTPException):
            self.bot.logger.exception(
                'Failed to enforce join restriction for user %s in guild %s',
                member.id,
                member.guild.id,
            )

    @blacklist.command(
        name='block_user_messages',
        description=app_commands.locale_str(
            'command.moderation.blacklist.block_user.messages.description',
        ),
    )
    async def block_user_from_messaging(
        self,
        interaction: Interaction,
        user: Member,
    ) -> None:
        loc = await self.bot.get_locale(interaction)
        database = self.bot.database.guild

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.guild_only.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.guild_only.description',
                        loc,
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        if database is None:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.description',
                        loc,
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        def mutate(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            anti_message = config.filtering.filters.get('anti_message')

            if not isinstance(anti_message, AntiMessageFilter):
                return False, 'not_configured'

            if not anti_message.enabled:
                return False, 'not_configured'

            if user.id in anti_message.blocked_user_ids:
                return False, 'already_blocked'

            anti_message.blocked_user_ids.append(user.id)
            return True, None

        _, success, message = await database.mutate_config(
            interaction.guild.id,
            mutate,
        )

        if not success:
            # Replace these keys with the corresponding keys in your locale files.
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'command.moderation.blacklist.block_user.messages.error.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        (
                            'command.moderation.blacklist.block_user.messages.'
                            f'{message or "not_configured"}'
                        ),
                        loc,
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        await interaction.followup.send(
            embed=Embed(
                title=self.bot.internal_translator.T(
                    'command.moderation.blacklist.block_user.messages.success.title',
                    loc,
                ),
                description=self.bot.internal_translator.T(
                    'command.moderation.blacklist.block_user.messages.success.description',
                    loc,
                ),
                timestamp=datetime.now(UTC),
                color=Color.green(),
            )
        )

    @blacklist.command(
        name='unblock_user_messages',
        description=app_commands.locale_str(
            'command.moderation.blacklist.unblock_user.messages.description',
        ),
    )
    async def unblock_user_from_messaging(
        self,
        interaction: Interaction,
        user: Member,
    ) -> None:
        loc = await self.bot.get_locale(interaction)
        database = self.bot.database.guild

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.guild_only.title', loc
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.guild_only.description', loc
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        if database is None:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.title', loc
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.description', loc
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        def mutate(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            anti_message = config.filtering.filters.get('anti_message')
            if not isinstance(anti_message, AntiMessageFilter):
                return False, 'not_configured'

            if user.id not in anti_message.blocked_user_ids:
                return False, 'not_blocked'

            anti_message.blocked_user_ids.remove(user.id)
            return True, None

        _, success, reason = await database.mutate_config(
            interaction.guild.id,
            mutate,
        )

        if not success:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'command.moderation.blacklist.unblock_user.messages.error.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        (
                            'command.moderation.blacklist.unblock_user.messages.'
                            f'{reason or "not_configured"}'
                        ),
                        loc,
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        await interaction.followup.send(
            embed=Embed(
                title=self.bot.internal_translator.T(
                    'command.moderation.blacklist.unblock_user.messages.success.title',
                    loc,
                ),
                description=self.bot.internal_translator.T(
                    'command.moderation.blacklist.unblock_user.messages.success.description',
                    loc,
                    {'user': user.mention},
                ),
                timestamp=datetime.now(UTC),
                color=Color.green(),
            )
        )

    @group.command(
        name='toggle_global_chat_swear_filter',
        description=app_commands.locale_str(
            'command.moderation.toggle_global_chat_swear_filter.description',
        ),
    )
    async def toggle_global_chat_swear_filter(
        self,
        interaction: Interaction,
    ) -> None:
        loc = await self.bot.get_locale(interaction, prefer_guild=True)
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.guild_only.title', loc
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.guild_only.description', loc
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        database = self.bot.database.guild
        if database is None:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.title', loc
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.description', loc
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        def mutate(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            filtering = config.filtering
            profanity = filtering.filters.get('profanity')

            if not isinstance(profanity, ProfanityFilter):
                return False, 'not_configured'

            if not filtering.enabled or not profanity.enabled:
                return False, 'not_configured'

            profanity.use_in_globalchat = not profanity.use_in_globalchat
            return True, ('enabled' if profanity.use_in_globalchat else 'disabled')

        _, success, status = await database.mutate_config(
            interaction.guild.id,
            mutate,
        )

        if not success:
            await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'command.moderation.toggle_global_chat_swear_filter.error.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'command.moderation.toggle_global_chat_swear_filter.error.not_configured',
                        loc,
                    ),
                    timestamp=datetime.now(UTC),
                    color=Color.red(),
                )
            )
            return

        await interaction.followup.send(
            embed=Embed(
                title=self.bot.internal_translator.T(
                    'command.moderation.toggle_global_chat_swear_filter.success.title',
                    loc,
                ),
                description=self.bot.internal_translator.T(
                    (f'command.moderation.toggle_global_chat_swear_filter.{status}'),
                    loc,
                ),
                timestamp=datetime.now(UTC),
                color=Color.green(),
            )
        )

    @word_group.command(
        name='add_word',
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

        def ensure_word_filter(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            filtering = config.filtering
            filtering.enabled = True

            word_filter = filtering.filters.get('word')
            if isinstance(word_filter, WordFilter):
                word_filter.enabled = True
                return True, None

            filtering.filters['word'] = WordFilter(enabled=True)
            return True, None

        await self.bot.database.guild.mutate_config(
            interaction.guild.id,
            ensure_word_filter,
        )

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

    @word_group.command(
        name='remove_word',
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

    @word_group.command(
        name='list_words',
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

    @user_group.command(
        name='serverban',
        description=app_commands.locale_str(
            'command.moderation.user.serverban.description',
        ),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def add_user_item(
        self,
        interaction: Interaction,
        user: Member,
        until: app_commands.Timestamp | None = None,
        reason: str | None = None,
    ) -> None:
        loc = await self.bot.get_locale(interaction, prefer_guild=True)

        if not interaction.guild:
            await interaction.response.send_message(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.guild_only.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.guild_only.description',
                        loc,
                    ),
                )
            )
            return

        await self._add_user_restriction(
            interaction,
            user,
            scope=interaction.guild.id,
            command_name='serverban',
            until=until,
            reason=reason,
        )

    @user_group.command(
        name='globalban',
        description=app_commands.locale_str(
            'command.moderation.user.globalban.description',
        ),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @is_bot_owner()
    async def global_ban(
        self,
        interaction: Interaction,
        user: User,
        until: app_commands.Timestamp | None = None,
        reason: str | None = None,
    ) -> None:
        await self._add_user_restriction(
            interaction,
            user,
            scope=-1,
            command_name='globalban',
            until=until,
            reason=reason,
        )

    @user_group.command(
        name='botban',
        description=app_commands.locale_str(
            'command.moderation.user.botban.description',
        ),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @is_bot_owner()
    async def bot_ban(
        self,
        interaction: Interaction,
        user: User,
        until: app_commands.Timestamp | None = None,
        reason: str | None = None,
    ) -> None:
        await self._add_user_restriction(
            interaction,
            user,
            scope=-2,
            command_name='botban',
            until=until,
            reason=reason,
        )


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
