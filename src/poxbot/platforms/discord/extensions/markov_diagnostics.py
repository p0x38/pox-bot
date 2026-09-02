from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, cast

from discord import Message

from ....application import PoxBot
from ....persistence.models.guild_settings_v2 import MarkovModelScope
from .chatbot import ChatbotCog

OriginalLearnMarkovMessage = Callable[..., Awaitable[None]]


_original_learn_markov_message = cast(
    OriginalLearnMarkovMessage,
    ChatbotCog.learn_markov_message,
)


@wraps(_original_learn_markov_message)
async def _learn_markov_message_with_logging(
    self: ChatbotCog,
    message: Message,
    *,
    scope: MarkovModelScope,
    order: int = 2,
) -> None:
    tokens = self.markov_tokenizer.tokenize(message.content.strip())

    self.bot.logger.debug(
        '[MARKOV] Learning message: scope=%s scope_id=%s user_id=%s '
        'tokens=%d order=%d',
        scope.value,
        message.guild.id if message.guild else None,
        message.author.id,
        len(tokens),
        order,
    )

    await _original_learn_markov_message(
        self,
        message,
        scope=scope,
        order=order,
    )

    self.bot.logger.debug(
        '[MARKOV] Learning completed: scope=%s scope_id=%s user_id=%s',
        scope.value,
        message.guild.id if message.guild else None,
        message.author.id,
    )


if ChatbotCog.learn_markov_message is _original_learn_markov_message:
    ChatbotCog.learn_markov_message = cast(
        Any,
        _learn_markov_message_with_logging,
    )


async def setup(bot: PoxBot) -> None:
    """Install Markov learning diagnostics on the chatbot cog."""
    del bot
