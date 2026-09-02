from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

from discord import Message


class TriggerReason(IntEnum):
    """Relative strength of a chatbot response trigger."""

    NONE = 0
    CONTEXT = 1
    NAME = 2
    QUESTION = 3
    REPLY = 4
    MENTION = 5


@dataclass(frozen=True, slots=True)
class TriggerDecision:
    """Result of evaluating whether a message should trigger the bot."""

    reason: TriggerReason = TriggerReason.NONE
    score: float = 0.0

    @property
    def should_respond(self) -> bool:
        return self.reason is not TriggerReason.NONE


class SmartTriggerEvaluator:
    """Evaluate Discord messages for direct and conversational bot triggers."""

    _QUESTION_PATTERN = re.compile(
        r"(?:^|[\s,;:!?])"
        r"(?:who|what|when|where|why|how|can|could|would|will|do|does|did|"
        r"is|are|am|should|tell|explain)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        bot_user_id: int,
        bot_names: tuple[str, ...] = (),
        threshold: float = 0.75,
    ) -> None:
        self.bot_user_id = bot_user_id
        self.bot_names = tuple(
            name.casefold() for name in bot_names if name.strip()
        )
        self.threshold = max(0.0, min(1.0, threshold))

    def evaluate(self, message: Message) -> TriggerDecision:
        if message.author.bot:
            return TriggerDecision()

        if self._is_direct_mention(message):
            return TriggerDecision(TriggerReason.MENTION, 1.0)

        if self._is_reply_to_bot(message):
            return TriggerDecision(TriggerReason.REPLY, 0.95)

        content = message.content.strip()
        if not content:
            return TriggerDecision()

        if self._contains_bot_name(content):
            return TriggerDecision(TriggerReason.NAME, 0.9)

        if self._is_question(content):
            return TriggerDecision(TriggerReason.QUESTION, 0.8)

        return TriggerDecision()

    def _is_direct_mention(self, message: Message) -> bool:
        return (
            not message.mention_everyone
            and any(user.id == self.bot_user_id for user in message.mentions)
        )

    def _is_reply_to_bot(self, message: Message) -> bool:
        reference = message.reference
        resolved = reference.resolved if reference else None
        return isinstance(resolved, Message) and resolved.author.id == self.bot_user_id

    def _contains_bot_name(self, content: str) -> bool:
        normalized = content.casefold()
        return any(
            re.search(rf"\b{re.escape(name)}\b", normalized)
            for name in self.bot_names
        )

    def _is_question(self, content: str) -> bool:
        return content.endswith("?") or bool(self._QUESTION_PATTERN.search(content))
