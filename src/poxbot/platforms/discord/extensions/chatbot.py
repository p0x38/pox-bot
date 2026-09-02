from __future__ import annotations

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
    Interaction,
    Message,
    app_commands,
)
from discord.abc import Messageable
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....features.markov.dialogue import MarkovDialogueMemory
from ....features.markov.generator import MarkovGenerator
from ....features.markov.model import (
    MarkovGenerationResult,
    MarkovModel,
    MarkovModelKey,
)
from ....features.markov.storage import MarkovDatabase
from ....features.markov.tokenizer import MarkovTokenizer
from ....persistence.models.guild_settings_v2 import ChatbotMethodType, MarkovModelScope
from ....services.ai import LLMManager, LLMProviderType
from ....shared.utils.app_path import app_dir


class ChatbotCog(commands.Cog):
    chatbot_group = app_commands.Group(
        name='chatbot',
        description='Configure and use the chatbot',
    )

    def __init__(self, bot: PoxBot):
        self.bot = bot

        # ------------------------------------------------------------------
        # AI
        # ------------------------------------------------------------------

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
        self.persistence_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ------------------------------------------------------------------
        # Markov
        # ------------------------------------------------------------------

        self.markov_tokenizer = MarkovTokenizer()
        self.markov_models: dict[MarkovModelKey, MarkovModel] = {}
        self.markov_dialogues: dict[MarkovModelKey, MarkovDialogueMemory] = {}
        self.markov_dialogue_dir = app_dir.user_data_path / 'markov'
        self.markov_dialogue_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ------------------------------------------------------------------
        # Runtime state
        # ------------------------------------------------------------------

        self.cooldowns: dict[int, datetime] = {}
        self.cooldown_seconds = timedelta(seconds=8)
        self.locks: dict[int, asyncio.Lock] = {}

        self.trigger_patterns = [
            re.compile(r"\b(pox|p0x38)('s)?(\s+bot|bot)?\b"),
        ]

        self.database = bot.database.guild

    @property
    def markov_storage(self) -> MarkovDatabase:
        database = self.bot.database.markov

        if database is None:
            raise RuntimeError(
                'Markov database is not initialized',
            )

        return database

    # ======================================================================
    # AI history persistence
    # ======================================================================

    def _get_file_path(self, channel_id: int) -> Path:
        return self.persistence_dir / f'{channel_id}.json'

    async def _save_history(self, channel_id: int) -> None:
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
            self.bot.logger.exception(
                'Failed to persist history for %s',
                channel_id,
            )

    # ======================================================================
    # Markov persistence
    # ======================================================================

    def _get_markov_dialogue_path(
        self,
        key: MarkovModelKey,
    ) -> Path:
        return self.markov_dialogue_dir / (
            f'{key.scope.value}-{key.scope_id}-dialogue.json'
        )

    async def _get_markov_dialogue(
        self,
        key: MarkovModelKey,
    ) -> MarkovDialogueMemory:
        dialogue = self.markov_dialogues.get(key)

        if dialogue is not None:
            return dialogue

        dialogue = MarkovDialogueMemory(
            self.markov_tokenizer,
        )

        file_path = self._get_markov_dialogue_path(key)

        if file_path.is_file():
            try:
                async with aiofiles.open(file_path, 'rb') as file:
                    raw = await file.read()

                loaded = orjson.loads(raw) if raw else []

                if isinstance(loaded, list):
                    for item in loaded:
                        if not isinstance(item, dict):
                            continue

                        prompt = item.get('prompt')
                        response = item.get('response')

                        if isinstance(prompt, str) and isinstance(response, str):
                            dialogue.learn(prompt, response)

            except Exception:
                self.bot.logger.exception(
                    'Failed to load Markov dialogue memory for %s/%s',
                    key.scope.value,
                    key.scope_id,
                )

        self.markov_dialogues[key] = dialogue

        return dialogue

    async def _save_markov_dialogue(
        self,
        key: MarkovModelKey,
    ) -> None:
        dialogue = self.markov_dialogues.get(key)

        if dialogue is None:
            return

        file_path = self._get_markov_dialogue_path(key)

        payload = [
            {
                'prompt': entry.prompt,
                'response': entry.response,
            }
            for entry in dialogue.entries
        ]

        try:
            async with aiofiles.open(file_path, 'wb') as file:
                await file.write(orjson.dumps(payload))

        except Exception:
            self.bot.logger.exception(
                'Failed to save Markov dialogue memory for %s/%s',
                key.scope.value,
                key.scope_id,
            )

    def _get_markov_fallback_keys(
        self,
        scope: MarkovModelScope,
        *,
        guild_id: int,
        user_id: int,
    ) -> list[MarkovModelKey]:
        match scope:
            case MarkovModelScope.GLOBAL:
                return [
                    MarkovModelKey.global_model(),
                ]

            case MarkovModelScope.SERVER:
                return [
                    MarkovModelKey.server(guild_id),
                    MarkovModelKey.global_model(),
                ]

            case MarkovModelScope.USER:
                return [
                    MarkovModelKey.user(user_id),
                    MarkovModelKey.server(guild_id),
                    MarkovModelKey.global_model(),
                ]

            case _:
                raise ValueError(
                    f'Unsupported Markov model scope: {scope!r}',
                )

    def _make_markov_key(
        self,
        scope: MarkovModelScope,
        *,
        guild_id: int | None = None,
        user_id: int | None = None,
    ) -> MarkovModelKey:
        match scope:
            case MarkovModelScope.GLOBAL:
                return MarkovModelKey.global_model()

            case MarkovModelScope.SERVER:
                if guild_id is None:
                    raise ValueError(
                        'Server Markov scope requires a guild ID.',
                    )

                return MarkovModelKey.server(guild_id)

            case MarkovModelScope.USER:
                if user_id is None:
                    raise ValueError(
                        'User Markov scope requires a user ID.',
                    )

                return MarkovModelKey.user(user_id)

            case _:
                raise ValueError(
                    f'Unsupported Markov model scope: {scope!r}',
                )

    async def _get_markov_model(
        self,
        key: MarkovModelKey,
        *,
        order: int = 2,
    ) -> MarkovModel:
        model = self.markov_models.get(key)

        if model is not None:
            if model.order == order:
                return model

            self.markov_models.pop(key, None)

        model = MarkovModel(order=order)

        await self.markov_storage.load(
            key,
            model,
        )

        self.markov_models[key] = model

        return model

    async def _save_markov_model(
        self,
        key: MarkovModelKey,
    ) -> None:
        model = self.markov_models.get(key)

        if model is None:
            return

        await self.markov_storage.save(
            key,
            model,
        )

    async def _clear_markov_model(
        self,
        key: MarkovModelKey,
    ) -> None:
        self.markov_models.pop(
            key,
            None,
        )
        self.markov_dialogues.pop(
            key,
            None,
        )

        await self.markov_storage.clear(
            key,
        )

        file_path = self._get_markov_dialogue_path(key)

        with contextlib.suppress(FileNotFoundError):
            file_path.unlink()

    # ======================================================================
    # Markov learning / generation
    # ======================================================================

    def _clean_markov_prompt(self, message: Message) -> str:
        content = message.content.strip()

        if self.bot.user:
            content = content.replace(
                f'<@{self.bot.user.id}>',
                '',
            ).replace(
                f'<@!{self.bot.user.id}>',
                '',
            )

        return ' '.join(content.split())

    async def learn_markov_message(
        self,
        message: Message,
        *,
        scope: MarkovModelScope,
        order: int = 2,
    ) -> None:
        if not message.guild or message.author.bot:
            return

        content = message.content.strip()

        if not content:
            return

        if content.startswith(self.bot.settings.bot_prefix):
            return

        tokens = self.markov_tokenizer.tokenize(content)

        if not tokens:
            return

        key = self._make_markov_key(
            scope,
            guild_id=message.guild.id,
            user_id=message.author.id,
        )

        model = await self._get_markov_model(
            key,
            order=order,
        )

        model.train(tokens)

        await self._save_markov_model(key)

    async def _generate_markov_from_key(
        self,
        key: MarkovModelKey,
        *,
        prompt: str = '',
        max_tokens: int = 50,
        order: int = 2,
    ) -> MarkovGenerationResult | None:
        model = await self._get_markov_model(
            key,
            order=order,
        )

        if model.message_count <= 0:
            return None

        generator = MarkovGenerator(
            model,
            self.markov_tokenizer,
        )

        response = generator.generate(
            max_tokens=max_tokens,
            seed=prompt,
        )

        if not response:
            response = generator.generate(
                max_tokens=max_tokens,
            )

        if not response:
            return None

        return MarkovGenerationResult(
            response=response.strip(),
            key=key,
        )

    async def _find_markov_dialogue_response(
        self,
        key: MarkovModelKey,
        prompt: str,
    ) -> str | None:
        dialogue = await self._get_markov_dialogue(key)
        return dialogue.find(prompt)

    async def generate_markov_response(
        self,
        message: Message,
        *,
        scope: MarkovModelScope,
        max_tokens: int = 50,
        order: int = 2,
    ) -> MarkovGenerationResult | None:
        if not message.guild:
            return None

        primary_key = self._make_markov_key(
            scope,
            guild_id=message.guild.id,
            user_id=message.author.id,
        )

        prompt = self._clean_markov_prompt(message)

        learned_response = await self._find_markov_dialogue_response(
            primary_key,
            prompt,
        )

        if learned_response:
            return MarkovGenerationResult(
                response=learned_response,
                key=primary_key,
            )

        fallback_keys = self._get_markov_fallback_keys(
            scope,
            guild_id=message.guild.id,
            user_id=message.author.id,
        )

        for key in fallback_keys:
            result = await self._generate_markov_from_key(
                key,
                prompt=prompt,
                max_tokens=max_tokens,
                order=order,
            )

            if result is not None:
                return result

        return None

    # ======================================================================
    # AI message formatting / history
    # ======================================================================

    async def format_discord_message(
        self,
        message: Message,
    ) -> dict[str, Any]:
        message_content = message.content.strip() if message.content else ''

        if message_content and self.bot.user:
            message_content = message_content.replace(
                f'<@{self.bot.user.id}> ',
                '',
            ).replace(
                f'<@!{self.bot.user.id}> ',
                '',
            )

        role_type = 'assistant' if message.author == self.bot.user else 'user'

        formatted_message_author = message.author.display_name

        formatted_message_content = (
            message_content if message_content else 'Empty message'
        )

        if message.attachments:
            attachments = ', '.join(
                attachment.filename for attachment in message.attachments
            )

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

        return {
            'role': role_type,
            'content': role_content,
        }

    def _sanitize_history_item(
        self,
        item: Any,
    ) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {
                'role': 'assistant',
                'content': str(item),
            }

        role = str(item.get('role', 'assistant'))
        content = item.get('content', '')

        if asyncio.iscoroutine(content):
            content = '<coroutine>'

        return {
            'role': role,
            'content': str(content),
        }

    async def populate_channel_cache(
        self,
        channel: Messageable,
        limit: int = 10,
    ) -> None:
        channel_id = getattr(channel, 'id', 0)

        if channel_id == 0:
            return

        if channel_id not in self.history:
            self.history[channel_id] = deque(
                maxlen=self.history_limit,
            )

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
                    'Failed to load persisted history for channel %s',
                    channel_id,
                )

        try:
            fetched_messages = [
                message
                async for message in channel.history(
                    limit=limit,
                    oldest_first=False,
                )
            ]

            for message in reversed(fetched_messages):
                data = await self.format_discord_message(message)
                sanitized = self._sanitize_history_item(data)

                if sanitized not in self.history[channel_id]:
                    self.history[channel_id].append(sanitized)

        except Exception:
            self.bot.logger.exception(
                'Failed to populate channel cache',
            )

        await self._save_history(channel_id)

    # ======================================================================
    # AI response
    # ======================================================================

    async def respond(
        self,
        message: Message,
        provider: str,
        model: str,
        include_history: bool = False,
    ) -> None:
        if not self.bot.user:
            raise RuntimeError('Bot user is not set')

        now = datetime.now(UTC)

        user_cd = self.cooldowns.get(message.author.id)

        if user_cd:
            elapsed = now - user_cd
            cooldown_left = self.cooldown_seconds - elapsed

            if cooldown_left.total_seconds() > 0:
                remaining = max(
                    1,
                    round(cooldown_left.total_seconds()),
                )

                with contextlib.suppress(Exception):
                    await message.reply(
                        (
                            'You are on cooldown. '
                            f'Please retry after {remaining} seconds'
                        ),
                        allowed_mentions=AllowedMentions.none(),
                    )

                return

        if len(self.cooldowns) > 1000:
            self.cooldowns = {
                user_id: timestamp
                for user_id, timestamp in self.cooldowns.items()
                if now - timestamp < self.cooldown_seconds
            }

        lock = self.locks.setdefault(
            message.channel.id,
            asyncio.Lock(),
        )

        async with lock:
            if message.channel.id not in self.history:
                await self.populate_channel_cache(
                    message.channel,
                )

            messages = [
                {
                    'role': 'system',
                    'content': 'You are a helpful assistant.',
                },
            ]

            current_msg_data = self._sanitize_history_item(
                await self.format_discord_message(message),
            )

            is_duplicate = any(
                h['content'] == current_msg_data['content']
                and h['role'] == current_msg_data['role']
                for h in self.history[message.channel.id]
            )

            if not is_duplicate:
                self.history[message.channel.id].append(
                    current_msg_data,
                )
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

                    self.bot.logger.exception(
                        'Failed to generate response',
                    )

                    await message.channel.send(
                        embed=embed,
                        allowed_mentions=AllowedMentions.none(),
                    )
                    return

                output = output.strip()

                if not output:
                    raise RuntimeError(
                        'AI returned an empty response.',
                    )

                output = output.replace(
                    '{author_name}',
                    message.author.display_name or 'User',
                )

                output = output.replace(
                    '{author_mention}',
                    message.author.mention,
                )

                is_reply = output.startswith('[REPLY]')
                send_content = output[7:] if is_reply else output

                if len(send_content) > 2000:
                    chunks = [
                        send_content[i : i + 2000]
                        for i in range(
                            0,
                            len(send_content),
                            2000,
                        )
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

                elif is_reply:
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
                    self._sanitize_history_item(
                        {
                            'role': 'assistant',
                            'content': output,
                        },
                    ),
                )

                await self._save_history(message.channel.id)

    # ======================================================================
    # Trigger handling
    # ======================================================================

    def is_matching(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.trigger_patterns)

    def _is_triggered(self, message: Message) -> bool:
        if not self.bot.user:
            return False

        if self.bot.user in message.mentions and not message.mention_everyone:
            return True

        return self.is_matching(message.content)

    def _is_markov_triggered(self, message: Message) -> bool:
        if not self.bot.user:
            return False

        return self.bot.user in message.mentions and not message.mention_everyone

    # ======================================================================
    # Message listener
    # ======================================================================

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if message.author.bot or not message.guild or not self.bot.user:
            return

        if not self.database:
            return

        if message.content.startswith(
            self.bot.settings.bot_prefix,
        ):
            return

        guild_settings = await self.database.get_config(
            message.guild.id,
        )

        chatbot = guild_settings.chatbot

        if not chatbot.enabled:
            return

        match chatbot.type:
            # --------------------------------------------------------------
            # AI
            # --------------------------------------------------------------

            case ChatbotMethodType.ai:
                if not self._is_triggered(message):
                    return

                member = message.guild.me or message.guild.get_member(
                    self.bot.user.id,
                )

                if not member:
                    return

                permissions = message.channel.permissions_for(
                    member,
                )

                if not permissions.send_messages:
                    return

                await self.respond(
                    message=message,
                    provider=LLMProviderType.OPEN_ROUTER.value,
                    model=self.bot.settings.llm_config.model_id,
                    include_history=permissions.read_message_history,
                )

            # --------------------------------------------------------------
            # Markov
            # --------------------------------------------------------------

            case ChatbotMethodType.markov_chain:
                await self.learn_markov_message(
                    message,
                    scope=chatbot.markov_scope,
                    order=chatbot.markov_order,
                )

                if not self._is_markov_triggered(message):
                    return

                member = message.guild.me or message.guild.get_member(
                    self.bot.user.id,
                )

                if not member:
                    return

                permissions = message.channel.permissions_for(
                    member,
                )

                if not permissions.send_messages:
                    return

                result = await self.generate_markov_response(
                    message,
                    scope=chatbot.markov_scope,
                    max_tokens=chatbot.markov_max_tokens,
                    order=chatbot.markov_order,
                )

                if result is None:
                    return

                response = result.response

                self.bot.logger.debug(
                    'Generated Markov response using %s/%s',
                    result.key.scope.value,
                    result.key.scope_id,
                )

                await message.reply(
                    response[:2000],
                    allowed_mentions=AllowedMentions.none(),
                )

                key = self._make_markov_key(
                    chatbot.markov_scope,
                    guild_id=message.guild.id,
                    user_id=message.author.id,
                )

                dialogue = await self._get_markov_dialogue(key)
                dialogue.learn(
                    self._clean_markov_prompt(message),
                    response,
                )
                await self._save_markov_dialogue(key)

            case _:
                return

    # ======================================================================
    # /chatbot status
    # ======================================================================

    @chatbot_group.command(
        name='status',
        description='Show the current chatbot configuration',
    )
    @app_commands.guild_only()
    async def chatbot_status(
        self,
        interaction: Interaction,
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot

        await interaction.response.send_message(
            (
                '**Chatbot**\n'
                f'Enabled: `{chatbot.enabled}`\n'
                f'Mode: `{chatbot.type.name}`\n'
                f'Markov scope: `{chatbot.markov_scope.value}`\n'
                f'Markov order: `{chatbot.markov_order}`\n'
                f'Max tokens: `{chatbot.markov_max_tokens}`'
            ),
            ephemeral=True,
        )

    # ======================================================================
    # /chatbot generate
    # ======================================================================

    @chatbot_group.command(
        name='generate',
        description='Generate a response from the Markov model',
    )
    @app_commands.guild_only()
    @app_commands.describe(
        max_tokens='Maximum number of generated tokens',
    )
    async def chatbot_generate(
        self,
        interaction: Interaction,
        max_tokens: app_commands.Range[int, 1, 200] = 50,
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot

        if chatbot.type != ChatbotMethodType.markov_chain:
            await interaction.response.send_message(
                ('The chatbot is not currently using Markov Chain mode.'),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        key = self._make_markov_key(
            chatbot.markov_scope,
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        model = await self._get_markov_model(
            key,
            order=chatbot.markov_order,
        )

        if model.message_count <= 0:
            await interaction.followup.send(
                'The Markov model has not learned any messages yet.',
                ephemeral=True,
            )
            return

        result = None

        fallback_keys = self._get_markov_fallback_keys(
            chatbot.markov_scope,
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        for key in fallback_keys:
            result = await self._generate_markov_from_key(
                key,
                max_tokens=max_tokens,
                order=chatbot.markov_order,
            )

            if result is not None:
                break

        if result is None:
            await interaction.followup.send(
                'No Markov model in the fallback chain has learned any messages yet.',
                ephemeral=True,
            )
            return

        self.bot.logger.debug(
            'Generated Markov command response using %s/%s',
            result.key.scope.value,
            result.key.scope_id,
        )

        await interaction.followup.send(
            result.response[:2000],
            allowed_mentions=AllowedMentions.none(),
        )

    # ======================================================================
    # /chatbot clear
    # ======================================================================

    @chatbot_group.command(
        name='clear',
        description='Clear the Markov model',
    )
    @app_commands.guild_only()
    @commands.is_owner()
    async def chatbot_clear(
        self,
        interaction: Interaction,
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot

        key = self._make_markov_key(
            chatbot.markov_scope,
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        await self._clear_markov_model(key)

        await interaction.response.send_message(
            'The Markov model has been cleared.',
            ephemeral=True,
        )

    # ======================================================================
    # /chatbot clear_server
    # ======================================================================

    @chatbot_group.command(
        name='clear_server',
        description="Clear this server's Markov model and dialogue history",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def chatbot_clear_server(
        self,
        interaction: Interaction,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        key = MarkovModelKey.server(
            interaction.guild.id,
        )

        await self._clear_markov_model(key)

        await interaction.response.send_message(
            "This server's Markov model and dialogue history have been cleared.",
            ephemeral=True,
        )

    # ======================================================================
    # /chatbot clear_history
    # ======================================================================

    @chatbot_group.command(
        name='clear_history',
        description="Clear this server's AI conversation history",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def chatbot_clear_history(
        self,
        interaction: Interaction,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        channel_ids = {channel.id for channel in interaction.guild.channels}

        # Remove cached history for this server.
        for channel_id in channel_ids:
            self.history.pop(channel_id, None)

        # Remove persisted history files.
        cleared_files = 0

        for channel_id in channel_ids:
            file_path = self._get_file_path(channel_id)

            if not file_path.is_file():
                continue

            with contextlib.suppress(OSError):
                file_path.unlink()
                cleared_files += 1

        await interaction.response.send_message(
            (f'Cleared AI conversation history for {cleared_files} channel(s).'),
            ephemeral=True,
        )

    # ======================================================================
    # /chatbot stats
    # ======================================================================

    @chatbot_group.command(
        name='stats',
        description='Show Markov model statistics',
    )
    @app_commands.guild_only()
    async def chatbot_stats(
        self,
        interaction: Interaction,
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot

        key = self._make_markov_key(
            chatbot.markov_scope,
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        model = await self._get_markov_model(
            key,
            order=chatbot.markov_order,
        )

        dialogue = await self._get_markov_dialogue(key)

        await interaction.response.send_message(
            (
                '**Markov Statistics**\n'
                f'Scope: `{key.scope.value}`\n'
                f'Scope ID: `{key.scope_id}`\n'
                f'Order: `{model.order}`\n'
                f'Messages: `{model.message_count:,}`\n'
                f'Tokens: `{model.token_count:,}`\n'
                f'States: `{model.state_count:,}`\n'
                f'Dialogue pairs: `{len(dialogue.entries):,}`'
            ),
            ephemeral=True,
        )

    @chatbot_group.command(
        name='mode',
        description='Change the chatbot mode',
    )
    @app_commands.guild_only()
    @app_commands.describe(
        mode='The chatbot mode to use',
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(
                name='AI',
                value='ai',
            ),
            app_commands.Choice(
                name='Markov Chain',
                value='markov_chain',
            ),
        ],
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def chatbot_mode(
        self,
        interaction: Interaction,
        mode: app_commands.Choice[str],
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot

        new_mode = ChatbotMethodType[mode.value]

        if chatbot.type == new_mode:
            await interaction.response.send_message(
                f'Chatbot mode is already `{mode.name}`.',
                ephemeral=True,
            )
            return

        chatbot.type = new_mode

        # TODO: Replace this with your actual config persistence method.
        #
        # Example:
        # await self.database.save_config(
        #     interaction.guild.id,
        #     config,
        # )
        await self.database.update_config(
            interaction.guild.id,
            config,
        )

        await interaction.response.send_message(
            f'Chatbot mode changed to `{mode.name}`.',
            ephemeral=True,
        )

    # ======================================================================
    # /chatbot toggle
    # ======================================================================

    @chatbot_group.command(
        name='toggle',
        description='Enable or disable the chatbot',
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def chatbot_toggle(
        self,
        interaction: Interaction,
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot
        chatbot.enabled = not chatbot.enabled

        await self.database.update_config(
            interaction.guild.id,
            config,
        )

        state = 'enabled' if chatbot.enabled else 'disabled'

        await interaction.response.send_message(
            f'Chatbot has been **{state}**.',
            ephemeral=True,
        )

    # ======================================================================
    # /chatbot scope
    # ======================================================================

    @chatbot_group.command(
        name='scope',
        description='Change which Markov model scope the chatbot uses',
    )
    @app_commands.guild_only()
    @app_commands.describe(
        scope='The Markov model scope to use',
    )
    @app_commands.choices(
        scope=[
            app_commands.Choice(
                name='Global',
                value='global',
            ),
            app_commands.Choice(
                name='Server',
                value='server',
            ),
            app_commands.Choice(
                name='User',
                value='user',
            ),
        ],
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def chatbot_scope(
        self,
        interaction: Interaction,
        scope: app_commands.Choice[str],
    ) -> None:
        if not self.database or not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        config = await self.database.get_config(
            interaction.guild.id,
        )

        chatbot = config.chatbot
        new_scope = MarkovModelScope(scope.value)

        if chatbot.markov_scope == new_scope:
            await interaction.response.send_message(
                f'Markov model scope is already `{scope.name}`.',
                ephemeral=True,
            )
            return

        chatbot.markov_scope = new_scope

        await self.database.update_config(
            interaction.guild.id,
            config,
        )

        await interaction.response.send_message(
            f'Markov model scope changed to `{scope.name}`.',
            ephemeral=True,
        )


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(ChatbotCog(bot))
