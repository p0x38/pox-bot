from aiocache import cached
from discord import (
    AuditLogAction,
    ButtonStyle,
    Color,
    Embed,
    Guild,
    Interaction,
    SelectOption,
    app_commands,
    ui,
)
from discord.app_commands import Choice
from discord.ext import commands

from ....application import PoxBot
from ....shared.utils.pagination_view import PaginationView


class LoggingView(ui.View):
    def __init__(self, data_dict, user, default, translator, locale):
        super().__init__(timeout=60)
        self.data_dict = data_dict
        self.user = user
        self.translator = translator
        self.locale = locale
        self.categories = list(data_dict.keys())

        if isinstance(default, str):
            self.current_category = default
        else:
            self.current_category = self.categories[default]

        self.current_page = 0
        self.items_per_page = 10

    def get_total_pages(self):
        data_len = len(self.data_dict[self.current_category])
        return max(1, (data_len - 1) // self.items_per_page + 1)

    def create_embed(self):
        category_data = self.data_dict[self.current_category]
        total_pages = self.get_total_pages()

        embed = Embed(
            title=self.translator.T(
                'command.guild.logs.embeds.default.title',
                self.locale,
                category=self.translator.T(
                    f'command.guild.logs.categories.{self.current_category}',
                    self.locale,
                ),
            ),
        )

        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = category_data[start:end]

        if not page_items:
            embed.description = 'No history found for this category.'
        else:
            description = ''
            for i, entry in enumerate(page_items, start + 1):
                description += f'**{i}.** {entry}\n'
            embed.description = description

        category_label = self.translator.T(
            f'command.guild.logs.categories.{self.current_category}',
            self.locale,
        )
        embed.set_footer(
            text=f'Page {self.current_page + 1}/{total_pages} | {category_label}',
        )
        return embed

    @ui.button(label='Prev', style=ButtonStyle.gray)
    async def previous_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self,
            )
        else:
            await interaction.response.send_message(
                "You're on the first page.",
                ephemeral=True,
            )

    @ui.button(label='Next', style=ButtonStyle.gray)
    async def next_page(self, interaction: Interaction, button: ui.Button):
        total_pages = self.get_total_pages()
        if self.current_page < total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self,
            )
        else:
            await interaction.response.send_message(
                "You're on the last page 3:",
                ephemeral=True,
            )

    @ui.select(
        placeholder='Select history type',
        options=[
            SelectOption(label='Kicks', value='kicks', emoji='👟'),
            SelectOption(label='Bans', value='bans', emoji='🔨'),
            SelectOption(label='Timeouts', value='timeouts', emoji='🚫'),
        ],
    )
    async def select_category(self, interaction: Interaction, select: ui.Select):
        self.current_category = select.values[0]
        self.current_page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                'This menu belongs to another user.',
                ephemeral=True,
            )
            return False
        return True


class GuildCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    async def _send_paginated_lines(
            self,
            interaction: Interaction,
            *,
            title: str,
            lines: list[str],
            page_size: int = 20,
    ) -> None:
        """Send text items through the shared Components V2 paginator."""
        if page_size < 1:
            raise ValueError('page_size must be greater than zero.')
        if not lines:
            raise ValueError('lines must contain at least one item.')

        total = len(lines)
        pages: list[str] = []

        for offset in range(0, total, page_size):
            page_lines = lines[offset : offset + page_size]
            last_item = offset + len(page_lines)

            pages.append(
                f'## {title}\n\n'
                f'{"\n".join(page_lines)}\n\n'
                f'-# {offset + 1}–{last_item} / {total}'  # ruff: ignore[ambiguous-unicode-character-string]
            )

        view = PaginationView(
            pages,
            owner_id=interaction.user.id,
            timeout=180,
        )
        await view.send(interaction)

    checker_group = app_commands.Group(
        name='guild',
        description=app_commands.locale_str('command.guild.description'),
    )

    @checker_group.command(
        name='info',
        description=app_commands.locale_str('command.guild.info.description'),
    )
    @app_commands.guild_only()
    async def check_server_info(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)

        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        if guild:
            temp1 = {
                'server_description': (
                    guild.description
                    if guild.description
                    else self.bot.internal_translator.T(
                        'command.guild.info.placeholders.no_description',
                        str(loc),
                    )
                ),
                'server_locale': guild.preferred_locale.language_code,
                'server_owner': (
                    guild.owner.mention
                    if guild.owner
                    else self.bot.internal_translator.T('text.unknown', str(loc))
                ),
                'server_members': self.bot.internal_translator.T(
                    'command.guild.info.placeholders.members',
                    str(loc),
                    {
                        'count': (
                            guild.member_count
                            if guild.member_count is not None
                            else len(guild.members)
                        ),
                    },
                ),
                'server_creation': guild.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'server_shard': (
                    guild.shard_id
                    if guild.shard_id is not None
                    else 'N/A'
                ),
                'server_large': self.bot.internal_translator.T(
                    'text.boolean.true' if guild.large else 'text.boolean.false',
                    str(loc),
                ),
                'server_roles': f'{len(guild.roles):,} roles',
                'server_emojis': f'{len(guild.emojis):,} emojis',
                'server_stickers': f'{len(guild.stickers):,} stickers',
                'server_level': f'Level {guild.premium_tier}',
                'server_boosts': (
                    f'{guild.premium_subscription_count:,} boosts'
                    if guild.premium_subscription_count is not None
                    else self.bot.internal_translator.T(
                        'text.unknown',
                        str(loc),
                    )
                ),
                'server_channels': f'{len(guild.channels):,} channels',
                'server_categories': f'{len(guild.categories):,} categories',
                'server_chunked': f'{"Yes" if guild.chunked else "No"}',
            }

            temp1 = self.bot.internal_translator.translate_map(temp1, str(loc))
            e = Embed(
                title=self.bot.internal_translator.T(
                    'command.guild.info.embeds.default.title',
                    loc,
                    guild_name=guild.name,
                ),
                color=Color.blue(),
            )
            e.set_footer(text=f'Guild ID: {guild.id}')
            e.set_author(
                name=f'By {guild.owner.name if guild.owner else "Unknown"}',
                icon_url=(
                    guild.owner.avatar.url
                    if guild.owner and guild.owner.avatar
                    else None
                ),
            )

            for key, value in temp1.items():
                e.add_field(name=key, value=value, inline=True)

            if guild.icon:
                e.set_thumbnail(url=guild.icon.url)
            return await interaction.followup.send(embed=e)
        return await interaction.followup.send('Guild not found.')

    @checker_group.command(
        name='kickmembers',
        description=app_commands.locale_str('command.guild.kickmembers.description'),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def kick_all_realusers(self, interaction: Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        if guild:
            for member in guild.members:
                try:
                    if member.bot:
                        continue
                    await member.kick(reason='Kicked via command')
                except Exception:
                    self.bot.logger.exception('Exception raised')
            return await interaction.followup.send('kicked')
        return await interaction.followup.send('Guild not found.')

    @checker_group.command(
        name='listmembers',
        description=app_commands.locale_str('command.guild.listmembers.description'),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(
        sort_by=[
            Choice(
                name=app_commands.locale_str('command.guild.listmembers.parameters.id'),
                value='id',
            ),
            Choice(
                name=app_commands.locale_str(
                    'command.guild.listmembers.parameters.username'
                ),
                value='username',
            ),
            Choice(
                name=app_commands.locale_str(
                    'command.guild.listmembers.parameters.created_at'
                ),
                value='created_at',
            ),
            Choice(
                name=app_commands.locale_str(
                    'command.guild.listmembers.parameters.joined_at'
                ),
                value='joined_at',
            ),
        ],
    )
    async def list_all_realusers(
        self,
        interaction: Interaction,
        sort_by: str | None = None,
    ) -> None:
        guild = interaction.guild
        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer(thinking=True)

        if guild is None:
            embed = Embed(
                title=self.bot.internal_translator.T(
                    'error.embeds.guild_only.title',
                    loc,
                ),
                description=self.bot.internal_translator.T(
                    'error.embeds.guild_only.description',
                    loc,
                ),
                color=Color.red(),
            )
            await interaction.edit_original_response(embed=embed)
            return

        members = [member for member in guild.members if not member.bot]

        if sort_by == 'id':
            members.sort(key=lambda member: member.id)
        elif sort_by == 'username':
            members.sort(key=lambda member: member.name.casefold())
        elif sort_by == 'created_at':
            members.sort(key=lambda member: member.created_at)
        elif sort_by == 'joined_at':
            members.sort(
                key=lambda member: (
                    member.joined_at is None,
                    (
                        member.joined_at.timestamp()
                        if member.joined_at is not None
                        else 0.0
                    ),
                ),
            )

        if not members:
            embed = Embed(
                description=self.bot.internal_translator.T(
                    'error.embeds.no_members.description',
                    loc,
                ),
                title=self.bot.internal_translator.T(
                    'error.embeds.no_members.title',
                    loc,
                ),
                color=Color.red(),
            )
            await interaction.edit_original_response(embed=embed)
            return

        page_title = self.bot.internal_translator.T(
            'command.guild.listmembers.embeds.default.title',
            loc,
            guild_name=guild.name,
        )
        lines = [
            f'`{index}.` {member.mention}'
            for index, member in enumerate(members, start=1)
        ]

        await self._send_paginated_lines(
            interaction,
            title=page_title,
            lines=lines,
        )

    @cached(300)
    @checker_group.command(
        name='nsfw_level',
        description=app_commands.locale_str('command.guild.nsfw_level.description'),
    )
    @app_commands.guild_only()
    async def check_nsfw_level(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(thinking=True)
        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.guild.nsfw_level.embeds.default.title',
                loc,
            ),
            description='',
        )
        if interaction.guild:
            embed.description = self.bot.internal_translator.T(
                f'text.NSFWLevel.{interaction.guild.nsfw_level.name}',
                loc,
            )
        else:
            return await interaction.followup.send('Guild not found.')

        return await interaction.followup.send(embed=embed)

    @cached(300)
    @checker_group.command(
        name='icon',
        description=app_commands.locale_str('command.guild.icon.description'),
    )
    @app_commands.guild_only()
    async def get_server_icon(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(thinking=True)
        if interaction.guild and interaction.guild.icon:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'command.guild.icon.embeds.default.title',
                        loc,
                    ),
                ).set_image(url=interaction.guild.icon.url),
            )
        return await interaction.followup.send('No icon found.')

    @checker_group.command(
        name='count',
        description=app_commands.locale_str('command.guild.count.description'),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def get_member(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.generic.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.custom.guild_only',
                        loc,
                    ),
                    color=Color.red(),
                ),
            )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.guild.count.embeds.default.title',
                loc,
                guild_name=interaction.guild.name,
            ),
            description='',
            color=Color.green(),
        )

        total_members = 0
        bots = 0
        nitros = 0

        for member in interaction.guild.members:
            total_members += 1
            if member.bot:
                bots += 1
            if member.premium_since:
                nitros += 1

        lines = []

        if total_members > 0:
            lines.append(f'Total: {total_members}')
            lines.append(f'Bot ratio: {round((bots / total_members) * 100)}%')
            lines.append(f'Nitro users: {nitros}')

        embed.description = '\n'.join(lines)

        return await interaction.followup.send(embed=embed)

    @cached(60)
    @checker_group.command(
        name='members_list',
        description=app_commands.locale_str('command.guild.members_list.description'),
    )
    @app_commands.guild_only()
    async def get_members(
        self,
        interaction: Interaction,
        include_bot: bool = False,
        include_member: bool = True,
    ):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.generic.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.custom.guild_only',
                        loc,
                    ),
                    color=Color.red(),
                ),
            )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.guild.members_list.embeds.default.title',
                loc,
                guild_name=interaction.guild.name,
            ),
            description='',
            color=Color.green(),
        )

        members: list[str] = []

        if not include_bot and not include_member:
            embed.color = Color.red()
            embed.description = 'You cannot exclude both!'
            return await interaction.followup.send(embed=embed)

        for member in sorted(
            interaction.guild.members,
            key=lambda r: r.top_role.position,
            reverse=True,
        ):
            if include_bot and member.bot:
                members.append(f'{member.top_role.mention}: {member.mention}')

            if include_member and not member.bot:
                members.append(f'{member.top_role.mention}: {member.mention}')

        if len(members) == 0:
            embed.color = Color.purple()
            embed.description = 'Not found'
            return await interaction.followup.send(embed=embed)

        await self._send_paginated_lines(
            interaction,
            title=embed.title or '',
            lines=members,
        )

    @cached(60)
    @checker_group.command(
        name='search_members',
        description=app_commands.locale_str('command.guild.search_members.description'),
    )
    @app_commands.guild_install()
    async def search_members(self, interaction: Interaction, keyword: str):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.generic.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.custom.guild_only',
                        loc,
                    ),
                    color=Color.red(),
                ),
            )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.guild.search_members.embeds.default.title',
                loc,
                keyword=keyword,
                guild_name=interaction.guild.name,
            ),
            description='',
            color=Color.green(),
        )

        result = [
            member.mention
            for member in interaction.guild.members
            if member.name.casefold().startswith(keyword.casefold())
        ]

        if len(result) == 0:
            embed.color = Color.purple()
            embed.description = f'User starts with {keyword} not found from this guild.'
            return await interaction.followup.send(embed=embed)

        await self._send_paginated_lines(
            interaction,
            title=embed.title or '',
            lines=result,
        )

    @cached(60)
    @checker_group.command(
        name='role_list',
        description=app_commands.locale_str('command.guild.role_list.description'),
    )
    @app_commands.guild_install()
    async def get_roles(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.generic.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.custom.guild_only',
                        loc,
                    ),
                    color=Color.red(),
                ),
            )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.guild.role_list.embeds.default.title',
                loc,
                guild_name=interaction.guild.name,
            ),
            color=Color.green(),
        )

        lines = [
            role.mention
            for role in sorted(
                interaction.guild.roles,
                key=lambda role: role.position,
                reverse=True,
            )
            if not role.managed and role.name != '@everyone'
        ]

        if not lines:
            return await interaction.followup.send(embed=embed)

        await self._send_paginated_lines(
            interaction,
            title=embed.title or '',
            lines=lines,
        )

    @cached(60)
    async def fetch_guild_history(self, guild: Guild):
        history = {'kicks': [], 'bans': [], 'timeouts': []}

        async for entry in guild.audit_logs(limit=128):
            target = entry.target
            user = entry.user
            reason = entry.reason or 'No reason provided'

            if entry.action == AuditLogAction.kick:
                history['kicks'].append(
                    f'**Target:** {target} | **Mod:** {user}\n- *Reason: {reason}*',
                )
            elif entry.action == AuditLogAction.ban:
                history['bans'].append(
                    f'**Target:** {target} | **Mod:** {user}\n- *Reason: {reason}*',
                )
            elif (
                entry.action == AuditLogAction.member_update
                and hasattr(entry.after, 'communication_disabled_until')
                and entry.after.communication_disabled_until
            ):
                until = entry.after.communication_disabled_until.strftime(
                    '%Y-%m-%d %H:%M',
                )
                history['timeouts'].append(
                    f'**Target:** {target} | **Until:** {until}\n- *Reason: {reason}*',
                )

        return history

    @checker_group.command(
        name='logs',
        description=app_commands.locale_str('command.guild.logs.description'),
    )
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def show_history(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        if not interaction.guild:
            return await interaction.response.send_message('Must be in guild.')

        await interaction.response.defer(thinking=True)
        history_data = await self.fetch_guild_history(interaction.guild)

        view = LoggingView(
            history_data,
            interaction.user,
            'kicks',
            self.bot.internal_translator,
            loc,
        )
        await interaction.followup.send(embed=view.create_embed(), view=view)


async def setup(bot):
    await bot.add_cog(GuildCog(bot))
