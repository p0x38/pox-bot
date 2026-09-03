import asyncio
import inspect
import random
from datetime import datetime, timedelta
from textwrap import shorten
from typing import Any, cast

from aiocache import cached
from discord import (
    Activity,
    ActivityType,
    ClientStatus,
    Color,
    CustomActivity,
    Embed,
    Forbidden,
    Game,
    HTTPException,
    Interaction,
    Member,
    SelectOption,
    Spotify,
    Streaming,
    TextChannel,
    TextStyle,
    User,
    app_commands,
    ui,
)
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....shared.utils import (
    crop_word,
    format_status,
    get_next_power_of_two,
    parse_duration,
)
from ....shared.utils.formats.user import format_userflags
from ....shared.utils.text_util import format_discord_message

MAX_TIMEOUT = timedelta(days=28)
SUFFIX = 'Action taken by {} via ContextMenu'


class TimeoutModal(ui.Modal, title='User timeout'):
    def __init__(self, bot: PoxBot, target: Member):
        super().__init__()
        self.bot = bot
        self.target = target
        self.reason_suffix = SUFFIX.format(target.display_name)
        self.embed = Embed(color=Color.red())

    duration = ui.TextInput(
        label='Duration',
        placeholder='e.g. 1d 2h (1 day 2 hours), 02:00 (2 minutes), 3600 (1 hour)',
        required=True,
    )

    reason = ui.TextInput(
        label='Reason',
        style=TextStyle.paragraph,
        required=False,
        max_length=250,
    )

    async def on_submit(self, interaction: Interaction):
        loc = str(interaction.locale)
        try:
            td = parse_duration(self.duration.value)

            if td.total_seconds() <= 0:
                raise ValueError(
                    self.bot.internal_translator.T(
                        'error.custom.timeout_duration_lessflow',
                        loc,
                    ),
                )

            td = min(td, MAX_TIMEOUT)

            if not interaction.guild:
                raise RuntimeError(
                    self.bot.internal_translator.T('error.custom.guild_only', loc),
                )

            if isinstance(interaction.user, User):
                raise TypeError(
                    self.bot.internal_translator.T('error.exceptions.Unknown', loc),
                )

            if self.target == interaction.user:
                raise RuntimeError(
                    self.bot.internal_translator.T(
                        'error.custom.tried_to_timeout_himself',
                        loc,
                    ),
                )

            if self.target == interaction.guild.owner:
                raise RuntimeError(
                    self.bot.internal_translator.T(
                        'error.custom.tried_to_timeout_owner',
                        loc,
                    ),
                )

            if self.target.top_role >= interaction.user.top_role:
                raise RuntimeError(
                    self.bot.internal_translator.T(
                        'error.custom.tried_to_timeout_higher',
                        loc,
                    ),
                )

            if not interaction.guild.me.guild_permissions.moderate_members:
                raise RuntimeError(
                    self.bot.internal_translator.T(
                        'error.custom.forbidden_timeout',
                        loc,
                    ),
                )

            if self.target.top_role >= interaction.guild.me.top_role:
                raise RuntimeError(
                    self.bot.internal_translator.T(
                        'error.custom.cannot_timeout_higher',
                        loc,
                    ),
                )

            try:
                timeout_reason = (
                    self.reason.value or 'No reason specified from executor'
                )
                await self.target.timeout(
                    td,
                    reason=timeout_reason + self.reason_suffix,
                )
            except Exception as e:
                self.embed.description = f'Exception thrown!\n{e}'
                self.bot.logger.exception('Failed to set timeout')
                await interaction.response.send_message(embed=self.embed)
                return

            self.embed.description = self.bot.internal_translator.T(
                'messages.timed_out_user',
                loc,
                {'user': self.target.mention, 'length': td},
            )

            await interaction.response.send_message(embed=self.embed)
        except Exception as e:
            self.embed.description = f'Exception thrown!\n{e}'
            self.bot.logger.exception('Failed to send')
            await interaction.response.send_message(embed=self.embed)


