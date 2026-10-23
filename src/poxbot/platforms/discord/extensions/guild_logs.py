from datetime import UTC, datetime
from typing import TYPE_CHECKING

from discord import (
    AllowedMentions,
    Color,
    Embed,
    Forbidden,
    Guild,
    HTTPException,
    Interaction,
    Member,
    Message,
    NotFound,
    RawBulkMessageDeleteEvent,
    RawMessageDeleteEvent,
    Role,
    TextChannel,
    User,
    VoiceState,
    app_commands,
)
from discord.abc import GuildChannel
from discord.ext import commands

from ....infrastructure.logger import get_logger
from ....persistence.models.guild_settings_v2 import GuildConfigV2

if TYPE_CHECKING:
    from ....application import PoxBot


class GuildLogsCog(commands.Cog):
    group = app_commands.Group(
        name='logs',
        description="Configure this server's audit log channel",
        guild_only=True,
    )

    def __init__(self, bot: 'PoxBot') -> None:
        self.bot = bot
        self.logger = get_logger(__name__, prefix='GuildLogs')

    @staticmethod
    def _clip(value: str | None, limit: int = 1024) -> str:
        text = value or '(empty)'
        if len(text) <= limit:
            return text
        return f'{text[: limit - 3]}...'

    async def _get_config(self, guild_id: int) -> GuildConfigV2 | None:
        database = self.bot.database.guild
        if database is None:
            return None
        try:
            return await database.get_config(guild_id)
        except Exception:
            self.logger.exception(
                'Could not load log configuration for guild %s',
                guild_id,
            )
            return None

    async def _resolve_log_channel(self, guild_id: int) -> TextChannel | None:
        config = await self._get_config(guild_id)
        if config is None or not config.logs.enabled or config.logs.channel_id is None:
            return None

        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(config.logs.channel_id) if guild else None
        if channel is None:
            channel = self.bot.get_channel(config.logs.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(config.logs.channel_id)
            except (Forbidden, NotFound):
                return None
            except HTTPException:
                self.logger.exception(
                    'Could not fetch log channel %s for guild %s',
                    config.logs.channel_id,
                    guild_id,
                )
                return None

        if not isinstance(channel, TextChannel) or channel.guild.id != guild_id:
            self.logger.warning(
                'Configured log channel %s is unavailable or is not a text channel '
                'in guild %s',
                config.logs.channel_id,
                guild_id,
            )
            return None
        return channel

    async def _configured_log_channel_id(self, guild_id: int) -> int | None:
        config = await self._get_config(guild_id)
        if config is None or not config.logs.enabled:
            return None
        return config.logs.channel_id

    async def _send_embed(self, channel: TextChannel, embed: Embed) -> None:
        try:
            await channel.send(
                embed=embed,
                allowed_mentions=AllowedMentions.none(),
            )
        except (Forbidden, NotFound) as error:
            self.logger.warning(
                'Could not send audit log to channel %s: %s',
                channel.id,
                error,
            )
        except HTTPException:
            self.logger.exception(
                'Failed to send audit log to channel %s',
                channel.id,
            )
        except Exception:
            self.logger.exception(
                'Unexpected error while sending audit log to channel %s',
                channel.id,
            )

    async def log_event(
        self,
        guild: Guild,
        *,
        title: str,
        description: str,
        fields: list[tuple[str, str]] | None = None,
        color: Color | None = None,
    ) -> None:
        channel = await self._resolve_log_channel(guild.id)
        if channel is None:
            return

        embed = Embed(
            title=self._clip(title, 256),
            description=self._clip(description, 4096),
            color=color or Color.blurple(),
            timestamp=datetime.now(UTC),
        )
        for name, value in fields or []:
            embed.add_field(
                name=self._clip(name, 256),
                value=self._clip(value),
                inline=False,
            )
        await self._send_embed(channel, embed)

    async def _ignore_message_channel(self, guild_id: int, channel_id: int) -> bool:
        return await self._configured_log_channel_id(guild_id) == channel_id

    @group.command(
        name='channel',
        description='Set the channel for server-wide audit logs',
    )
    @app_commands.describe(channel='The text channel where audit logs are sent')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(
        self,
        interaction: Interaction,
        channel: TextChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None or self.bot.database.guild is None:
            await interaction.followup.send(
                'The guild database is unavailable.',
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me
        if bot_member is None:
            await interaction.followup.send(
                'I could not resolve my member in this server.',
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(bot_member)
        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.followup.send(
                'I need View Channel, Send Messages, and Embed Links permissions '
                'in that channel.',
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id
        database = self.bot.database.guild
        execution_time = datetime.now(UTC).timestamp()

        def configure_logs(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            config.logs.channel_id = channel.id
            config.logs.enabled = True
            config.logs.last_executor = interaction.user.id
            config.logs.last_execution = execution_time
            return True, None

        await database.mutate_config(guild_id, configure_logs)

        embed = Embed(
            title='Server audit logging configured',
            description=f'Server events will be logged in {channel.mention}.',
            color=Color.green(),
            timestamp=datetime.now(UTC),
        )
        embed.add_field(
            name='Changed by',
            value=f'{interaction.user} (`{interaction.user.id}`)',
            inline=False,
        )
        await self._send_embed(channel, embed)
        await interaction.followup.send(
            f'Server-wide audit logs will be sent to {channel.mention}.',
            ephemeral=True,
        )

    @group.command(
        name='disable',
        description='Disable server-wide audit logging',
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def disable(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None or self.bot.database.guild is None:
            await interaction.followup.send(
                'The guild database is unavailable.',
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id
        database = self.bot.database.guild
        channel = await self._resolve_log_channel(guild_id)

        if channel is not None:
            embed = Embed(
                title='Server audit logging disabled',
                description='A server manager disabled audit logging.',
                color=Color.dark_grey(),
                timestamp=datetime.now(UTC),
            )
            embed.add_field(
                name='Changed by',
                value=f'{interaction.user} (`{interaction.user.id}`)',
                inline=False,
            )
            await self._send_embed(channel, embed)

        execution_time = datetime.now(UTC).timestamp()

        def disable_logs(
            config: GuildConfigV2,
        ) -> tuple[bool, str | None]:
            config.logs.enabled = False
            config.logs.last_executor = interaction.user.id
            config.logs.last_execution = execution_time
            return True, None

        await database.mutate_config(guild_id, disable_logs)

        await interaction.followup.send(
            'Server-wide audit logging is disabled.',
            ephemeral=True,
        )

    @group.command(
        name='status',
        description='Show the server-wide audit log configuration',
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None or self.bot.database.guild is None:
            await interaction.followup.send(
                'The guild database is unavailable.',
                ephemeral=True,
            )
            return

        config = await self.bot.database.guild.get_config(interaction.guild.id)
        channel_id = config.logs.channel_id
        channel_text = (
            f'<#{channel_id}>' if channel_id is not None else 'Not configured'
        )
        status_text = (
            'Enabled' if config.logs.enabled and channel_id is not None else 'Disabled'
        )
        await interaction.followup.send(
            f'**Audit logging:** {status_text}\n**Channel:** {channel_text}',
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        if before.guild is None or before.author.bot or before.content == after.content:
            return
        if await self._ignore_message_channel(before.guild.id, before.channel.id):
            return
        await self.log_event(
            before.guild,
            title='Message edited',
            description=f'Message [jump link]({after.jump_url}) was edited.',
            color=Color.orange(),
            fields=[
                ('Author', f'{before.author} (`{before.author.id}`)'),
                ('Channel', f'<#{before.channel.id}>'),
                ('Before', self._clip(before.content)),
                ('After', self._clip(after.content)),
            ],
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent) -> None:
        if payload.guild_id is None:
            return
        if await self._ignore_message_channel(payload.guild_id, payload.channel_id):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        message = payload.cached_message
        if message is not None and message.author.bot:
            return

        fields = [
            ('Message ID', str(payload.message_id)),
            ('Channel', f'<#{payload.channel_id}>'),
        ]
        if message is not None:
            fields.extend(
                [
                    ('Author', f'{message.author} (`{message.author.id}`)'),
                    ('Content', self._clip(message.content)),
                ]
            )
        else:
            fields.append(
                (
                    'Content',
                    'The message was not cached; content is unavailable.',
                )
            )

        await self.log_event(
            guild,
            title='Message deleted',
            description='A message was deleted.',
            fields=fields,
            color=Color.red(),
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self,
        payload: RawBulkMessageDeleteEvent,
    ) -> None:
        if payload.guild_id is None:
            return
        if await self._ignore_message_channel(payload.guild_id, payload.channel_id):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        cached_messages = list(payload.cached_messages)
        if cached_messages and all(message.author.bot for message in cached_messages):
            return
        message_ids = ', '.join(
            str(message_id) for message_id in sorted(payload.message_ids)[:20]
        )
        if len(payload.message_ids) > 20:
            message_ids += f', … (+{len(payload.message_ids) - 20} more)'
        await self.log_event(
            guild,
            title='Messages bulk deleted',
            description=f'{len(payload.message_ids)} messages were bulk deleted.',
            fields=[
                ('Channel', f'<#{payload.channel_id}>'),
                ('Message IDs', message_ids or 'Unavailable'),
            ],
            color=Color.red(),
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        await self.log_event(
            member.guild,
            title='Member joined',
            description=f'{member.mention} joined the server.',
            color=Color.green(),
            fields=[
                ('User', f'{member} (`{member.id}`)'),
                (
                    'Account created',
                    member.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                ),
            ],
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member) -> None:
        await self.log_event(
            member.guild,
            title='Member left',
            description=f'{member} left or was removed from the server.',
            color=Color.dark_grey(),
            fields=[('User ID', str(member.id))],
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member) -> None:
        fields: list[tuple[str, str]] = []
        if before.nick != after.nick:
            fields.append(('Nickname before', before.nick or '(none)'))
            fields.append(('Nickname after', after.nick or '(none)'))

        before_roles = {
            role.id: role for role in before.roles if role != before.guild.default_role
        }
        after_roles = {
            role.id: role for role in after.roles if role != after.guild.default_role
        }
        added = [
            role.mention
            for role_id, role in after_roles.items()
            if role_id not in before_roles
        ]
        removed = [
            role.mention
            for role_id, role in before_roles.items()
            if role_id not in after_roles
        ]
        if added:
            fields.append(('Roles added', ', '.join(added)))
        if removed:
            fields.append(('Roles removed', ', '.join(removed)))
        if before.timed_out_until != after.timed_out_until:
            fields.append(('Timeout before', str(before.timed_out_until or 'None')))
            fields.append(('Timeout after', str(after.timed_out_until or 'None')))

        if not fields:
            return
        await self.log_event(
            after.guild,
            title='Member updated',
            description=f'{after} (`{after.id}`) had server settings changed.',
            fields=fields,
            color=Color.orange(),
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: Guild, user: User) -> None:
        await self.log_event(
            guild,
            title='Member banned',
            description=f'{user} (`{user.id}`) was banned.',
            color=Color.red(),
            fields=[('User ID', str(user.id))],
        )

    @commands.Cog.listener()
    async def on_member_unban(self, guild: Guild, user: User) -> None:
        await self.log_event(
            guild,
            title='Member unbanned',
            description=f'{user} (`{user.id}`) was unbanned.',
            color=Color.green(),
            fields=[('User ID', str(user.id))],
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: GuildChannel) -> None:
        await self.log_event(
            channel.guild,
            title='Channel created',
            description=f'Channel **{channel.name}** was created.',
            color=Color.green(),
            fields=[('Channel ID', str(channel.id)), ('Type', str(channel.type))],
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: GuildChannel) -> None:
        await self.log_event(
            channel.guild,
            title='Channel deleted',
            description=f'Channel **{channel.name}** was deleted.',
            color=Color.red(),
            fields=[('Channel ID', str(channel.id)), ('Type', str(channel.type))],
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: GuildChannel,
        after: GuildChannel,
    ) -> None:
        changes: list[tuple[str, str]] = []
        if before.name != after.name:
            changes.extend([('Name before', before.name), ('Name after', after.name)])
        before_topic = getattr(before, 'topic', None)
        after_topic = getattr(after, 'topic', None)
        if before_topic != after_topic:
            changes.extend(
                [
                    ('Topic before', self._clip(before_topic)),
                    ('Topic after', self._clip(after_topic)),
                ]
            )
        if not changes:
            return
        await self.log_event(
            after.guild,
            title='Channel updated',
            description=f'Channel <#{after.id}> was updated.',
            fields=changes,
            color=Color.orange(),
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: Role) -> None:
        await self.log_event(
            role.guild,
            title='Role created',
            description=f'Role **{role.name}** was created.',
            color=Color.green(),
            fields=[('Role ID', str(role.id))],
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: Role) -> None:
        await self.log_event(
            role.guild,
            title='Role deleted',
            description=f'Role **{role.name}** was deleted.',
            color=Color.red(),
            fields=[('Role ID', str(role.id))],
        )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: Role, after: Role) -> None:
        changes: list[tuple[str, str]] = []
        if before.name != after.name:
            changes.extend([('Name before', before.name), ('Name after', after.name)])
        if before.permissions != after.permissions:
            changes.extend(
                [
                    ('Permissions before', str(before.permissions.value)),
                    ('Permissions after', str(after.permissions.value)),
                ]
            )
        if before.color != after.color:
            changes.extend(
                [
                    ('Color before', str(before.color)),
                    ('Color after', str(after.color)),
                ]
            )
        if not changes:
            return
        await self.log_event(
            after.guild,
            title='Role updated',
            description=f'Role <@&{after.id}> was updated.',
            fields=changes,
            color=Color.orange(),
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: Member,
        before: VoiceState,
        after: VoiceState,
    ) -> None:
        if before.channel == after.channel:
            return
        if before.channel is None and after.channel is not None:
            title = 'Member joined voice channel'
            description = f'{member} joined **{after.channel.name}**.'
            color = Color.green()
        elif before.channel is not None and after.channel is None:
            title = 'Member left voice channel'
            description = f'{member} left **{before.channel.name}**.'
            color = Color.dark_grey()
        else:
            title = 'Member moved voice channels'
            before_name = before.channel.name if before.channel else 'Unknown'
            after_name = after.channel.name if after.channel else 'Unknown'
            description = f'{member} moved from **{before_name}** to **{after_name}**.'
            color = Color.orange()
        await self.log_event(
            member.guild,
            title=title,
            description=description,
            color=color,
            fields=[('User ID', str(member.id))],
        )


async def setup(bot: 'PoxBot') -> None:
    await bot.add_cog(GuildLogsCog(bot))
