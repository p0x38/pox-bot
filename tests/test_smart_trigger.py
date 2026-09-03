"""Tests for the smart chatbot trigger evaluator."""
from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from discord import Message

from poxbot.features.chatbot.trigger import SmartTriggerEvaluator, TriggerReason


def make_message(
    *,
    content: str = '',
    mentions: tuple[object, ...] = (),
    mention_everyone: bool = False,
    reply_author_id: int | None = None,
    author_bot: bool = False,
) -> Message:
    """Create a minimal Discord-like message for testing."""
    resolved = None

    if reply_author_id is not None:
        resolved = SimpleNamespace(
            author=SimpleNamespace(id=reply_author_id),
        )

    message = SimpleNamespace(
        author=SimpleNamespace(bot=author_bot),
        content=content,
        mentions=list(mentions),
        mention_everyone=mention_everyone,
        reference=SimpleNamespace(resolved=resolved),
    )

    return cast(Message, message)


def test_mention_has_highest_priority() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )

    decision = evaluator.evaluate(
        make_message(
            content='what are you doing?',
            mentions=(SimpleNamespace(id=123),),
        ),
    )

    assert decision.reason is TriggerReason.MENTION
    assert decision.score == pytest.approx(1.0)
    assert decision.should_respond


def test_reply_triggers_without_bot_name() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )

    decision = evaluator.evaluate(
        make_message(
            content='yeah that makes sense',
            reply_author_id=123,
        ),
    )

    assert decision.reason is TriggerReason.REPLY
    assert decision.should_respond


def test_question_requires_recent_bot_context() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )
    message = make_message(content='what is this?')

    without_context = evaluator.evaluate(message)
    with_context = evaluator.evaluate(
        message,
        recent_bot_activity=True,
    )

    assert without_context.reason is TriggerReason.NONE
    assert not without_context.should_respond

    assert with_context.reason is TriggerReason.QUESTION
    assert with_context.should_respond


def test_unrelated_message_does_not_trigger() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )

    decision = evaluator.evaluate(
        make_message(content='hello everyone'),
    )

    assert decision.reason is TriggerReason.NONE
    assert not decision.should_respond


def test_threshold_suppresses_weak_context() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        threshold=0.75,
    )

    decision = evaluator.evaluate(
        make_message(content='hello'),
        recent_bot_activity=True,
    )

    assert decision.reason is TriggerReason.NONE
    assert not decision.should_respond
