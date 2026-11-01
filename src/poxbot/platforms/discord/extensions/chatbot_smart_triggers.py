from __future__ import annotations

from datetime import datetime, timedelta

from discord import Message
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot
from ....features.chatbot.trigger import SmartTriggerEvaluator, TriggerReason
from ....services.ai import LLMProviderType
from .chatbot import ChatbotCog


class SmartChatbotTriggersCog(commands.Cog):
    """Add conservative conversational triggers to the existing chatbot."""

    cooldown = timedelta(seconds=10)
    history_window = 6

    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot
        self._cooldowns: dict[int, datetime] = {}

    def _get_chatbot(self) -> ChatbotCog | None:
        cog = self.bot.get_cog('ChatbotCog')
        return cog if isinstance(cog, ChatbotCog) else None

    def _recent_bot_activity(self, chatbot: ChatbotCog, message: Message) -> bool:
        history = chatbot.history.get(message.channel.id)
        if not history:
            return False

        return any(
            isinstance(item, dict) and item.get('role') == 'assistant'
            for item in list(history)[-self.history_window :]
        )

    def _on_cooldown(self, user_id: int) -> bool:
        timestamp = self._cooldowns.get(user_id)
        if timestamp is None:
            return False
        return datetime.now(UTC) - timestamp < self.cooldown

    def _mark_cooldown(self, user_id: int) -> None:
        now = datetime.now(UTC)
        self._cooldowns[user_id] = now

        if len(self._cooldowns) > 1000:
            self._cooldowns = {
                user_id: timestamp
                for user_id, timestamp in self._cooldowns.items()
                if now - timestamp < self.cooldown
            }

    def _evaluator(self) -> SmartTriggerEvaluator:
        if not self.bot.user:
            raise RuntimeError('Bot user is not set')

        names = tuple(
            name
            for name in (
                self.bot.user.name,
                getattr(self.bot.user, 'global_name', None),
                'pox',
                'p0x38',
            )
            if isinstance(name, str) and name.strip()
        )

        return SmartTriggerEvaluator(
            bot_user_id=self.bot.user.id,
            bot_names=names,
            threshold=0.75,
        )

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if message.author.bot or not message.guild or not self.bot.user:
            return

        if message.content.startswith(self.bot.settings.bot_config.bot_prefix):
            return

        chatbot = self._get_chatbot()
        if chatbot is None or chatbot.database is None:
            return

        config = await chatbot.database.get_config(message.guild.id)
        if not config.chatbot.enabled:
            return

        decision = self._evaluator().evaluate(
            message,
            recent_bot_activity=self._recent_bot_activity(chatbot, message),
        )

        # The normal chatbot listener already handles explicit mentions and
        # name-based triggers. This extension only adds contextual triggers.
        if decision.reason not in {TriggerReason.REPLY, TriggerReason.QUESTION}:
            return

        chatbot.bot.logger.debug(
            'Smart chatbot trigger: reason=%s score=%.2f channel=%s user=%s',
            decision.reason.name.lower(),
            decision.score,
            message.channel.id,
            message.author.id,
        )

        if self._on_cooldown(message.author.id):
            return

        member = message.guild.me or message.guild.get_member(self.bot.user.id)
        if not member:
            return

        permissions = message.channel.permissions_for(member)
        if not permissions.send_messages:
            return

        provider = self.bot.settings.llm_config.provider_type

        if provider not in {item.value for item in LLMProviderType}:
            chatbot.bot.logger.error(
                'Unsupported LLM provider configured: %s',
                provider,
            )
            return

        await chatbot.respond(
            message=message,
            provider=provider,
            model=self.bot.settings.llm_config.model_id,
            include_history=permissions.read_message_history,
        )

        self._mark_cooldown(message.author.id)


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(SmartChatbotTriggersCog(bot))
