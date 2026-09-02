from types import SimpleNamespace

from poxbot.features.chatbot.trigger import SmartTriggerEvaluator, TriggerReason


def make_message(
    *,
    content: str = '',
    mentions: tuple[object, ...] = (),
    mention_everyone: bool = False,
    reply_author_id: int | None = None,
    author_bot: bool = False,
) -> SimpleNamespace:
    resolved = None
    if reply_author_id is not None:
        resolved = SimpleNamespace(author=SimpleNamespace(id=reply_author_id))

    return SimpleNamespace(
        author=SimpleNamespace(bot=author_bot),
        content=content,
        mentions=list(mentions),
        mention_everyone=mention_everyone,
        reference=SimpleNamespace(resolved=resolved),
    )


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
    assert decision.score == 1.0


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
