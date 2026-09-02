from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

from discord import Message


class TriggerReason(IntEnum):
    """Relative strength of a chatbot response trigger."""

    NONE = 0
    CONTEXT = 1
    QUESTION = 2
    REPLY = 3
    NAME = 4
    MENTION = 5


@dataclass(frozen=True, slots=True)
class TriggerDecision:
    """Result of evaluating whether a message should trigger the bot."""

    reason: TriggerReason = TriggerReason.NONE
    score: float = 0.0

    @property
    def should_respond(self) -> bool:
        """Return whether this decision requests a response."""
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

    def evaluate(
        self,
        message: Message,
        *,
        recent_bot_activity: bool = False,
    ) -> TriggerDecision:
        if message.author.bot:
            return TriggerDecision()

        candidates: list[TriggerDecision] = []

        if self._is_direct_mention(message):
            candidates.append(TriggerDecision(TriggerReason.MENTION, 1.0))

        if self._is_reply_to_bot(message):
            candidates.append(TriggerDecision(TriggerReason.REPLY, 0.95))

        content = message.content.strip()
        if not content:
            return self._best(candidates)

        # Name references outrank reply/question signals so the existing
        # chatbot listener remains the sole handler for name-based triggers.
        if self._contains_bot_name(content):
            candidates.append(TriggerDecision(TriggerReason.NAME, 0.96))

        # A question by itself is intentionally not enough. Recent bot activity
        # provides the conversational context needed to avoid replying to every
        # unrelated question in a busy channel.
        if self._is_question(content) and recent_bot_activity:
            candidates.append(TriggerDecision(TriggerReason.QUESTION, 0.8))

        if recent_bot_activity and not candidates:
            candidates.append(TriggerDecision(TriggerReason.CONTEXT, 0.65))

        return self._best(candidates)

    def _best(self, candidates: list[TriggerDecision]) -> TriggerDecision:
        if not candidates:
            return TriggerDecision()

        decision = max(candidates, key=lambda item: item.score)
        if decision.score < self.threshold:
            return TriggerDecision()

        return decision

    def _is_direct_mention(self, message: Message) -> bool:
        return (
            not message.mention_everyone
            and any(user.id == self.bot_user_id for user in message.mentions)
        )

    def _is_reply_to_bot(self, message: Message) -> bool:
        reference = message.reference
        resolved = reference.resolved if reference else None
        author = getattr(resolved, 'author', None)
        return getattr(author, 'id', None) == self.bot_user_id

    def _contains_bot_name(self, content: str) -> bool:
        normalized = content.casefold()
        return any(
            re.search(rf"\b{re.escape(name)}\b", normalized)
            for name in self.bot_names
        )

    def _is_question(self, content: str) -> bool:
        return content.endswith('?') or bool(self._QUESTION_PATTERN.search(content))
