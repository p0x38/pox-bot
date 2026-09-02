from __future__ import annotations

from poxbot.features.markov.dialogue import MarkovDialogueMemory
from poxbot.features.markov.tokenizer import MarkovTokenizer


def test_dialogue_learn_and_find() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())

    memory.learn(
        'what is this?',
        'idk lol',
    )

    assert memory.find('what is this?') == 'idk lol'


def test_dialogue_find_is_case_insensitive() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())

    memory.learn(
        'What Is This?',
        'idk lol',
    )

    assert memory.find('what is this?') == 'idk lol'


def test_dialogue_tfidf_retrieval() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())
    memory.learn('how do I install python', 'use the Python installer')
    memory.learn('how do I cook rice', 'use a rice cooker')

    match = memory.find_match('how can I install python')

    assert match is not None
    assert match.response == 'use the Python installer'
    assert match.score > 0.5


def test_dialogue_exact_match_has_perfect_score() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())
    memory.learn('hello there', 'hello!')

    match = memory.find_match('hello there')

    assert match is not None
    assert match.score == 1.0
    assert match.response == 'hello!'


def test_dialogue_find_returns_none_when_empty() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())

    assert memory.find('hello') is None


def test_dialogue_threshold_can_reject_unrelated_queries() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())
    memory.learn('how do I install python', 'use the Python installer')

    assert memory.find('completely unrelated topic', threshold=0.55) is None


def test_dialogue_clear() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())

    memory.learn('hello', 'hi')
    memory.clear()

    assert memory.entries == []


def test_dialogue_respects_max_entries() -> None:
    memory = MarkovDialogueMemory(
        MarkovTokenizer(),
        max_entries=2,
    )

    memory.learn('one', 'first')
    memory.learn('two', 'second')
    memory.learn('three', 'third')

    assert len(memory.entries) == 2
    assert [entry.prompt for entry in memory.entries] == [
        'two',
        'three',
    ]
