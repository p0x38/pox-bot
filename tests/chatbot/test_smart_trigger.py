from math import isclose
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    message = MagicMock(spec=Message)

    author = MagicMock()
    author.bot = author_bot

    message.author = author
    message.content = content
    message.mentions = list(mentions)
    message.mention_everyone = mention_everyone

    if reply_author_id is None:
        message.reference = None
    else:
        reference = MagicMock()
        resolved = MagicMock()
        resolved.author.id = reply_author_id
        reference.resolved = resolved
        message.reference = reference

    return message


def test_mention_is_highest_priority() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )
    message = make_message(
        content='what are you doing?',
        mentions=(SimpleNamespace(id=123),),
    )

    decision = evaluator.evaluate(message)

    assert decision.reason is TriggerReason.MENTION
    assert isclose(decision.score, 1.0, rel_tol=1e-9, abs_tol=1e-9)


def test_reply_triggers_without_bot_name() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )
    message = make_message(
        content='yeah that makes sense',
        reply_author_id=123,
    )

    decision = evaluator.evaluate(message)

    assert decision.reason is TriggerReason.REPLY
    assert decision.should_respond


def test_question_requires_recent_bot_context() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )
    message = make_message(content='what is this?')

    assert evaluator.evaluate(message).reason is TriggerReason.NONE
    assert (
        evaluator.evaluate(message, recent_bot_activity=True).reason
        is TriggerReason.QUESTION
    )


def test_unrelated_message_does_not_trigger() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        bot_names=('poxbot',),
    )

    decision = evaluator.evaluate(make_message(content='hello everyone'))

    assert decision.reason is TriggerReason.NONE
    assert not decision.should_respond


def test_threshold_suppresses_context_only() -> None:
    evaluator = SmartTriggerEvaluator(
        bot_user_id=123,
        threshold=0.75,
    )

    decision = evaluator.evaluate(
        make_message(content='hello'),
        recent_bot_activity=True,
    )

    assert decision.reason is TriggerReason.NONE
