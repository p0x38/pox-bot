import asyncio
import hashlib
import json
import re
import unicodedata
from datetime import datetime
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
    Member,
    Message,
    NotFound,
    RawBulkMessageDeleteEvent,
    RawMessageDeleteEvent,
    TextChannel,
    Thread,
    Webhook,
    app_commands,
)
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....features.moderation import (
    GlobalChatModerator,
    ModerationAction,
    ModerationReason,
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
    AntiMessageFilter,
    AntiSpamFilter,
    GlobalChatDeliveryType,
    GuildConfigV2,
    ProfanityFilter,
)
from ....persistence.models.pydantic.blacklisted_item import (
    BlacklistItem,
)
from ....services.spam import AntiSpamManager
from ..checks.is_owner import is_bot_owner


class GlobalChatCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.logger = get_logger(__name__, prefix='GlobalChat')
        self.antispam_managers: dict[int, AntiSpamManager] = {}
        self.whitelisted_domains = {
            domain.strip().casefold().rstrip('.')
            for domain in bot.constants.whitelisted_domains
            if domain.strip()
        }
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

    async def _send_audit_log(
        self,
        guild_id: int,
        *,
        title: str,
        description: str,
        color: Color | None = None,
        fields: dict[str, str] | None = None,
        channel_id: int | None = None,
    ) -> None:
        database = self.bot.database.guild
        try:
            if channel_id is None:
                if database is None:
                    return

                config = await database.get_config(guild_id)
                if not config.logs.enabled:
                    return

                channel_id = config.logs.channel_id

            if channel_id is None:
                return

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)

            if not isinstance(channel, TextChannel):
                self.logger.warning(
                    'Global-chat audit channel %s is not a text channel',
                    channel_id,
                )
                return

            embed = Embed(
                title=title,
                description=description,
                color=color or Color.blurple(),
            )
            for name, value in (fields or {}).items():
                embed.add_field(name=name, value=value, inline=False)

            await channel.send(
                embed=embed,
                allowed_mentions=AllowedMentions.none(),
            )
        except (Forbidden, NotFound) as error:
            self.logger.warning(
                'Could not send global-chat audit log for guild %s: %s',
                guild_id,
                error,
            )
        except HTTPException:
            self.logger.exception(
                'Failed to send global-chat audit log for guild %s',
                guild_id,
            )
        except Exception:
            self.logger.exception(
                'Unexpected error while sending global-chat audit log for guild %s',
                guild_id,
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
        anti_message_setting = filtering.filters.get('anti_message')
        if (
            filtering.enabled
            and isinstance(anti_message_setting, AntiMessageFilter)
            and anti_message_setting.enabled
            and message.author.id in anti_message_setting.blocked_user_ids
        ):
            return

        restrictions = await db_manager.guild.get_moderation_entries(
            item_type='user',
            item_scope=(message.guild.id, -1, -2),
        )

        now = datetime.now(UTC).timestamp()
        restriction = next(
            (
                entry
                for entry in restrictions
                if entry.value == str(message.author.id)
                and (entry.expires_at is None or entry.expires_at > now)
            ),
            None,
        )

        if restriction is not None:
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

        await self.broadcast_global_message(message, config=config)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent) -> None:
        if payload.guild_id is None:
            return

        await self._handle_global_chat_message_deletion(
            payload.message_id,
            origin_guild_id=payload.guild_id,
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self,
        payload: RawBulkMessageDeleteEvent,
    ) -> None:
        if payload.guild_id is None:
            return

        for message_id in payload.message_ids:
            await self._handle_global_chat_message_deletion(
                message_id,
                origin_guild_id=payload.guild_id,
            )

    async def _handle_global_chat_message_deletion(
        self,
        message_id: int,
        *,
        origin_guild_id: int,
    ) -> None:
        database = self.bot.database.guild
        if database is None:
            return

        origin_message_id = await database.get_global_chat_origin_message_id(
            message_id,
        )
        if origin_message_id is None or origin_message_id != message_id:
            return

        replicas: dict[int, tuple[int, int]] = await database.get_global_chat_replicas(
            origin_message_id
        )
        deleted_count = 0
        failed_count = 0
        for replica_guild_id, (
            replica_channel_id,
            replica_message_id,
        ) in replicas.items():
            if replica_message_id == origin_message_id:
                continue

            channel = self.bot.get_channel(replica_channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(replica_channel_id)
                except NotFound:
                    continue
                except Forbidden:
                    self.logger.warning(
                        'Cannot access global-chat replica channel %s',
                        replica_channel_id,
                    )
                    continue
                except HTTPException:
                    self.logger.exception(
                        'Failed to fetch global-chat replica channel %s',
                        replica_channel_id,
                    )
                    continue

            if not isinstance(channel, (TextChannel, Thread)):
                continue

            try:
                await channel.get_partial_message(replica_message_id).delete()
                deleted_count += 1
            except NotFound:
                pass
            except Forbidden:
                failed_count += 1
                self.logger.warning(
                    'Cannot delete global-chat replica message %s in channel %s',
                    replica_message_id,
                    replica_channel_id,
                )
                await self._send_audit_log(
                    replica_guild_id,
                    title='Global-chat replica deletion failed',
                    description=(
                        'The bot lacks permission to delete a mirrored message.'
                    ),
                    color=Color.red(),
                    fields={'Origin message ID': str(origin_message_id)},
                )
            except HTTPException:
                failed_count += 1
                self.logger.exception(
                    'Failed to delete global-chat replica message %s in channel %s',
                    replica_message_id,
                    replica_channel_id,
                )
                await self._send_audit_log(
                    replica_guild_id,
                    title='Global-chat replica deletion failed',
                    description=(
                        'Discord returned an error while deleting a mirrored message.'
                    ),
                    color=Color.red(),
                    fields={'Origin message ID': str(origin_message_id)},
                )

        await database.delete_global_chat_message_references(origin_message_id)

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

                hostname = (
                    '.'.join(
                        part for part in (ext.subdomain, ext.domain, ext.suffix) if part
                    )
                    .casefold()
                    .rstrip('.')
                )

                domain = f'{ext.domain}.{ext.suffix}'.casefold().rstrip('.')

                if any(
                    hostname == allowed_domain
                    or hostname.endswith(f'.{allowed_domain}')
                    for allowed_domain in self.whitelisted_domains
                ):
                    continue

                dummy_item = BlacklistItem({'value': domain})

                if dummy_item in self.blacklisted_domains:
                    actual_item = next(
                        (x for x in self.blacklisted_domains if x == dummy_item), None
                    )
                    if actual_item:
                        reason_names = ', '.join(
                            [
                                (r[0] if isinstance(r, tuple) else r).value
                                for r in actual_item.reasons
                            ]
                        )
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

    async def moderate_message(
        self,
        message: Message,
        *,
        config: GuildConfigV2 | None = None,
    ) -> ModerationResult:
        text_result = self.moderator.moderate_text(message.content)
        if config and config.filtering.enabled:
            sub_feats = config.filtering.filters

            profanity = sub_feats.get('profanity')

            if (
                profanity
                and profanity.enabled
                and isinstance(profanity, ProfanityFilter)
                and profanity.use_in_globalchat
                and message.guild
                and self.bot.resources.profanity_filter.is_profane(
                    normalize_text(message.content),
                )
            ):
                text_result = combine_results(
                    text_result,
                    ModerationResult.block(
                        ModerationReason.PROFANITY,
                        'Message contains profanity',
                    ),
                )

        if text_result.action == ModerationAction.BLOCK:
            return text_result

        image_data: list[bytes] = []
        total_size = 0
        try:
            async with asyncio.timeout(10):
                for attachment in message.attachments:
                    if (
                        not attachment.content_type
                        or not attachment.content_type.startswith(('image/',))
                    ):
                        continue

                    if (
                        attachment.size > MAX_IMAGE_BYTES
                        or total_size + attachment.size > MAX_TOTAL_IMAGE_BYTES
                    ):
                        return combine_results(
                            text_result,
                            ModerationResult.review(
                                ModerationReason.ATTACHMENT_SIZE_LIMIT,
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
                                ModerationReason.ATTACHMENT_SIZE_LIMIT,
                                'Image attachments exceed moderation size limits',
                            ),
                        )
                    total_size += len(data)
                    image_data.append(data)
        except (HTTPException, TimeoutError):
            return combine_results(
                text_result,
                ModerationResult.review(
                    ModerationReason.ATTACHMENT_READ_FAILED,
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

    def _get_moderation_reason_labels(
        self,
        reason_codes: tuple[str, ...] | list[str],
        locale: str,
    ) -> list[str]:
        reason_labels = []
        for reason_code in reason_codes:
            try:
                reason = ModerationReason(reason_code)
            except ValueError:
                reason = ModerationReason.INDICATOR_MATCH

            reason_labels.append(
                self.bot.internal_translator.T(
                    f'text.moderation.global_chat.reasons.{reason.value}',
                    locale,
                ),
            )

        return reason_labels

    def _get_moderation_notice(self, result: ModerationResult, locale: str) -> Embed:
        reason_labels = self._get_moderation_reason_labels(
            result.reason_codes,
            locale,
        )
        if not reason_labels:
            reason_labels = self._get_moderation_reason_labels(
                [],
                locale,
            )

        action_key = 'review' if result.action == ModerationAction.REVIEW else 'blocked'
        separator = '、' if locale.lower().startswith('ja') else '; '
        return Embed(
            title=self.bot.internal_translator.T(
                f'text.moderation.global_chat.{action_key}.title',
                locale,
            ),
            description=self.bot.internal_translator.T(
                f'text.moderation.global_chat.{action_key}.description',
                locale,
                reasons=separator.join(reason_labels),
            ),
            color=(
                Color.orange()
                if result.action == ModerationAction.REVIEW
                else Color.red()
            ),
        )

    async def _send_moderation_notice(
        self,
        message: Message,
        result: ModerationResult,
    ) -> None:
        if not message.guild:
            return

        notice = self._get_moderation_notice(
            result,
            str(message.guild.preferred_locale),
        )
        try:
            await message.reply(
                embed=notice,
                delete_after=10.0,
                mention_author=False,
                allowed_mentions=AllowedMentions.none(),
            )
        except (Forbidden, NotFound) as error:
            self.logger.warning(
                'Could not send moderation notice for message %s in guild %s: %s',
                message.id,
                message.guild.id,
                error,
            )
        except HTTPException:
            self.logger.exception(
                'Failed to send moderation notice for message %s in guild %s',
                message.id,
                message.guild.id,
            )

    @staticmethod
    def _message_fingerprint(message: Message) -> str:
        snapshot = [
            message.content,
            [
                (attachment.id, attachment.filename, attachment.size)
                for attachment in message.attachments
            ],
        ]
        return hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode(),
        ).hexdigest()

    async def broadcast_global_message(
        self,
        original: Message,
        *,
        config: GuildConfigV2 | None = None,
        approved: bool = False,
    ):
        if not original.guild:
            return
        original_guild = original.guild

        if not approved:
            is_whitelisted = (
                config is not None
                and original.author.id in config.global_chat.whitelisted_user_ids
            )

            if not approved and not is_whitelisted:
                moderation_result = await self.moderate_message(
                    original,
                    config=config,
                )

                if moderation_result.action != ModerationAction.ALLOW:
                    self._record_counter(
                        name='bot_global_chat_messages_total',
                        description=(
                            'Total count of messages sent to the global chat system'
                        ),
                        labels={
                            'guild_id': str(original_guild.id),
                            'status': 'filtered',
                        },
                    )
                    self.logger.warning(
                        'Held global chat message %s in guild %s for moderation: %s',
                        original.id,
                        original_guild.id,
                        ', '.join(moderation_result.reason_codes),
                    )
                    if (
                        moderation_result.action == ModerationAction.REVIEW
                        and self.bot.database.guild
                    ):
                        await (
                            self.bot.database.guild.create_global_chat_moderation_case(
                                message_id=original.id,
                                guild_id=original_guild.id,
                                channel_id=original.channel.id,
                                author_id=original.author.id,
                                reason_codes=list(moderation_result.reason_codes),
                                message_fingerprint=self._message_fingerprint(original),
                            )
                        )
                    await self._send_moderation_notice(original, moderation_result)
                    await self._send_audit_log(
                        original_guild.id,
                        title='Global chat moderation',
                        description=(
                            'A message was held for review.'
                            if moderation_result.action == ModerationAction.REVIEW
                            else 'A message was blocked by moderation.'
                        ),
                        color=(
                            Color.orange()
                            if moderation_result.action == ModerationAction.REVIEW
                            else Color.red()
                        ),
                        fields={
                            'Author ID': str(original.author.id),
                            'Message': original.jump_url,
                            'Action': moderation_result.action.name,
                            'Reasons': (
                                ', '.join(moderation_result.reason_codes) or 'Unknown'
                            ),
                        },
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

        database = self.bot.database.guild
        reply_replicas: dict[int, tuple[int, int]] = {}
        reference = original.reference

        if database:
            if reference and reference.message_id:
                parent_origin_message_id = (
                    await database.get_global_chat_origin_message_id(
                        reference.message_id,
                    )
                )
                if parent_origin_message_id is not None:
                    reply_replicas = await database.get_global_chat_replicas(
                        parent_origin_message_id,
                    )

            await database.save_global_chat_message_reference(
                origin_message_id=original.id,
                replica_message_id=original.id,
                replica_guild_id=original_guild.id,
                replica_channel_id=original.channel.id,
            )

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
                        if not attachment.content_type.startswith(
                            (
                                'image',
                                'video',
                                'audio',
                            )
                        ):
                            continue

                        try:
                            files.append(
                                await attachment.to_file(
                                    spoiler=attachment.is_spoiler(),
                                ),
                            )
                        except (HTTPException, Forbidden, NotFound):
                            continue

                    sent_message: Message | None = None
                    try:
                        permissions = channel.permissions_for(guild.me)
                        reply_replica = reply_replicas.get(guild.id)
                        reply_message_id = (
                            reply_replica[1]
                            if reply_replica is not None
                            and reply_replica[0] == channel.id
                            else None
                        )

                        if (
                            reply_message_id is not None
                            and permissions.send_messages
                            and permissions.read_message_history
                        ):
                            bot_kwargs = {
                                'embed': embed,
                                'silent': global_feat.silent,
                                'allowed_mentions': (
                                    AllowedMentions.none()
                                    if global_feat.silent
                                    else None
                                ),
                                'reference': channel.get_partial_message(
                                    reply_message_id,
                                ),
                                'mention_author': False,
                            }
                            if files:
                                bot_kwargs['files'] = files

                            sent_message = await channel.send(**bot_kwargs)

                        elif (
                            global_feat.message_delivery_type
                            == GlobalChatDeliveryType.webhook
                        ):
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

                            sent_message = await webhook.send(**webhook_kwargs)
                        else:
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

                            sent_message = await channel.send(**bot_kwargs)

                        if sent_message is not None and database:
                            await database.save_global_chat_message_reference(
                                origin_message_id=original.id,
                                replica_message_id=sent_message.id,
                                replica_guild_id=guild.id,
                                replica_channel_id=channel.id,
                            )
                    except NotFound:
                        self.webhook_cache.pop(channel.id, None)
                        await self._send_audit_log(
                            guild.id,
                            title='Global-chat relay failed',
                            description=(
                                'The destination channel or webhook was not found.'
                            ),
                            color=Color.red(),
                            fields={
                                'Origin guild ID': str(original_guild.id),
                                'Origin message ID': str(original.id),
                            },
                        )
                    except Forbidden:
                        await self._send_audit_log(
                            guild.id,
                            title='Global-chat relay failed',
                            description=(
                                'The bot lacks permission to relay this message.'
                            ),
                            color=Color.red(),
                            fields={
                                'Origin message ID': str(original.id),
                            },
                        )
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
                        await self._send_audit_log(
                            guild.id,
                            title='Global-chat relay failed',
                            description=f'Discord returned HTTP status {e.status}.',
                            color=Color.red(),
                            fields={
                                'Origin guild ID': str(original_guild.id),
                                'Origin message ID': str(original.id),
                            },
                        )
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
        guild_only=True,
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

        database = self.bot.database.guild

        if not interaction.guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id

        def configure(config: GuildConfigV2) -> tuple[bool, str | None]:
            config.global_chat.channel_id = channel.id
            config.global_chat.enabled = True

            return True, None

        await database.mutate_config(guild_id, configure)
        await self._send_audit_log(
            guild_id,
            title='Global chat configured',
            description=f'The global-chat channel was set to {channel.mention}.',
            fields={'Changed by user ID': str(interaction.user.id)},
        )

        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.setup.embeds.default.description',
                loc,
                channel=channel.mention,
            ),
        )

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

        database = self.bot.database.guild

        if not interaction.guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id

        def mutation(config: GuildConfigV2) -> tuple[bool, str | None]:
            global_chat = config.global_chat

            if not global_chat.enabled:
                return False, 'not_configured'

            delivery_type = (
                GlobalChatDeliveryType.webhook
                if mode.lower() == 'webhook'
                else GlobalChatDeliveryType.bot
            )
            config.global_chat.message_delivery_type = delivery_type
            return True, None

        _, updated, message = await database.mutate_config(guild_id, mutation)

        if not updated and message == 'not_configured':
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.feature_not_available.description',
                    loc,
                ),
            )

        await self._send_audit_log(
            guild_id,
            title='Global-chat delivery mode changed',
            description=f'Delivery mode changed to {mode.lower()}.',
            fields={'Changed by user ID': str(interaction.user.id)},
        )

        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.delivery.texts.success',
                loc,
                {'mode': mode.capitalize()},
            )
        )

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

        database = self.bot.database.guild

        if not interaction.guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id

        def mutation(config: GuildConfigV2) -> tuple[bool, str | None]:
            global_chat = config.global_chat

            if not global_chat.enabled:
                return False, 'not_configured'

            config.global_chat.silent = value
            return True, None

        config, updated, message = await database.mutate_config(guild_id, mutation)

        if not updated and message == 'not_configured':
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.feature_not_available.description',
                    loc,
                ),
            )

        await self._send_audit_log(
            guild_id,
            title='Global-chat silent mode changed',
            description=f'Silent mode is now {"enabled" if value else "disabled"}.',
            fields={'Changed by user ID': str(interaction.user.id)},
        )

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

        database = self.bot.database.guild

        if not interaction.guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = interaction.guild.id

        def toggle(config: GuildConfigV2) -> tuple[bool, str | None]:
            global_chat = config.global_chat

            if not global_chat.channel_id:
                return False, 'not_configured'

            global_chat.enabled = not global_chat.enabled
            return True, None

        config, toggled, message = await database.mutate_config(guild_id, toggle)

        if not toggled and message == 'not_configured':
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.feature_not_available.description',
                    loc,
                ),
            )

        await self._send_audit_log(
            guild_id,
            title='Global chat toggled',
            description=(
                f'Global chat is now '
                f'{"enabled" if config.global_chat.enabled else "disabled"}.'
            ),
            fields={'Changed by user ID': str(interaction.user.id)},
        )

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
        embed.add_field(
            name='Server log channel',
            value=(
                f'<#{config.logs.channel_id}>'
                if config.logs.enabled and config.logs.channel_id is not None
                else 'Disabled'
            ),
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

            profanity = filtering.filters.get('profanity')
            if (
                profanity
                and profanity.enabled
                and isinstance(profanity, ProfanityFilter)
            ):
                embed.add_field(
                    name=self.bot.internal_translator.T(
                        'label.global_chat_profanity_filter',
                        loc,
                    ),
                    value=self.bot.internal_translator.T(
                        'command.global_chat.status.labels.profanity_filter',
                        loc,
                    ),
                    inline=False,
                )

        await interaction.followup.send(embed=embed)
        return None

    @group.command(
        name='pending',
        description=app_commands.locale_str(
            'command.global_chat.pending.description',
        ),
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def globalchat_pending(self, interaction: Interaction):
        loc = str(await self.bot.get_locale(interaction))
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not self.bot.database.guild:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        cases = await self.bot.database.guild.get_pending_global_chat_moderation_cases(
            interaction.guild.id,
        )
        if not cases:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.pending.responses.empty',
                    loc,
                ),
            )

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.global_chat.pending.embeds.default.title',
                loc,
            ),
            description=self.bot.internal_translator.T(
                'command.global_chat.pending.embeds.default.description',
                loc,
            ),
            color=Color.orange(),
        )
        for case in cases:
            message_link = (
                f'https://discord.com/channels/{case.guild_id}/'
                f'{case.channel_id}/{case.message_id}'
            )
            reason_labels = self._get_moderation_reason_labels(
                case.reason_codes,
                loc,
            )
            separator = '、' if loc.lower().startswith('ja') else '; '
            reason_text = separator.join(reason_labels) or (
                self.bot.internal_translator.T(
                    'text.moderation.global_chat.reasons.indicator_match',
                    loc,
                )
            )
            embed.add_field(
                name=str(case.message_id),
                value=self.bot.internal_translator.T(
                    'command.global_chat.pending.embeds.default.case',
                    loc,
                    message_link=message_link,
                    reasons=reason_text,
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)
        return None

    @group.command(
        name='review',
        description=app_commands.locale_str(
            'command.global_chat.review.description',
        ),
    )
    @app_commands.describe(
        message_id=app_commands.locale_str(
            'command.global_chat.review.parameters.message_id',
        ),
        decision=app_commands.locale_str(
            'command.global_chat.review.parameters.decision',
        ),
    )
    @app_commands.choices(
        decision=[
            app_commands.Choice(
                name=app_commands.locale_str(
                    'command.global_chat.review.choices.approve',
                ),
                value='approve',
            ),
            app_commands.Choice(
                name=app_commands.locale_str(
                    'command.global_chat.review.choices.deny',
                ),
                value='deny',
            ),
        ],
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def globalchat_review(
        self,
        interaction: Interaction,
        message_id: str,
        decision: app_commands.Choice[str],
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

        try:
            parsed_message_id = int(message_id)
        except ValueError:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.invalid_id',
                    loc,
                ),
            )

        database = self.bot.database.guild
        guild_id = interaction.guild.id
        case = await database.get_global_chat_moderation_case(
            guild_id,
            parsed_message_id,
        )
        if case is None or case.status != 'pending':
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.not_pending',
                    loc,
                ),
            )

        if decision.value == 'deny':
            resolved = await database.resolve_global_chat_moderation_case(
                guild_id=guild_id,
                message_id=parsed_message_id,
                status='denied',
                reviewer_id=interaction.user.id,
            )
            if resolved:
                await self._send_audit_log(
                    guild_id,
                    title='Global-chat message review denied',
                    description=f'Message `{parsed_message_id}` was denied by review.',
                    color=Color.red(),
                    fields={'Reviewer ID': str(interaction.user.id)},
                )
            response_key = 'denied' if resolved else 'already_reviewed'
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    f'command.global_chat.review.responses.{response_key}',
                    loc,
                ),
            )

        channel = interaction.guild.get_channel_or_thread(case.channel_id)
        try:
            if channel is None:
                channel = await self.bot.fetch_channel(case.channel_id)
            if not isinstance(channel, (TextChannel, Thread)):
                return await interaction.followup.send(
                    self.bot.internal_translator.T(
                        'command.global_chat.review.responses.source_unavailable',
                        loc,
                    ),
                )
            original = await channel.fetch_message(case.message_id)
        except NotFound:
            await database.resolve_global_chat_moderation_case(
                guild_id=guild_id,
                message_id=parsed_message_id,
                status='stale',
                reviewer_id=interaction.user.id,
            )
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.message_missing',
                    loc,
                ),
            )
        except Forbidden:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.source_unavailable',
                    loc,
                ),
            )
        except HTTPException:
            self.logger.exception(
                'Failed to fetch pending global-chat message %s',
                parsed_message_id,
            )
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.failed',
                    loc,
                ),
            )

        if self._message_fingerprint(original) != case.message_fingerprint:
            await database.resolve_global_chat_moderation_case(
                guild_id=guild_id,
                message_id=parsed_message_id,
                status='stale',
                reviewer_id=interaction.user.id,
            )
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.message_changed',
                    loc,
                ),
            )

        resolved = await database.resolve_global_chat_moderation_case(
            guild_id=guild_id,
            message_id=parsed_message_id,
            status='approved',
            reviewer_id=interaction.user.id,
        )
        if not resolved:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.review.responses.already_reviewed',
                    loc,
                ),
            )

        await self.broadcast_global_message(original, approved=True)
        await self._send_audit_log(
            guild_id,
            title='Global-chat message review approved',
            description=f'Message `{parsed_message_id}` was approved and broadcast.',
            color=Color.green(),
            fields={'Reviewer ID': str(interaction.user.id)},
        )
        return await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.review.responses.approved',
                loc,
            ),
        )

    @group.command(
        name='whitelist',
        description=app_commands.locale_str(
            'command.global_chat.whitelist.description'
        ),
    )
    @app_commands.describe(
        user=app_commands.locale_str('command.global_chat.whitelist.parameters.user')
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @is_bot_owner()
    async def globalchat_whitelist(
        self,
        interaction: Interaction,
        user: Member,
    ) -> None:
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        database = self.bot.database.guild
        guild = interaction.guild

        if not guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = guild.id

        def mutation(config: GuildConfigV2) -> tuple[bool, str | None]:
            global_chat = config.global_chat

            if user.id in global_chat.whitelisted_user_ids:
                return False, 'no_change'

            global_chat.whitelisted_user_ids.append(user.id)
            global_chat.whitelisted_user_ids.sort()

            return True, None

        _, updated, message = await database.mutate_config(guild_id, mutation)

        if not updated and message == 'no_change':
            await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.whitelist.texts.already_whitelisted',
                    loc,
                    {'mention': user.mention},
                ),
                ephemeral=True,
            )
            return  # ruff: ignore[implicit-return-value]

        await self._send_audit_log(
            guild.id,
            title='Global-chat whitelist updated',
            description='A member was added to the moderation whitelist.',
            color=Color.green(),
            fields={
                'Member': f'{user} ({user.id})',
                'Changed by': (f'{interaction.user} ({interaction.user.id})'),
            },
        )

        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.whitelist.texts.whitelisted',
                loc,
                {'mention': user.mention},
            ),
            ephemeral=True,
        )

    @group.command(
        name='unwhitelist',
        description=app_commands.locale_str(
            'command.global_chat.unwhitelist.description'
        ),
    )
    @app_commands.describe(
        user=app_commands.locale_str('command.global_chat.unwhitelist.parameters.user')
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def globalchat_unwhitelist(
        self,
        interaction: Interaction,
        user: Member,
    ) -> None:
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        database = self.bot.database.guild
        guild = interaction.guild

        if not guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        guild_id = guild.id

        def mutate(config: GuildConfigV2) -> tuple[bool, str | None]:
            global_chat = config.global_chat

            if user.id not in global_chat.whitelisted_user_ids:
                return False, 'no_change'

            global_chat.whitelisted_user_ids.remove(user.id)

            return True, None

        _, updated, message = await database.mutate_config(
            guild_id,
            mutate,
        )

        if not updated and message == 'no_change':
            await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.global_chat.unwhitelist.texts.not_whitelisted',
                    loc,
                    {'mention': user.mention},
                ),
                ephemeral=True,
            )
            return  # ruff: ignore[implicit-return-value]

        await self._send_audit_log(
            guild.id,
            title='Global-chat whitelist updated',
            description='A member was removed from the moderation whitelist.',
            color=Color.orange(),
            fields={
                'Member': f'{user} ({user.id})',
                'Changed by': (f'{interaction.user} ({interaction.user.id})'),
            },
        )

        await interaction.followup.send(
            self.bot.internal_translator.T(
                'command.global_chat.unwhitelist.texts.unwhitelisted',
                loc,
                {'mention': user.mention},
            ),
            ephemeral=True,
        )

    @group.command(
        name='whitelist_list',
        description=app_commands.locale_str(
            'command.global_chat.whitelist_list.description'
        ),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def globalchat_whitelist_list(
        self,
        interaction: Interaction,
    ) -> None:
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        database = self.bot.database.guild
        guild = interaction.guild

        if not guild or not database:
            return await interaction.followup.send(
                self.bot.internal_translator.T(
                    'error.embeds.database_not_available.description',
                    loc,
                ),
            )

        config = await database.get_config(guild.id)
        user_ids = sorted(config.global_chat.whitelisted_user_ids)

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.global_chat.whitelist_list.embeds.default.title',
                loc,
            ),
            description=(
                '\n'.join(f'<@{user_id}> (`{user_id}`)' for user_id in user_ids)
                if user_ids
                else self.bot.internal_translator.T(
                    'command.global_chat.whitelist_list.embeds.default.description',
                    loc,
                )
            ),
            color=Color.blurple(),
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: PoxBot):
    await bot.add_cog(GlobalChatCog(bot))
