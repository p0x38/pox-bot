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


def test_dialogue_find_returns_none_when_empty() -> None:
    memory = MarkovDialogueMemory(MarkovTokenizer())

    assert memory.find('hello') is None


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
