import asyncio
import contextlib
import os
import re
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiofiles
import orjson
from discord import (
    AllowedMentions,
    Color,
    Embed,
    Message,
)
from discord.abc import Messageable
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....services.ai import LLMManager, LLMProviderType
from ....shared.utils.app_path import app_dir


class LLMChatCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

        token_cfg = bot.settings.token_config
        api_key_str = None
        if token_cfg and hasattr(token_cfg, 'openrouter_api_key'):
            api_key_str = token_cfg.openrouter_api_key.get_secret_value()

        self.llm_manager = LLMManager(
            bot,
            bot.settings.token_config,
            api_key=api_key_str,
        )
        self.history: dict[int, deque[dict[str, Any]]] = {}
        self.history_limit = 25

        custom_dir = os.getenv('LLM_HISTORY_DIR')
        self.persistence_dir = (
            Path(custom_dir) if custom_dir else app_dir.user_data_path / 'llm_history'
        )
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

        self.cooldowns: dict[int, datetime] = {}
        self.cooldown_seconds = timedelta(seconds=8)
        self.locks: dict[int, asyncio.Lock] = {}

        self.trigger_patterns = [re.compile(r"\b(pox|p0x38)('s)?(\s+bot|bot)?\b")]

    def _get_file_path(self, channel_id: int) -> Path:
        return self.persistence_dir / f'{channel_id}.json'

    async def _save_history(self, channel_id: int):
        if channel_id not in self.history:
            return

        file_path = self._get_file_path(channel_id)
        to_save = list(self.history[channel_id])[-self.history_limit :]

        try:

            def _write() -> None:
                with file_path.open('wb') as f:
                    f.write(orjson.dumps(to_save))

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _write)
        except Exception:
            self.bot.logger.exception('Failed to persist history for %s', channel_id)

    async def format_discord_message(self, message: Message) -> dict[str, Any]:
        message_content = message.content.strip() if message.content else ''
        if message_content and self.bot.user:
            message_content = message_content.replace(
                f'<@{self.bot.user.id}> ',
                '',
            ).replace(f'<@!{self.bot.user.id}> ', '')  # type: ignore

        role_type = 'assistant' if message.author == self.bot.user else 'user'
        formatted_message_author = message.author.display_name
        formatted_message_content = (
            message_content if message_content else 'Empty message'
        )

        if message.attachments:
            attachments = ', '.join(a.filename for a in message.attachments)
            formatted_message_content = (
                f'{message_content} *includes attachments: {attachments}*'
            )

        if message.reference and isinstance(message.reference.resolved, Message):
            ref_msg = message.reference.resolved
            ref_author = (
                'You'
                if ref_msg.author == self.bot.user
                else ref_msg.author.display_name
            )
            role_content = (
                f'[{formatted_message_author} -> {ref_author}]'
                f'{formatted_message_content}'
            )
        elif message.mention_everyone:
            role_content = (
                f'[{formatted_message_author} -> @everyone] {formatted_message_content}'
            )
        elif len(message.mentions) == 1 and self.bot.user in message.mentions:
            role_content = (
                f'[{formatted_message_author} -> You] {formatted_message_content}'
            )
        else:
            role_content = f'[{formatted_message_author}] {formatted_message_content}'

        return {'role': role_type, 'content': role_content}

    def _sanitize_history_item(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {'role': 'assistant', 'content': str(item)}

        role = str(item.get('role', 'assistant'))
        content = item.get('content', '')

        if asyncio.iscoroutine(content):
            content = '<coroutine>'

        return {'role': role, 'content': str(content)}

    async def populate_channel_cache(
        self,
        channel: Messageable,
        limit: int = 10,
    ):
        channel_id = getattr(channel, 'id', 0)  # TODO: avoid if channel_id is 0
        if channel_id == 0 or not isinstance(channel, Messageable):
            return

        if channel_id not in self.history:
            self.history[channel_id] = deque(maxlen=self.history_limit)

        file_path = self._get_file_path(channel_id)

        if file_path.is_file():
            try:
                async with aiofiles.open(file_path, 'rb') as f:
                    raw = await f.read()
                    if raw:
                        loaded = orjson.loads(raw)
                        for item in loaded:
                            self.history[channel_id].append(
                                self._sanitize_history_item(item),
                            )
            except Exception:
                self.bot.logger.exception(
                    'Failed to load persisted history for a channel %s',
                    channel_id,
                )

        try:
            fetched_messages = [
                message
                async for message in channel.history(limit=limit, oldest_first=False)
            ]

            for message in reversed(fetched_messages):
                data = await self.format_discord_message(message)
                sanitized = self._sanitize_history_item(data)
                if sanitized not in self.history[channel_id]:
                    self.history[channel_id].append(sanitized)
        except Exception:
            self.bot.logger.exception('Failed to populate channel cache')

        await self._save_history(channel_id)

    async def respond(
        self,
        message: Message,
        provider: str,
        model: str,
        include_history: bool = False,
    ):
        if not self.bot.user:
            raise RuntimeError('Bot user is not set')  # noqa: TRY003

        now = datetime.now(UTC)
        user_cd = self.cooldowns.get(message.author.id)
        if user_cd:
            elapsed = now - user_cd
            cooldown_left = self.cooldown_seconds - elapsed
            if cooldown_left.total_seconds() > 0:
                remaining = max(1, round(cooldown_left.total_seconds()))
                with contextlib.suppress(Exception):
                    return await message.reply(
                        f'You are on cooldown. Please retry after {remaining} seconds',
                        allowed_mentions=AllowedMentions.none(),
                    )

        if len(self.cooldowns) > 1000:
            self.cooldowns = {
                k: v
                for k, v in self.cooldowns.items()
                if now - v < self.cooldown_seconds
            }

        lock = self.locks.setdefault(message.channel.id, asyncio.Lock())

        async with lock:
            if message.channel.id not in self.history:
                await self.populate_channel_cache(message.channel)

            messages = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
            current_msg_data = self._sanitize_history_item(
                await self.format_discord_message(message),
            )

            is_duplicate = any(
                h['content'] == current_msg_data['content']
                and h['role'] == current_msg_data['role']
                for h in self.history[message.channel.id]
            )

            if not is_duplicate:
                self.history[message.channel.id].append(current_msg_data)
                await self._save_history(message.channel.id)

            if include_history:
                messages.extend(
                    self._sanitize_history_item(data)
                    for data in self.history[message.channel.id]
                )
            else:
                messages.append(current_msg_data)

            self.cooldowns[message.author.id] = now
            output = ''

            async with message.channel.typing():
                try:
                    input_payload = {
                        'provider': provider,
                        'model': model,
                        'query': messages,
                    }

                    async with self.llm_manager.generate_response(
                        input_payload,
                    ) as chunk:
                        output += chunk
                except Exception as e:
                    embed = Embed(
                        title=e.__class__.__name__,
                        description=str(e),
                        color=Color.red(),
                    )
                    self.bot.logger.exception('Failed to generate response')
                    return await message.channel.send(
                        embed=embed,
                        allowed_mentions=AllowedMentions.none(),
                    )

                output = output.strip()
                if not output:
                    raise RuntimeError('AI returned an empty response.')  # noqa: TRY003

                output = output.replace(
                    '{author_name}',
                    message.author.display_name or 'User',
                )
                output = output.replace('{author_mention}', message.author.mention)

                is_reply = output.startswith('[REPLY]')
                send_content = output[7:] if is_reply else output

                if len(send_content) > 2000:
                    chunks = [
                        send_content[i : i + 2000]
                        for i in range(0, len(send_content), 2000)
                    ]
                    for chunk in chunks:
                        if is_reply:
                            await message.reply(
                                chunk,
                                allowed_mentions=AllowedMentions.none(),
                            )
                        else:
                            await message.channel.send(
                                chunk,
                                allowed_mentions=AllowedMentions.none(),
                            )
                else:
                    if is_reply:
                        await message.reply(
                            send_content,
                            allowed_mentions=AllowedMentions.none(),
                        )
                    else:
                        await message.channel.send(
                            send_content,
                            allowed_mentions=AllowedMentions.none(),
                        )

                self.history[message.channel.id].append(
                    self._sanitize_history_item({
                        'role': 'assistant',
                        'content': output,
                    }),
                )
                await self._save_history(message.channel.id)

    def is_matching(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.trigger_patterns)

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.user:
            return

        if message.content.startswith(self.bot.settings.bot_prefix):
            return

        is_triggered = False

        if self.bot.user in message.mentions and not message.mention_everyone:
            is_triggered = True

        if (
            not is_triggered
            and hasattr(self, 'is_matching')
            and self.is_matching(message.content)
        ):
            is_triggered = True

        if not is_triggered:
            return

        read_history = True
        if message.guild:
            member = message.guild.me or message.guild.get_member(self.bot.user.id)
            if not member:
                return

            permissions = message.channel.permissions_for(member)
            if not permissions.send_messages:
                return
            read_history = permissions.read_message_history

        await self.respond(
            message=message,
            provider=LLMProviderType.OPEN_ROUTER.value,
            model=self.bot.settings.llm_config.model_id,
            include_history=read_history,
        )


async def setup(bot: PoxBot):
    await bot.add_cog(LLMChatCog(bot))
