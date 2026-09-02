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
from ....features.markov.generator import MarkovGenerator
from ....features.markov.model import MarkovModel
from ....features.markov.storage import MarkovDatabase
from ....features.markov.tokenizer import MarkovTokenizer
from ....persistence.models.guild_settings_v2 import ChatbotMethodType
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
        self.markov_models: dict[int, MarkovModel] = {}

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

    async def _get_markov_model(
        self,
        guild_id: int,
        *,
        order: int = 2,
    ) -> MarkovModel:
        model = self.markov_models.get(guild_id)

        if model is not None:
            if model.order == order:
                return model

            self.markov_models.pop(guild_id, None)

        model = MarkovModel(order=order)

        await self.markov_storage.load(
            guild_id,
            model,
        )

        self.markov_models[guild_id] = model

        return model

    async def _save_markov_model(
        self,
        guild_id: int,
    ) -> None:
        model = self.markov_models.get(guild_id)

        if model is None:
            return

        await self.markov_storage.save(
            guild_id,
            model,
        )

    async def _clear_markov_model(
        self,
        guild_id: int,
    ) -> None:
        self.markov_models.pop(
            guild_id,
            None,
        )

        await self.markov_storage.clear(
            guild_id,
        )
    
    # ======================================================================
    # Markov learning / generation
    # ======================================================================

    async def learn_markov_message(
        self,
        message: Message,
        *,
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

        model = await self._get_markov_model(
            message.guild.id,
            order=order,
        )

        model.train(tokens)

        await self._save_markov_model(
            message.guild.id,
        )

    async def generate_markov_response(
        self,
        message: Message,
        *,
        max_tokens: int = 50,
        order: int = 2,
    ) -> str | None:
        if not message.guild:
            return None

        model = await self._get_markov_model(
            message.guild.id,
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
            seed=message.content,
        )

        if not response:
            response = generator.generate(
                max_tokens=max_tokens,
            )

        return response.strip() if response else None

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
                # Learn from every normal message while Markov mode is
                # enabled, not only messages directed at the bot.
                await self.learn_markov_message(
                    message,
                    order=chatbot.markov_order,
                )

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

                response = await self.generate_markov_response(
                    message,
                    max_tokens=chatbot.markov_max_tokens,
                    order=chatbot.markov_order,
                )

                if not response:
                    return

                await message.reply(
                    response[:2000],
                    allowed_mentions=AllowedMentions.none(),
                )

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

        model = await self._get_markov_model(
            interaction.guild.id,
            order=chatbot.markov_order,
        )

        if model.message_count <= 0:
            await interaction.followup.send(
                'The Markov model has not learned any messages yet.',
                ephemeral=True,
            )
            return

        generator = MarkovGenerator(
            model,
            self.markov_tokenizer,
        )

        response = generator.generate(
            max_tokens=max_tokens,
        )

        if not response:
            await interaction.followup.send(
                'I could not generate a response from the model.',
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            response[:2000],
            allowed_mentions=AllowedMentions.none(),
        )

    # ======================================================================
    # /chatbot clear
    # ======================================================================

    @chatbot_group.command(
        name='clear',
        description='Clear the Markov model for this server',
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def chatbot_clear(
        self,
        interaction: Interaction,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                'This command can only be used in a server.',
                ephemeral=True,
            )
            return

        await self._clear_markov_model(
            interaction.guild.id,
        )

        await interaction.response.send_message(
            'The Markov model has been cleared.',
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


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(ChatbotCog(bot))
