from collections.abc import Callable
from datetime import datetime

from discord import (
    AllowedMentions,
    Color,
    Embed,
    HTTPException,
    Interaction,
    Member,
    TextChannel,
    User,
    app_commands,
)
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....dsl.template_parser import TemplateError, render_template, validate_template
from ....persistence.models.guild_settings_v2 import GuildConfigV2

_WelcomeMutation = Callable[
    [GuildConfigV2],
    tuple[bool, str | None],
]


class WelcomeCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

    group = app_commands.Group(
        name='welcome',
        description=app_commands.locale_str('command.welcome.description'),
    )

    @staticmethod
    def format_user_as_text(user: User | Member) -> str:
        if user.name == user.display_name:
            return user.display_name

        return f'{user.display_name} ({user.name})'

    @staticmethod
    def format_timestamp(value: datetime | None) -> str:
        if value is None:
            return 'Unknown'

        return value.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def build_template_context(member: Member) -> dict[str, object]:
        guild = member.guild
        member_count = guild.member_count

        if member_count is None:
            member_count = len(guild.members)

        return {
            'user': {
                'mention': member.mention,
                'name': member.name,
                'display': member.display_name,
                'avatar': member.display_avatar.url,
            },
            'server': {
                'name': guild.name,
                'members': member_count,
            },
        }

    def build_embed(self, member: Member, *, leaving: bool) -> Embed:
        rows: list[tuple[str, str]] = [
            ('user_id', str(member.id)),
            ('user_name', self.format_user_as_text(member)),
            ('user_bot', 'Yes' if member.bot else 'No'),
            ('user_creation', self.format_timestamp(member.created_at)),
        ]

        if leaving:
            rows.append(
                ('user_join', self.format_timestamp(member.joined_at)),
            )

        embed = Embed()

        for name, value in rows:
            embed.add_field(name=name, value=value, inline=False)

        return embed

    async def send_message(
        self,
        member: Member,
        *,
        leaving: bool = False,
    ) -> None:
        database = self.bot.database.guild

        if database is None:
            return

        guild_settings = await database.get_config(member.guild.id)
        welcome = guild_settings.welcome

        if not welcome.enabled:
            return

        if leaving:
            channel_id = welcome.channels.leave or welcome.channels.join
            template = welcome.data.leave_message
        else:
            channel_id = welcome.channels.join
            template = welcome.data.welcome_message

        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)

        if not isinstance(channel, TextChannel):
            return

        try:
            if template and template.strip():
                try:
                    content = render_template(
                        template,
                        self.build_template_context(member),
                    )
                except TemplateError as exc:
                    self.bot.logger.error(
                        'Invalid %s template for guild %s: %s',
                        'leave' if leaving else 'welcome',
                        member.guild.id,
                        exc,
                    )
                else:
                    await channel.send(
                        content=content,
                        allowed_mentions=AllowedMentions(
                            users=[member],
                            roles=False,
                            everyone=False,
                            replied_user=False,
                        ),
                    )
                    return

            await channel.send(embed=self.build_embed(member, leaving=leaving))
        except Exception:
            self.bot.logger.exception(
                'Could not send %s message',
                'leave' if leaving else 'welcome',
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        await self.send_message(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member) -> None:
        await self.send_message(member, leaving=True)

    async def set_custom_message(
        self,
        interaction: Interaction,
        template: str | None,
        *,
        leaving: bool,
    ) -> None:
        locale = await self.bot.get_locale(interaction, prefer_guild=True)
        translator = self.bot.internal_translator

        if template is not None:
            try:
                if not template.strip():
                    raise TemplateError(
                        'Template cannot be empty. Omit it to reset the message.'
                    )

                validate_template(template)

            except TemplateError as exc:
                embed = Embed(
                    title=translator.T(
                        'command.welcome.template.embeds.invalid.title',
                        locale,
                    ),
                    description=translator.T(
                        'command.welcome.template.embeds.invalid.description',
                        locale,
                        {'error': str(exc)},
                    ),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                )

                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True,
                )
                return

        def mutation(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            if leaving:
                config.welcome.data.leave_message = template
            else:
                config.welcome.data.welcome_message = template

            return True, None

        command_key = 'leavemessage' if leaving else 'message'
        status_key = 'default' if template is not None else 'reset'

        await self.update_welcome_setting(
            interaction,
            mutation,
            title_key=(f'command.welcome.{command_key}.embeds.{status_key}.title'),
            description_key=(
                f'command.welcome.{command_key}.embeds.{status_key}.description'
            ),
        )

    async def get_context_error_embed(
        self,
        interaction: Interaction,
    ) -> Embed | None:
        locale = await self.bot.get_locale(interaction, prefer_guild=True)
        translator = self.bot.internal_translator

        if self.bot.database.guild is None:
            return Embed(
                title=translator.T(
                    'error.embeds.database_not_available.title',
                    locale,
                ),
                description=translator.T(
                    'error.embeds.database_not_available.description',
                    locale,
                ),
                timestamp=datetime.now(UTC),
                color=Color.red(),
            )

        if interaction.guild is None:
            return Embed(
                title=translator.T(
                    'error.embeds.guild_only.title',
                    locale,
                ),
                description=translator.T(
                    'error.embeds.guild_only.description',
                    locale,
                ),
                timestamp=datetime.now(UTC),
                color=Color.red(),
            )

        return None

    async def require_context(self, interaction: Interaction) -> bool:
        embed = await self.get_context_error_embed(interaction)

        if embed is None:
            return True

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

        return False

    async def interaction_check(self, interaction) -> bool:
        return await self.require_context(interaction)

    async def update_welcome_setting(
        self,
        interaction: Interaction,
        mutation: _WelcomeMutation,
        *,
        title_key: str,
        description_key: str,
        description_args: dict[str, str] | None = None,
    ) -> None:
        if not await self.require_context(interaction):
            return

        guild = interaction.guild
        database = self.bot.database.guild

        if guild is None or database is None:
            return

        await interaction.response.defer()

        await database.mutate_config(guild.id, mutation)

        locale = guild.preferred_locale
        translator = self.bot.internal_translator

        embed = Embed(
            title=translator.T(title_key, locale),
            description=translator.T(
                description_key,
                locale,
                description_args or {},
            ),
            color=Color.red(),
            timestamp=datetime.now(UTC),
        )

        await interaction.followup.send(embed=embed)

    @group.command(
        name='toggle',
        description=app_commands.locale_str('command.welcome.toggle.description'),
    )
    @app_commands.describe(
        enabled=app_commands.locale_str('command.welcome.toggle.parameters.enabled'),
    )
    async def toggle_welcome(
        self,
        interaction: Interaction,
        enabled: bool = False,
    ):
        def mutation(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            config.welcome.enabled = enabled
            return True, None

        await self.update_welcome_setting(
            interaction,
            mutation,
            title_key='command.welcome.toggle.embeds.default.title',
            description_key='command.welcome.toggle.embeds.default.description',
            description_args={
                'toggle': 'enabled' if enabled else 'disabled',
            },
        )

    @group.command(
        name='joinchannel',
        description=app_commands.locale_str('command.welcome.joinchannel.description'),
    )
    @app_commands.describe(
        channel=app_commands.locale_str(
            'command.welcome.joinchannel.parameters.channel',
        ),
    )
    async def set_joinchannel(
        self,
        interaction: Interaction,
        channel: TextChannel,
    ):
        def mutation(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            config.welcome.channels.join = channel.id
            return True, None

        await self.update_welcome_setting(
            interaction,
            mutation,
            title_key='command.welcome.joinchannel.embeds.default.title',
            description_key=('command.welcome.joinchannel.embeds.default.description'),
            description_args={'channel': channel.mention},
        )

    @group.command(
        name='leavechannel',
        description=app_commands.locale_str('command.welcome.leavechannel.description'),
    )
    @app_commands.describe(
        channel=app_commands.locale_str(
            'command.welcome.leavechannel.parameters.channel',
        ),
    )
    async def set_leavechannel(
        self,
        interaction: Interaction,
        channel: TextChannel,
    ):
        def mutation(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            config.welcome.channels.leave = channel.id
            return True, None

        await self.update_welcome_setting(
            interaction,
            mutation,
            title_key='command.welcome.leavechannel.embeds.default.title',
            description_key=('command.welcome.leavechannel.embeds.default.description'),
            description_args={'channel': channel.mention},
        )

    @group.command(
        name='set_join_message',
        description=app_commands.locale_str(
            'command.welcome.set_join_message.description',
        ),
    )
    @app_commands.describe(
        template=app_commands.locale_str(
            'command.welcome.set_join_message.parameters.template',
        ),
    )
    async def set_message(
        self,
        interaction: Interaction,
        template: str | None = None,
    ) -> None:
        await self.set_custom_message(
            interaction,
            template,
            leaving=False,
        )

    @group.command(
        name='set_leave_message',
        description=app_commands.locale_str(
            'command.welcome.set_leave_message.description',
        ),
    )
    @app_commands.describe(
        template=app_commands.locale_str(
            'command.welcome.set_leave_message.parameters.template',
        ),
    )
    async def set_leave_message(
        self,
        interaction: Interaction,
        template: str | None = None,
    ) -> None:
        await self.set_custom_message(
            interaction,
            template,
            leaving=True,
        )

    @group.command(
        name='test',
        description=app_commands.locale_str(
            'command.welcome.test.description',
        ),
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(
        message_type=[
            app_commands.Choice(name='Join message', value='join'),
            app_commands.Choice(name='Leave message', value='leave'),
        ],
    )
    async def test_message(
        self,
        interaction: Interaction,
        message_type: app_commands.Choice[str],
    ) -> None:
        if not await self.require_context(interaction):
            return

        guild = interaction.guild
        database = self.bot.database.guild

        if guild is None or database is None:
            return

        await interaction.response.defer(ephemeral=True)

        settings = await database.get_config(guild.id)
        welcome = settings.welcome
        leaving = message_type.value == 'leave'

        if leaving:
            channel_id = welcome.channels.leave or welcome.channels.join
            template = welcome.data.leave_message
        else:
            channel_id = welcome.channels.join
            template = welcome.data.welcome_message

        locale = guild.preferred_locale
        translator = self.bot.internal_translator

        if not channel_id:
            embed = Embed(
                title=translator.T(
                    'command.welcome.test.embeds.no_channel.title',
                    locale,
                ),
                description=translator.T(
                    'command.welcome.test.embeds.no_channel.description',
                    locale,
                ),
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        channel = self.bot.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except HTTPException:
                channel = None

        if not isinstance(channel, TextChannel):
            embed = Embed(
                title=translator.T(
                    'command.welcome.test.embeds.channel_unavailable.title',
                    locale,
                ),
                description=translator.T(
                    'command.welcome.test.embeds.channel_unavailable.description',
                    locale,
                ),
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            user = interaction.user

            if isinstance(user, Member):
                member = user
            else:
                member = await guild.fetch_member(user.id)

            allowed_mentions = AllowedMentions(
                users=[member],
                roles=False,
                everyone=False,
                replied_user=False,
            )

            if template and template.strip():
                content = render_template(
                    template,
                    self.build_template_context(member),
                )

                await channel.send(
                    content=content,
                    allowed_mentions=allowed_mentions,
                )
            else:
                await channel.send(
                    embed=self.build_embed(member, leaving=leaving),
                    allowed_mentions=AllowedMentions.none(),
                )

        except TemplateError as exc:
            embed = Embed(
                title=translator.T(
                    'command.welcome.template.embeds.invalid.title',
                    locale,
                ),
                description=translator.T(
                    'command.welcome.template.embeds.invalid.description',
                    locale,
                    {'error': str(exc)},
                ),
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        except HTTPException:
            self.bot.logger.exception(
                'Could not send welcome test message to channel %s',
                channel_id,
            )

            embed = Embed(
                title=translator.T(
                    'command.welcome.test.embeds.failed.title',
                    locale,
                ),
                description=translator.T(
                    'command.welcome.test.embeds.failed.description',
                    locale,
                ),
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = Embed(
            title=translator.T(
                'command.welcome.test.embeds.sent.title',
                locale,
            ),
            description=translator.T(
                'command.welcome.test.embeds.sent.description',
                locale,
                {'channel': channel.mention},
            ),
            color=Color.green(),
            timestamp=datetime.now(UTC),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: PoxBot):
    await bot.add_cog(WelcomeCog(bot))
