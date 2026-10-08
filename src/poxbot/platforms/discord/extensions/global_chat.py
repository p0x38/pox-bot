import asyncio
import re
import unicodedata
from time import perf_counter
from typing import Literal

import tldextract
from discord import (
    AllowedMentions,
    Color,
    Embed,
    Forbidden,
    HTTPException,
    Interaction,
    Message,
    NotFound,
    TextChannel,
    Webhook,
    app_commands,
)
from discord.ext import commands

from ....application import PoxBot
from ....features.moderation import (
    GlobalChatModerator,
    ModerationAction,
    ModerationResult,
    combine_results,
)
from ....features.moderation.manager import (
    MAX_IMAGE_BYTES,
    MAX_TOTAL_IMAGE_BYTES,
)
from ....features.moderation.normalization import normalize_text
from ....infrastructure.logger import get_logger
from ....persistence.models.guild_settings_v2 import (
    AntiSpamFilter,
    GlobalChatDeliveryType,
)
from ....persistence.models.pydantic.blacklisted_item import (
    BlacklistItem,
)
from ....services.spam import AntiSpamManager


class GlobalChatCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.logger = get_logger(__name__, prefix='GlobalChat')
        self.antispam_managers: dict[int, AntiSpamManager] = {}
        self.censored_words = [r'(?:https?://)?discord\.gg\/[a-zA-Z0-9]+']
        self.whitelisted_domains = bot.constants.whitelisted_domains
        self.blacklisted_domains = bot.constants.blacklisted_domains

        self.moderator = GlobalChatModerator(
            url_extractor=bot.resources.url_extrator,
            blacklisted_domains=self.blacklisted_domains,
        )
        self.webhook_cache: dict[int, Webhook] = {}

    async def cog_load(self):
        threat_data = await self.bot.resources.load_with_orjson_async(
            'global_chat_threats.json',
        )
        self.moderator.load_catalog(threat_data)

    def _record_counter(self, name: str, description: str, labels: dict[str, str]):
        if self.bot.metrics:
            self.bot.metrics.increment_counter(
                name=name,
                description=description,
                amount=1,
                labels=labels,
            )

    async def _get_or_create_webhook(self, channel: TextChannel) -> Webhook | None:
        if channel.id in self.webhook_cache:
            return self.webhook_cache[channel.id]

        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.user == self.bot.user:
                    self.webhook_cache[channel.id] = wh
                    return wh

            new_wh = await channel.create_webhook(
                name='p0x38bot_globalchat_webhook',
                reason='Create a webhook for sending global chat messages',
            )
            self.webhook_cache[channel.id] = new_wh
        except (Forbidden, HTTPException):
            return None
        else:
            return new_wh

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        db_manager = self.bot.database
        if message.author.bot or not message.guild or not db_manager.guild:
            return

        config = await db_manager.guild.get_config(message.guild.id)

        global_chat = config.global_chat
        if (
            not global_chat
            or not global_chat.enabled
            or message.channel.id != global_chat.channel_id
        ):
            return

        filtering = config.filtering
        antispam_setting = filtering.filters.get('anti_spam')

        if (
            filtering.enabled
            and antispam_setting
            and isinstance(antispam_setting, AntiSpamFilter)
            and antispam_setting.enabled
        ):
            if message.guild.id not in self.antispam_managers:
                self.antispam_managers[message.guild.id] = AntiSpamManager(
                    database_manager=db_manager,
                    time_window=antispam_setting.window_length,
                    max_messages_per_window=antispam_setting.messages_per_window,
                )

            manager = self.antispam_managers[message.guild.id]

            manager.time_window = antispam_setting.window_length
            manager.max_messages_per_window = antispam_setting.messages_per_window

            manager.record_message(message.author)

            if manager.is_spamming(message.author):
                self._record_counter(
                    name='bot_global_chat_messages_total',
                    description=(
                        'Total count of messages sent to the global chat system'
                    ),
                    labels={'guild_id': str(message.guild.id), 'status': 'spam'},
                )
                await self.handle_spam(message)
                return

        await self.broadcast_global_message(message)

    async def handle_spam(self, message: Message):
        try:
            await message.delete()
        except Forbidden:
            self.bot.logger.warning(
                'Missing permissions to delete message'
                'in guild {message.guild.id if message.guild else "Unknown"}',
            )
        except NotFound:
            pass

        embed = Embed(
            description=f"⚠️ {message.author.mention}, don't spam!",
            color=Color.red(),
        )
        await message.channel.send(embed=embed, delete_after=5.0)

    async def censor_urls(self, text: str):
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[\u200b-\u200f\uFEFF\u202a-\u202e]', '', text)

        found = (
            self.bot.resources.url_extrator.find_urls(
                text,
                only_unique=True,
                check_dns=False,
                get_indices=True,
                with_schema_only=False,
            )
            or []
        )

        for item in reversed(found):
            if isinstance(item, tuple) and len(item) == 2:
                url, (start, end) = item

                ext = tldextract.extract(url)
                domain = f'{ext.domain}.{ext.suffix}'

                if domain in self.whitelisted_domains:
                    continue

                dummy_item = BlacklistItem({'value': domain})

                if dummy_item in self.blacklisted_domains:
                    actual_item = next(
                        (x for x in self.blacklisted_domains if x == dummy_item), None
                    )
                    if actual_item:
                        reason_names = ", ".join([
                            (r[0] if isinstance(r, tuple) else r).value
                            for r in actual_item.reasons
                        ])
                        censor_replacement = f'[URL Blocked: {reason_names}]'
                        self.logger.warning('Blocked %s; %s', domain, reason_names)
                    else:
                        censor_replacement = '[URL]'

                    text = text[:start] + censor_replacement + text[end:]
                    continue

                text = text[:start] + '[URL]' + text[end:]

        return text

    async def get_moderation_warning(self, flagged_data: dict, locale: str):
        flagged = [cat for cat, val in flagged_data.items() if val]
        descriptions = []
        for cat in flagged:
            key = f'texts.moderation.categories.{cat}'
            descriptions.append(self.bot.internal_translator.T(key, locale))

        if not descriptions:
            return self.bot.internal_translator.T(
                'text.moderation.moderation.format',
                locale,
                count=0,
            )

        combined = self.bot.internal_translator.T(
            'text.moderation.moderation.format',
            locale,
            count=len(descriptions),
            content=descriptions[0],
            first=descriptions[0],
            last=descriptions[-1],
            list=', '.join(descriptions[:-1]),
        )

        return self.bot.internal_translator.T(
            'text.moderation.flagged_message',
            locale,
            {'categories': combined},
        )

    async def is_text_sendable(self, message: Message):
        normalized_content = normalize_text(message.content)
        if message.guild and self.bot.resources.profanity_filter.is_profane(
            normalized_content,
        ):
            return False

        return all(
            not re.search(word, normalized_content)
            for word in self.censored_words
        )

    async def moderate_message(self, message: Message) -> ModerationResult:
        text_result = self.moderator.moderate_text(message.content)
        if text_result.action == ModerationAction.BLOCK:
            return text_result

        image_data: list[bytes] = []
        total_size = 0
        try:
            async with asyncio.timeout(10):
                for attachment in message.attachments:
                    if (
                        not attachment.content_type
                        or not attachment.content_type.startswith('image/')
                    ):
                        continue

                    if (
                        attachment.size > MAX_IMAGE_BYTES
                        or total_size + attachment.size > MAX_TOTAL_IMAGE_BYTES
                    ):
                        return combine_results(
                            text_result,
                            ModerationResult.review(
                                'attachment_size_limit',
                                'Image attachments exceed moderation size limits',
                            ),
                        )

                    data = await attachment.read()

                    if (
                        len(data) > MAX_IMAGE_BYTES
                        or total_size + len(data) > MAX_TOTAL_IMAGE_BYTES
                    ):
                        return combine_results(
                            text_result,
                            ModerationResult.review(
                                'attachment_size_limit',
                                'Image attachments exceed moderation size limits',
                            ),
                        )
                    total_size += len(data)
                    image_data.append(data)
        except (HTTPException, TimeoutError):
            return combine_results(
                text_result,
                ModerationResult.review(
                    'attachment_read_failed',
                    'Image attachment could not be inspected',
                ),
            )

        if not image_data:
            return text_result

        image_result = await asyncio.to_thread(
            self.moderator.moderate_images,
            image_data,
        )
        return combine_results(text_result, image_result)

    async def broadcast_global_message(self, original: Message):
        if not original.guild:
            return
        original_guild = original.guild

        if not await self.is_text_sendable(original):
            self._record_counter(
                name='bot_global_chat_messages_total',
                description='Total count of messages sent to the global chat system',
                labels={'guild_id': str(original_guild.id), 'status': 'filtered'},
            )
            return

        moderation_result = await self.moderate_message(original)
        if moderation_result.action != ModerationAction.ALLOW:
            self._record_counter(
                name='bot_global_chat_messages_total',
                description='Total count of messages sent to the global chat system',
                labels={'guild_id': str(original_guild.id), 'status': 'filtered'},
            )
            self.logger.warning(
                'Held global chat message %s in guild %s for moderation: %s',
                original.id,
                original_guild.id,
                ', '.join(moderation_result.reason_codes),
            )
            return

        profile = (
            await self.bot.database.user.get_full_profile(original.author.id)
            if self.bot.database.user
            else None
        )
        display_name = (
            getattr(profile, 'nickname', original.author.display_name)
            if profile
            else original.author.display_name
        )

        description_text = original.content.replace(
            '@everyone',
            '@\u200beveryone',
        ).replace('@here', '@\u200bhere')

        content_text = await self.censor_urls(description_text)

        if not description_text:
            if original.attachments:
                description_text = (
                    f'User sent {len(original.attachments)} attachment(s).'
                )
            else:
                return

        embed = Embed(
            description=content_text,
            color=Color.green(),
            timestamp=original.created_at,
        )
        embed.set_author(name=display_name, icon_url=original.author.display_avatar.url)
        embed.set_footer(
            text=f'Sent from {original.guild.name if original.guild else "Unknown"}',
        )

        if not embed.description:
            if original.attachments:
                embed.description = self.bot.internal_translator.T(
                    'command.global_chat.texts.including_attachments_no_text',
                    original.guild.preferred_locale,
                    count=len(original.attachments),
                )
            else:
                return
        else:
            if original.attachments:
                embed.description += f'\n\n ({
                    self.bot.internal_translator.T(
                        "command.global_chat.texts.including_attachments",
                        original.guild.preferred_locale,
                        count=len(original.attachments),
                    )
                })'

        image_urls = []
        for attachment in original.attachments:
            if not attachment.content_type:
                continue
            if not attachment.content_type.startswith(('image', 'video')):
                continue
            image_urls.append(attachment.url)

        start_time = perf_counter()
        self._record_counter(
            name='bot_global_chat_messages_total',
            description='Total count of messages sent to the global chat system',
            labels={'guild_id': str(original_guild.id), 'status': 'broadcasted'},
        )

        async def _dispatch_broadcast():
            for guild in self.bot.guilds:
                if guild.id == original_guild.id:
                    continue

                config = (
                    await self.bot.database.guild.get_config(guild.id)
                    if self.bot.database.guild
                    else None
                )
                if not config:
                    continue

                global_feat = config.global_chat

                if global_feat.enabled and global_feat.channel_id:
                    channel = guild.get_channel(global_feat.channel_id)
                    if not channel or not isinstance(channel, TextChannel):
                        continue

                    files = []
                    for attachment in original.attachments:
                        if not attachment.content_type:
                            continue
                        if not attachment.content_type.startswith((
                            'image',
                            'video',
                        )):
                            continue

                        try:
                            files.append(
                                await attachment.to_file(
                                    spoiler=attachment.is_spoiler(),
                                ),
                            )
                        except (HTTPException, Forbidden, NotFound):
                            continue

                    try:
                        if (
                            global_feat.message_delivery_type
                            == GlobalChatDeliveryType.webhook
                        ):
                            permissions = channel.permissions_for(guild.me)
                            if not (
                                permissions.send_messages
                                and permissions.manage_webhooks
                            ):
                                continue

                            webhook = await self._get_or_create_webhook(channel)
                            if not webhook:
                                continue

                            webhook_kwargs = {
                                'username': f'{display_name} ({original_guild.name})',
                                'avatar_url': original.author.display_avatar.url,
                                'wait': True,
                                'content': content_text,
                                'silent': global_feat.silent,
                                'allowed_mentions': (
                                    AllowedMentions.none()
                                    if global_feat.silent
                                    else None
                                ),
                            }
                            if files:
                                webhook_kwargs['files'] = files

                            await webhook.send(**webhook_kwargs)
                        else:
                            permissions = channel.permissions_for(guild.me)
                            if not permissions.send_messages:
                                continue

                            bot_kwargs = {
                                'embed': embed,
                                'silent': global_feat.silent,
                                'allowed_mentions': (
                                    AllowedMentions.none()
                                    if global_feat.silent
                                    else None
                                ),
                            }
                            if files:
                                bot_kwargs['files'] = files

                            await channel.send(**bot_kwargs)
                    except NotFound:
                        self.webhook_cache.pop(channel.id, None)
                    except Forbidden:
                        self._record_counter(
                            name='bot_global_chat_broadcast_errors_total',
                            description=(
                                'Total number of API errors encountered'
                                'while relaying messages'
                            ),
                            labels={
                                'error_type': 'forbidden',
                                'target_guild': str(guild.id),
                            },
                        )
                    except HTTPException as e:
                        self._record_counter(
                            name='bot_global_chat_broadcast_errors_total',
                            description=(
                                'Total number of API errors encountered'
                                'while relaying messages'
                            ),
                            labels={
                                'error_type': f'http_{e.status}',
                                'target_guild': str(guild.id),
                            },
                        )

        if self.bot.metrics:
            async with self.bot.metrics.span_async(
                'bot_global_chat_broadcast',
                origin_guild=str(original.guild.id),
                message_id=str(original.id),
            ):
                await _dispatch_broadcast()
        else:
            await _dispatch_broadcast()

        broadcast_duration = perf_counter() - start_time
        if self.bot.metrics:
            self.bot.metrics.record_histogram(
                name='bot_global_chat_broadcast_duration_seconds',
                description=(
                    'The time taken to relay a single global chat message'
                    'to all connected guilds in seconds'
                ),
                value=broadcast_duration,
                labels={'origin_guild': str(original.guild.id)},
            )

    group = app_commands.Group(
        name='globalchat',
        description=app_commands.locale_str('command.global_chat.description'),
    )

    @group.command(
        name='setup',
        description=app_commands.locale_str('command.global_chat.setup.description'),
    )
    @app_commands.describe(
        channel=app_commands.locale_str('command.global_chat.setup.parameters.channel'),
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def globalchat_setup(self, interaction: Interaction, channel: TextChannel):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not self.bot.database.guild:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id

        config = await self.bot.database.guild.get_config(guild_id)

        config.global_chat.channel_id = channel.id
        config.global_chat.enabled = True

        await self.bot.database.guild.update_config(guild_id, config)

        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.setup.embeds.default.description',
                loc,
                channel=channel.mention,
            ),
        )
        return None

    @group.command(
        name='delivery',
        description=app_commands.locale_str(
            'command.global_chat.delivery.description',
        ),
    )
    @app_commands.describe(
        mode=app_commands.locale_str(
            'command.global_chat.delivery.parameters.mode',
        ),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def globalchat_delivery(
        self,
        interaction: Interaction,
        mode: Literal['bot', 'webhook'],
    ):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not self.bot.database.guild:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id
        config = await self.bot.database.guild.get_config(guild_id)

        if not config.global_chat.channel_id:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.feature_not_available.description',
                    loc,
                ),
            )

        delivery_type = (
            GlobalChatDeliveryType.webhook
            if mode.lower() == 'webhook'
            else GlobalChatDeliveryType.bot
        )
        config.global_chat.message_delivery_type = delivery_type

        await self.bot.database.guild.update_config(guild_id, config)

        await interaction.followup.send(
            f'Global chat delivery mode set to {mode}.',
        )
        return None

    @group.command(
        name='silent',
        description=app_commands.locale_str(
            'command.global_chat.silentmode.description',
        ),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def globalchat_set_silent(self, interaction: Interaction, value: bool):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not self.bot.database.guild:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id
        config = await self.bot.database.guild.get_config(guild_id)

        if not config.global_chat.channel_id:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.feature_not_available.description',
                    loc,
                ),
            )

        config.global_chat.silent = value

        await self.bot.database.guild.update_config(guild_id, config)

        status_text = self.bot.internal_translator.T(
            'text.boolean.true' if config.global_chat.silent else 'text.boolean.false',
            loc,
        )
        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.silentmode.embeds.default.description',
                loc,
                toggle=status_text,
            ),
        )
        return None

    @group.command(
        name='toggle',
        description=app_commands.locale_str('command.global_chat.toggle.description'),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def globalchat_toggle(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not self.bot.database.guild:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id
        config = await self.bot.database.guild.get_config(guild_id)

        if not config.global_chat.channel_id:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.feature_not_available.description',
                    loc,
                ),
            )

        current_status = config.global_chat.enabled
        config.global_chat.enabled = not current_status

        await self.bot.database.guild.update_config(guild_id, config)

        status_text = self.bot.internal_translator.T(
            'text.boolean.true' if config.global_chat.enabled else 'text.boolean.false',
            loc,
        )
        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.toggle.embeds.default.description',
                loc,
                status_text=status_text,
            ),
        )
        return None

    @group.command(
        name='status',
        description=app_commands.locale_str('command.global_chat.status.description'),
    )
    async def globalchat_status(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer()

        if not interaction.guild or not self.bot.database.guild:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        config = await self.bot.database.guild.get_config(interaction.guild.id)
        gc = config.global_chat

        channel_mention = (
            f'<#{gc.channel_id}>'
            if gc.channel_id
            else self.bot.internal_translator.T('text.unset', loc)
        )
        status_text = self.bot.internal_translator.T(
            'text.run_status.running' if gc.enabled else 'text.run_status.stopped',
            loc,
        )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.global_chat.status.embeds.default.title',
                loc,
                guild_name=interaction.guild.name,
            ),
            color=Color.blue(),
        )
        embed.add_field(
            name=self.bot.internal_translator.T('label.global_chat_status', loc),
            value=status_text,
            inline=False,
        )
        embed.add_field(
            name=self.bot.internal_translator.T('label.global_chat_channel', loc),
            value=channel_mention,
            inline=False,
        )
        embed.add_field(
            name='Delivery mode',
            value=(
                'Webhook'
                if gc.message_delivery_type == GlobalChatDeliveryType.webhook
                else 'Bot'
            ),
            inline=False,
        )
        embed.add_field(
            name='Silent mode',
            value='Enabled' if gc.silent else 'Disabled',
            inline=False,
        )

        filtering = config.filtering
        if filtering and filtering.enabled:
            antispam = filtering.filters.get('anti_spam')
            if antispam and antispam.enabled and isinstance(antispam, AntiSpamFilter):
                embed.add_field(
                    name=self.bot.internal_translator.T(
                        'label.global_chat_antispam',
                        loc,
                    ),
                    value=self.bot.internal_translator.T(
                        'command.global_chat.status.labels.anti_spam',
                        loc,
                        {
                            'per': antispam.window_length,
                            'count': antispam.messages_per_window,
                        },
                    ),
                    inline=False,
                )

        await interaction.followup.send(embed=embed)
        return None


async def setup(bot: PoxBot):
    await bot.add_cog(GlobalChatCog(bot))