class DynamicUserInfoView(ui.View):
    def __init__(self, bot: PoxBot, member: Member, categories: dict, locale: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.member = member
        self.categories = categories
        self.locale = locale

        self.add_item(self.create_select())

    def create_select(self):
        options = []
        for key, data in self.categories.items():
            label = self.bot.internal_translator.T(
                f'modal.DynamicUserInfoView.fields.{key}',
                self.locale,
            )
            description = self.bot.internal_translator.T(data.get('desc'), self.locale)

            options.append(
                SelectOption(
                    label=label,
                    value=key,
                    description=description,
                    emoji=data.get('emoji'),
                ),
            )

        select = ui.Select(
            placeholder=self.bot.internal_translator.T(
                'modal.DynamicUserInfoView.placeholder',
                self.locale,
            ),
            options=options,
        )

        select.callback = self.select_callback
        return select

    async def select_callback(self, interaction: Interaction):
        await interaction.response.defer()

        data = cast(dict[str, Any], interaction.data or {})
        selected_values = data.get('values')
        if not isinstance(selected_values, list) or not selected_values:
            return await interaction.followup.send(
                'Category not found.',
                ephemeral=True,
            )

        selected_label = selected_values[0]
        category_data = self.categories.get(selected_label)

        if not category_data:
            return await interaction.followup.send(
                'Category not found.',
                ephemeral=True,
            )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'modal.DynamicUserInfoView.embeds.default.title',
                interaction.locale,
                {'category': selected_label},
            ),
            color=Color.brand_green(),
        )

        embed.set_author(
            name=self.member.display_name,
            icon_url=self.member.display_avatar.url,
        )

        for field_name, field_value in category_data.get('fields', {}).items():
            if inspect.iscoroutinefunction(field_value):
                display_value = await field_value(self.member)
            elif callable(field_value):
                display_value = field_value(self.member)
            else:
                display_value = field_value

            translated_field_name = self.bot.internal_translator.T(
                f'modal.DynamicUserInfoView.fields.{field_name}',
                self.locale,
            )
            embed.add_field(
                name=translated_field_name,
                value=display_value,
                inline=True,
            )

        await interaction.edit_original_response(embed=embed, view=self)


class UserCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

        @app_commands.context_menu(
            name=app_commands.locale_str('context_menu.kick_member.name'),
        )
        @app_commands.checks.has_permissions(kick_members=True)
        @app_commands.guild_only()
        async def contextmenu_kick(interaction: Interaction, member: Member):
            loc = (
                await self.bot.database.settings.get_locale(interaction)
                if self.bot.database.settings
                else interaction.locale
            )
            embed = Embed(color=Color.red())

            await interaction.response.defer()

            try:
                await member.kick(
                    reason=(
                        f'{interaction.user.display_name} kicked user via Context menu'
                    ),
                )
                embed.description = self.bot.internal_translator.T(
                    'messages.kick_user',
                    loc,
                    {'user': member.display_name},
                )
            except Forbidden:
                embed.description = self.bot.internal_translator.T(
                    'error.custom.insufficient_permission_kick',
                    loc,
                    {'user': member.display_name},
                )
            except HTTPException:
                embed.description = self.bot.internal_translator.T(
                    'error.exceptions.HTTPException',
                    loc,
                )
            except Exception as e:
                embed.description = self.bot.internal_translator.T(
                    'error.exceptions.Unknown',
                    loc,
                    {'e': e},
                )
            finally:
                await interaction.followup.send(embed=embed)

        @app_commands.context_menu(
            name=app_commands.locale_str('context_menu.ban_member.name'),
        )
        @app_commands.checks.has_permissions(ban_members=True)
        @app_commands.guild_only()
        async def contextmenu_ban(interaction: Interaction, member: Member):
            loc = (
                await self.bot.database.settings.get_locale(interaction)
                if self.bot.database.settings
                else interaction.locale
            )
            embed = Embed(color=Color.red())

            await interaction.response.defer()

            try:
                await member.ban(
                    reason=(
                        f'{interaction.user.display_name} banned user via Context menu'
                    ),
                )
                embed.description = self.bot.internal_translator.T(
                    'messages.ban_user',
                    loc,
                    {'user': member.display_name},
                )
            except Forbidden:
                embed.description = self.bot.internal_translator.T(
                    'error.custom.insufficient_permission_ban',
                    loc,
                    {'user': member.display_name},
                )
            except HTTPException:
                embed.description = self.bot.internal_translator.T(
                    'error.exceptions.HTTPException',
                    loc,
                )
            except Exception as e:
                embed.description = self.bot.internal_translator.T(
                    'error.exceptions.Unknown',
                    loc,
                    {'e': e},
                )
            finally:
                await interaction.followup.send(embed=embed)

        @app_commands.context_menu(
            name=app_commands.locale_str('context_menu.timeout_member.name'),
        )
        @app_commands.checks.has_permissions(moderate_members=True)
        @app_commands.guild_only()
        async def contextmenu_timeout(interaction: Interaction, member: Member):
            await interaction.response.send_modal(TimeoutModal(self.bot, member))

        bot.tree.add_command(contextmenu_kick)
        bot.tree.add_command(contextmenu_ban)
        bot.tree.add_command(contextmenu_timeout)

    group = app_commands.Group(
        name='user',
        description=app_commands.locale_str('command.user.description'),
    )
    global_group = app_commands.Group(
        name='user_global',
        description=app_commands.locale_str('command.user.description'),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True,
            dm_channel=True,
            private_channel=True,
        ),
    )

    @group.command(
        name='guild_duration',
        description='Checks how long user has been in the server.',
    )
    @app_commands.guild_only()
    async def check_how_long_user_has_been(
        self,
        interaction: Interaction,
        member: Member,
    ):
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(
                'You must be run this command in guild mode',
            )

        try:
            embed = Embed(title=f'How long {member.name} has been on server?')
            joined_date = member.joined_at
            if not joined_date:
                raise RuntimeError('Welp')

            now = datetime.now(joined_date.tzinfo)

            duration = now - joined_date

            embed.description = (
                f'{member.name} has been on the server for {duration} days'
            )
            embed.color = Color.green()

            await interaction.followup.send(embed=embed)
        except Exception:
            self.bot.logger.exception('Failed to lookup')
            await interaction.followup.send('sry errored')

    @global_group.command(
        name='user_profile',
        description=app_commands.locale_str('command.user.info.description'),
    )
    async def check_user_info(self, interaction: Interaction, member: Member | User):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale.value
        )
        await interaction.response.defer(thinking=True)
        try:
            user = (
                interaction.guild.get_member(member.id) if interaction.guild else member
            )
            if user:
                e = Embed(
                    title=self.bot.internal_translator.T(
                        'command.user.info.embeds.default.title',
                        loc,
                        {'user': user.display_name},
                    ),
                )
                temp1 = {
                    'user_id': user.id,
                    'user_name': f'`{user.display_name}`',
                    'user_bot': self.bot.internal_translator.T(
                        'text.boolean.true' if user.bot else 'text.boolean.false',
                        loc,
                    ),
                    'user_type': self.bot.internal_translator.T(
                        'text.user_type.user',
                        loc,
                    ),
                    'user_creation': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    + f' (<t:{int(user.created_at.timestamp())}:R>)',
                }

                translated_strings = []

                for key in format_userflags(user.public_flags):
                    result = self.bot.internal_translator.T(key, loc)
                    if result == key:
                        continue

                    translated_strings.append(result)

                temp1['user_additional'] = ', '.join(translated_strings)

                if user.system:
                    temp1['user_type'] = self.bot.internal_translator.T(
                        'text.user_type.system',
                        loc,
                    )
                elif user.bot:
                    temp1['user_type'] = self.bot.internal_translator.T(
                        'text.user_type.bot',
                        loc,
                    )

                if isinstance(user, Member):
                    roles = [role for role in user.roles if role.name != '@everyone']
                    temp1['user_highest_role'] = f'<@&{user.top_role.id}>'
                    temp1['user_join'] = (
                        user.joined_at.strftime('%Y-%m-%d %H:%M:%S')
                        + f' (<t:{int(user.joined_at.timestamp())}:R>)'
                        if user.joined_at
                        else (self.bot.internal_translator.T('text.unknown_join', loc))
                    )
                    temp1['user_roles'] = ', '.join(
                        [f'<@&{role.id}>' for role in roles],
                    )
                    temp1['user_status'] = format_status(
                        self.bot,
                        user.client_status,
                        loc,
                    )
                    temp1['user_nitro'] = (
                        user.premium_since.strftime('%Y-%m-%d %H:%M:%S')
                        if user.premium_since
                        else self.bot.internal_translator.T('label.non_nitro', loc)
                    )
                if self.bot.database.economy:
                    economy_data = await self.bot.database.economy.get_user(member.id)
                    if economy_data:
                        wallet = economy_data.wallet or 0
                        temp1['user_wallet'] = self.bot.internal_translator.T(
                            'command.user.info.fields.wallet',
                            loc,
                            {'coins': f'{wallet:,}'},
                        )
                if self.bot.database.stats:
                    statistics_data = await self.bot.database.stats.get_user_statistics(
                        member.id,
                    )
                    if statistics_data:
                        level = statistics_data.level
                        xp = statistics_data.xp
                        messages = statistics_data.total_messages

                        temp1['user_stats'] = self.bot.internal_translator.T(
                            'command.user.info.fields.stats',
                            loc,
                            {
                                'level': f'{level:,}',
                                'xp': f'{xp:,}',
                                'messages': f'{messages:,}',
                            },
                        )
                if self.bot.database.user:
                    data = await self.bot.database.user.get_full_profile(member.id)
                    if data:
                        nickname = data.nickname or self.bot.internal_translator.T(
                            'text.unknown',
                            loc,
                        )
                        description = (
                            data.description
                            or self.bot.internal_translator.T(
                                'error.custom.description_not_found',
                                loc,
                            )
                        )
                        temp1['user_nickname'] = nickname
                        temp1['user_description'] = description
                        e.description = description

                temp1 = self.bot.internal_translator.translate_map(temp1, loc)
                if isinstance(user, Member):
                    for index_activity, activity in enumerate(user.activities):
                        if isinstance(activity, Activity):
                            info = ''
                            match activity.type:
                                case ActivityType.custom:
                                    info = activity.name
                                case _:
                                    info = self.bot.internal_translator.T(
                                        f'text.activity_type.{activity.type.name}',
                                        loc,
                                        {'activity': activity.name},
                                    )

                            temp1[f'Activity #{index_activity}'] = (
                                f'{info} ({activity.state})'
                            )
                        elif isinstance(activity, Game):
                            temp1[f'Activity #{index_activity}'] = (
                                self.bot.internal_translator.T(
                                    'text.activity_type.game',
                                    loc,
                                    {
                                        'activity': activity.name,
                                        'platform': activity.platform,
                                    },
                                )
                            )
                        elif isinstance(activity, Streaming):
                            temp1[f'Activity #{index_activity}'] = (
                                self.bot.internal_translator.T(
                                    'text.activity_type.stream',
                                    loc,
                                    {
                                        'activity': activity.name,
                                        'platform': activity.platform,
                                    },
                                )
                            )
                        elif isinstance(activity, CustomActivity):
                            temp1[f'Activity #{index_activity}'] = activity.name
                        elif isinstance(activity, Spotify):
                            temp1[f'Activity #{index_activity}'] = (
                                self.bot.internal_translator.T(
                                    'text.activity_type.spotify',
                                    loc,
                                    {
                                        'title': activity.title,
                                        'artist': activity.artist,
                                        'album': activity.album,
                                    },
                                )
                            )
                        else:
                            temp1[f'Activity #{index_activity}'] = (
                                self.bot.internal_translator.T('text.unknown', loc)
                            )

                for key, value in temp1.items():
                    e.add_field(name=key, value=value, inline=True)

                if user.display_avatar:
                    e.set_thumbnail(url=user.display_avatar.url)
                else:
                    e.set_thumbnail(url=user.default_avatar.url)

                return await interaction.followup.send(embed=e)
            return await interaction.followup.send(
                self.bot.internal_translator.T('error.custom.user_not_found', loc),
            )
        except Exception as e:
            self.bot.logger.exception('Failed to retrieve user data')
            return await interaction.followup.send(f'Error. {e}')

    @global_group.command(
        name='set-profile',
        description=app_commands.locale_str('command.user.set_profile.description'),
    )
    async def set_user_community_profile(
        self,
        interaction: Interaction,
        nickname: str | None = None,
        description: str | None = None,
    ):
        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer()

        embed = Embed()

        if not self.bot.database.user:
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

        await self.bot.database.user.update_profile(
            interaction.user.id,
            description,
            nickname,
        )

        embed.title = self.bot.internal_translator.T(
            'command.user.set_profile.embeds.default.title',
            loc,
        )
        embed.description = self.bot.internal_translator.T(
            'command.user.set_profile.embeds.default.description',
            loc,
            {'nickname': nickname, 'description': description},
        )

        await interaction.followup.send(embed=embed)

    @cached(60)
    @global_group.command(
        name='avatar',
        description=app_commands.locale_str('command.user.avatar.description'),
    )
    async def get_user_avatar(self, interaction: Interaction, member: User | Member):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )
        await interaction.response.defer()

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.user.avatar.embeds.default.title',
                loc,
                {'user': member.name},
            ),
        )
        embed.set_image(
            url=member.display_avatar.url
            if member.display_avatar
            else member.default_avatar.url,
        )
        embed.set_footer(
            text=self.bot.internal_translator.T(
                'command.user.avatar.embeds.default.footer',
                loc,
                {'author': interaction.user.display_name},
            ),
            icon_url=(
                interaction.user.display_avatar.url
                if interaction.user.display_avatar
                else interaction.user.default_avatar.url
            ),
        )

        return await interaction.followup.send(embed=embed)

    @group.command(name='kick', description='Kick a member.')
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member='Member to kick.')
    @app_commands.describe(reason='Reason for member to give in DM.')
    @app_commands.guild_only()
    async def kick(
        self,
        interaction: Interaction,
        member: Member,
        reason: str | None = None,
    ):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )
        await interaction.response.defer()
        embed = Embed()
        try:
            await member.kick(
                reason=(
                    reason if reason is not None else 'Reason not provided by issuer.'
                ),
            )
            embed.description = self.bot.internal_translator.T(
                'messages.kick_user',
                loc,
                {'user': member.display_name},
            )
        except Forbidden:
            embed.description = self.bot.internal_translator.T(
                'error.custom.insufficient_permission_kick',
                loc,
                {'user': member.display_name},
            )
        except HTTPException:
            embed.description = self.bot.internal_translator.T(
                'error.exceptions.HTTPException',
                loc,
            )
        except Exception as e:
            embed.description = self.bot.internal_translator.T(
                'error.exceptions.Unknown',
                loc,
                {'e': e},
            )
        finally:
            await interaction.followup.send(embed=embed)

    @group.command(name='ban', description='Bans member from the server')
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member='Member to ban')
    @app_commands.describe(reason='Reason to ban')
    @app_commands.guild_only()
    async def ban_member(self, ctx: Interaction, member: Member, *, reason: str = ''):
        try:
            await member.ban(reason=reason)
            await member.send(
                f"You're banned by {ctx.user.name}."
                "\nReason: {reason if reason else 'No reason provided'}",
            )
            return await ctx.response.send_message(
                f'Banned <@{member.id}>.',
                ephemeral=True,
            )
        except Exception as e:
            return await ctx.response.send_message(
                f'Failed to ban. {e}',
                ephemeral=True,
            )

    @group.command(name='unban', description='Unbans member')
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member='Member to unban')
    @app_commands.guild_only()
    async def unban_member(self, ctx: Interaction, member: Member):
        try:
            await member.unban()
            return await ctx.response.send_message(
                f'Unbanned {member.name}.',
                ephemeral=True,
            )
        except Exception as e:
            return await ctx.response.send_message(
                f'Failed to unban. {e}',
                ephemeral=True,
            )

    @group.command(name='warn', description='Warns member')
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member='Member to warn')
    @app_commands.describe(reason='Reason to warn')
    @app_commands.guild_only()
    async def warn_member(self, ctx: Interaction, member: Member, *, reason: str = ''):
        try:
            await member.send(
                f"You're warned by {ctx.user.name}.\n\nReason: `{reason}`",
            )
            return await ctx.response.send_message(
                f'Warned <@{member.id}>.',
                ephemeral=True,
            )
        except Exception as e:
            self.bot.logger.exception('Failed to warn user')
            return await ctx.response.send_message(f'Failed to warn. {e}')

    @group.command(name='timeout', description='Warns member')
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member='Member to time-out')
    @app_commands.describe(reason='Reason to time-out')
    @app_commands.describe(length='Length of time-out (minutes)')
    @app_commands.guild_only()
    async def timeout_member(
        self,
        ctx: Interaction,
        member: Member,
        reason: str = '',
        length: int = 1,
    ):
        await member.timeout(
            timedelta(minutes=length),
            reason=(
                f"You're timed out. "
                f'{reason if reason else "No reason provided from source"}", '
                f'by {ctx.user.name}'
            ),
        )
        return await ctx.response.send_message(
            f'Timed out {member.mention} for {length} minutes.',
        )

    @group.command(name='remove_timeout', description='Un-timeout member')
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member='Member to remove timeout')
    @app_commands.guild_only()
    async def untimeout_member(self, ctx: Interaction, member: Member):
        await member.edit(timed_out_until=None)
        return await ctx.response.send_message(
            f'Took the timeout for {member.mention}.',
        )

    @group.command(name='total_members', description='Returns total members')
    @app_commands.guild_only()
    async def get_list_members(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title='Members in this server', description='')

        if interaction.guild:
            embed.description = ', '.join(
                [f'<@{m.id}>' for m in interaction.guild.members]
            )
        else:
            embed.description = 'This command only works in guild.'
            return await interaction.followup.send(embed=embed)

        return await interaction.followup.send(embed=embed)

    @group.command(
        name='set_nick',
        description=app_commands.locale_str('command.user.set_nick.description'),
    )
    @app_commands.guild_only()
    async def change_nickname(
        self,
        interaction: Interaction,
        member: Member,
        new_nick: str | None = None,
    ):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )
        await interaction.response.defer()

        embed = Embed()

        try:
            if new_nick is None:
                await member.edit(
                    nick=None,
                    reason=self.bot.internal_translator.T(
                        'command.user.set_nick.reasons.reset',
                        loc,
                        {'user': member.mention, 'author': interaction.user.name},
                    ),
                )
                embed.description = self.bot.internal_translator.T(
                    'command.user.set_nick.embeds.reset.description',
                    loc,
                    {'user': member.mention},
                )
                return await interaction.followup.send(embed=embed)
            await member.edit(
                nick=None,
                reason=self.bot.internal_translator.T(
                    'command.user.set_nick.reasons.changed',
                    loc,
                    {'user': member.mention, 'author': interaction.user.name},
                ),
            )
            embed.description = self.bot.internal_translator.T(
                'command.user.set_nick.embeds.changed.description',
                loc,
                {'user': member.mention, 'new_nickname': new_nick},
            )
            return await interaction.followup.send(embed=embed)
        except Forbidden:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.missing_permission.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.missing_permission.description',
                loc,
                {'missing': 'Manage Nicknames'},
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()
            return await interaction.followup.send(embed=embed)

    @group.command(
        name='status',
        description=app_commands.locale_str('command.user.status.description'),
    )
    @app_commands.guild_only()
    async def get_user_status(self, interaction: Interaction, member: Member):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )
        await interaction.response.defer()
        result = self.bot.internal_translator.T('text.unknown', loc)

        if interaction.guild:
            member2 = interaction.guild.get_member(member.id)
            if member2:
                result = member2.client_status

        e = Embed()
        e.title = self.bot.internal_translator.T(
            'command.user.status.embeds.default.title',
            loc,
            {'user': member.display_name},
        )
        e.description = (
            format_status(self.bot, result, loc)
            if isinstance(result, ClientStatus)
            else result
        )
        return await interaction.followup.send(embed=e)

    @group.command(
        name='to_reachgoal',
        description='Returns remaining members to reach a goal value.',
    )
    @app_commands.guild_only()
    async def get_remaining_members(
        self,
        interaction: Interaction,
        goal: int | None = None,
    ):
        if interaction.guild is None:
            return await interaction.response.send_message(
                'Object is not guild',
                ephemeral=True,
            )

        member_count = len(interaction.guild.members)

        embed = Embed(title='Number of remaining members to reach the desired value')

        await interaction.response.defer()

        if goal is None:
            goal = get_next_power_of_two(member_count)
            # goal = (round(member_count/1000)*1000)+1000

        remaining = goal - member_count

        if remaining <= 0:
            embed.description = (
                f'The server has already reached the goal of {goal} members!'
            )
            embed.color = Color.green()
        else:
            embed.description = (
                f'The server needs {remaining} more members'
                f'to reach the goal of {goal} members.'
            )
            embed.color = Color.blurple()

        return await interaction.followup.send(embed=embed)

    @cached(60)
    @group.command(
        name='find_first_message_contains',
        description=(
            'Finds the first message sent by specified user'
            'containing the keyword in the current channel.'
        ),
    )
    @app_commands.guild_only()
    @app_commands.describe(member='Member to search messages for.')
    @app_commands.describe(keyword='Keyword to search for in messages.')
    async def find_first_message_contains(
        self,
        interaction: Interaction,
        member: Member,
        keyword: str,
    ):
        await interaction.response.defer(thinking=True)
        if not interaction.channel:
            return await interaction.followup.send(
                'This command can only be used in guild channels.',
            )

        first_message = None

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None, oldest_first=True):
                if (
                    msg.author.id == member.id
                    and keyword.lower() in msg.content.lower()
                ):
                    first_message = msg
                    break

                await asyncio.sleep(0.5)

        embed = Embed(
            title=f"First message by {member.display_name} containing '{keyword}'",
            description='',
        )

        if first_message and first_message.guild:
            # TODO: change to format_discord_message
            message_url = (
                f'https://discord.com/channels/'
                f'{first_message.guild.id}/'
                f'{first_message.channel.id}/'
                f'{first_message.id}'
            )

            embed.description = (
                f'[{first_message.created_at:%Y-%m-%d %H:%M:%S}]'
                f'({message_url}): {first_message.content}'
            )
            embed.color = Color.blue()
        else:
            embed.description = (
                f'No messages found by {member.display_name} containing '
                f"'**{keyword}**'."
            )
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)

    @cached(120)
    @group.command(
        name='search_messages',
        description='Searches messages sent by specified user in the current channel.',
    )
    @app_commands.guild_only()
    @app_commands.describe(member='Member to search messages for.')
    @app_commands.describe(keyword='Keyword to search for in messages.')
    async def search_user_messages(
        self,
        interaction: Interaction,
        member: Member,
        keyword: str,
    ):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None:
            return await interaction.followup.send(
                'This command can only be used in guild channels.',
            )

        messages = []

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None):
                if len(messages) >= 15:
                    break

                if (
                    msg.author.id == member.id
                    and keyword.lower() in msg.content.lower()
                ):
                    self.bot.logger.debug(
                        'Found message: %s by %s',
                        msg.content,
                        msg.author.name,
                    )
                    messages.append(msg)

        embed = Embed(
            title=f"Messages by {member.display_name} containing '{keyword}'",
            description='',
        )

        if messages:
            lines = [
                format_discord_message(
                    msg,
                    lambda content: (
                        crop_word(content, keyword)
                        or shorten(
                            content,
                            width=30,
                        )
                    ),
                )
                for msg in messages
            ]

            embed.description = '\n'.join(lines)
            embed.color = Color.blue()
        else:
            embed.description = (
                f'No messages found by {member.display_name} containing'
                f" '**{keyword}**'."
            )
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)

    @cached(120 * 2)
    @group.command(
        name='first_message',
        description=(
            'Gets the first message sent by specified user in the current channel.'
        ),
    )
    @app_commands.guild_only()
    @app_commands.describe(member='Member to get first message for.')
    async def get_first_user_message(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None or interaction.guild is None:
            return await interaction.followup.send(
                'This command can only be used in guild channels.',
            )

        first_message = None

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None, oldest_first=True):
                if msg.author.id == member.id:
                    first_message = msg
                    break

        embed = Embed(title=f'First message by {member.display_name}', description='')

        if first_message and first_message.guild:
            # TODO: change to format_discord_message
            message_url = (
                f'https://discord.com/channels/'
                f'{first_message.guild.id}/'
                f'{first_message.channel.id}/'
                f'{first_message.id}'
            )

            embed.description = (
                f'[{first_message.created_at:%Y-%m-%d %H:%M:%S}]'
                f'({message_url}): {first_message.content}'
            )
            embed.color = Color.blue()
        else:
            embed.description = (
                f'No messages found by {member.display_name} in this channel.'
            )
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)

    @cached(60)
    @group.command(
        name='latest_message',
        description=(
            'Gets the latest message sent by specified user in the current channel.'
        ),
    )
    @app_commands.guild_only()
    @app_commands.describe(member='Member to get latest message for.')
    async def get_latest_user_message(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None or interaction.guild is None:
            return await interaction.followup.send(
                'This command can only be used in guild channels.',
            )

        latest_message = None

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=1):
                if msg.author.id == member.id:
                    latest_message = msg
                    break

        embed = Embed(title=f'Latest message by {member.display_name}', description='')

        if latest_message and latest_message.guild:
            # TODO: change to format_discord_message
            message_url = (
                f'https://discord.com/channels/'
                f'{latest_message.guild.id}/'
                f'{latest_message.channel.id}/'
                f'{latest_message.id}'
            )

            embed.description = (
                f'[{latest_message.created_at:%Y-%m-%d %H:%M:%S}]'
                f'({message_url}): {latest_message.content}'
            )
            embed.color = Color.blue()
        else:
            embed.description = (
                f'No messages found by {member.display_name} in this channel.'
            )
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)

    @cached(60)
    @group.command(
        name='random_message',
        description=(
            'Gets a random message sent by specified user in the current channel.'
        ),
    )
    @app_commands.guild_only()
    @app_commands.describe(member='Member to get random message for.')
    async def get_random_user_message(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None:
            return await interaction.followup.send(
                'This command can only be used in guild channels.',
            )

        user_messages = []

        if isinstance(interaction.channel, TextChannel):
            user_messages.extend(
                [
                    msg
                    async for msg in interaction.channel.history(limit=None)
                    if msg.author.id == member.id
                ]
            )

        embed = Embed(title=f'Random message by {member.display_name}', description='')

        if user_messages:
            random_message = random.choice(user_messages)
            # TODO: change to format_discord_message
            message_url = (
                f'https://discord.com/channels/'
                f'{random_message.guild.id}/'
                f'{random_message.channel.id}/'
                f'{random_message.id}'
            )

            embed.description = (
                f'[{random_message.created_at:%Y-%m-%d %H:%M:%S}]'
                f'({message_url}): {random_message.content}'
            )
            embed.color = Color.blue()
        else:
            embed.description = (
                f'No messages found by {member.display_name} in this channel.'
            )
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)

    @group.command(name='is_pepo', description='check if this dude is pepo')
    @app_commands.guild_only()
    async def is_pepo(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        e = Embed(title='Pepo Detector')

        if member.id == 1100132559851098163:
            e.description = f'Yes, <@{member.id}> is pepo.'
        else:
            e.description = f'No, <@{member.id}> is not pepo.'

        return await interaction.followup.send(embed=e)

    @cached(120 * 4)
    @group.command(name='hash_value', description="Get user's hash code.")
    @app_commands.guild_only()
    async def get_user_hash(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        e = Embed(title='User Hash Code', description=f'`{hash(member)}`')
        return await interaction.followup.send(embed=e)


async def setup(bot):
    await bot.add_cog(UserCog(bot))
