from __future__ import annotations

import asyncio
from collections import OrderedDict

from discord import AllowedMentions, Interaction, app_commands
from discord.ext import commands
from pygent import Agent
from pygent.memory import ConversationMemory
from pygent.providers.openrouter import OpenRouterProvider

from ....application import PoxBot


class PygentCog(commands.Cog):
    """Discord integration for the Pygent agent runtime."""

    MAX_CONVERSATIONS = 100
    MAX_MESSAGES = 25

    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot
        self._memories: OrderedDict[int, ConversationMemory] = OrderedDict()
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_memory(self, channel_id: int) -> ConversationMemory:
        memory = self._memories.get(channel_id)
        if memory is None:
            memory = ConversationMemory(conversation_id=str(channel_id))
            self._memories[channel_id] = memory
        else:
            self._memories.move_to_end(channel_id)

        while len(self._memories) > self.MAX_CONVERSATIONS:
            self._memories.popitem(last=False)

        return memory

    @classmethod
    def _trim_memory(cls, memory: ConversationMemory) -> None:
        if len(memory.current_messages) <= cls.MAX_MESSAGES:
            return

        memory.current_messages = memory.current_messages[-cls.MAX_MESSAGES :]
        memory.history[memory.conversation_id] = list(memory.current_messages)

    def _create_agent(self, model: str) -> Agent:
        token_config = self.bot.settings.token_config
        api_key = None

        if token_config and token_config.openrouter_api_key:
            api_key = token_config.openrouter_api_key.get_secret_value()

        provider = OpenRouterProvider(
            model,
            api_key=api_key,
            app_name="pox-bot",
        )

        return Agent(
            provider,
            max_iterations=4,
            max_tool_calls=8,
            total_timeout=60.0,
        )

    @app_commands.command(
        name="pygent",
        description="Ask the Pygent AI agent a question",
    )
    @app_commands.guild_only()
    @app_commands.describe(prompt="The prompt to send to Pygent")
    async def pygent_command(
        self,
        interaction: Interaction,
        prompt: str,
    ) -> None:
        """Run a prompt through Pygent using the configured OpenRouter model."""
        await interaction.response.defer()

        channel_id = interaction.channel_id
        lock = self._locks.setdefault(channel_id, asyncio.Lock())

        async with lock:
            memory = self._get_memory(channel_id)
            model = self.bot.settings.llm_config.model_id
            agent = self._create_agent(model)

            memory.set_conversation(str(channel_id))
            agent.memory = memory
            self._trim_memory(memory)

            try:
                response = await agent.run(prompt)
            except Exception:
                self.bot.logger.exception(
                    "Pygent request failed | channel=%s | model=%s",
                    channel_id,
                    model,
                )
                await interaction.followup.send(
                    "Pygent failed to generate a response.",
                    allowed_mentions=AllowedMentions.none(),
                )
                return

            self._trim_memory(memory)
            content = response.text.strip()

            if not content:
                await interaction.followup.send(
                    "Pygent returned an empty response.",
                    allowed_mentions=AllowedMentions.none(),
                )
                return

            for offset in range(0, len(content), 2000):
                await interaction.followup.send(
                    content[offset : offset + 2000],
                    allowed_mentions=AllowedMentions.none(),
                )


async def setup(bot: PoxBot) -> None:
    """Load the Pygent Discord integration."""
    await bot.add_cog(PygentCog(bot))
