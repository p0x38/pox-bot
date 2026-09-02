from __future__ import annotations

from poxbot.features.markov.tokenizer import MarkovTokenizer


def test_tokenize_removes_user_mentions() -> None:
    tokenizer = MarkovTokenizer()

    assert tokenizer.tokenize('hello <@123456789> world') == [
        'hello',
        'world',
    ]


def test_tokenize_removes_nickname_user_mentions() -> None:
    tokenizer = MarkovTokenizer()

    assert tokenizer.tokenize('hello <@!123456789> world') == [
        'hello',
        'world',
    ]


def test_tokenize_removes_role_and_channel_mentions() -> None:
    tokenizer = MarkovTokenizer()

    assert tokenizer.tokenize('hi <@&123456789> in <#987654321>') == [
        'hi',
        'in',
    ]
