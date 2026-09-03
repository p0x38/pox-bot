from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from discord import Message

from poxbot.features.markov.dialogue import MarkovDialogueMemory
from poxbot.features.markov.model import MarkovModelKey
from poxbot.persistence.models.guild_settings_v2 import MarkovModelScope
from poxbot.platforms.discord.extensions.chatbot import ChatbotCog


@pytest.mark.parametrize(
    ('scope', 'expected'),
    [
        (
            MarkovModelScope.GLOBAL,
            [
                MarkovModelKey.global_model(),
            ],
        ),
        (
            MarkovModelScope.SERVER,
            [
                MarkovModelKey.server(123),
                MarkovModelKey.global_model(),
            ],
        ),
        (
            MarkovModelScope.USER,
            [
                MarkovModelKey.user(456),
                MarkovModelKey.server(123),
                MarkovModelKey.global_model(),
            ],
        ),
    ],
)
def test_markov_fallback_keys(
    scope: MarkovModelScope,
    expected: list[MarkovModelKey],
) -> None:
    cog = object.__new__(ChatbotCog)

    result = cog._get_markov_fallback_keys(
        scope,
        guild_id=123,
        user_id=456,
    )

    assert result == expected


def test_markov_fallback_does_not_include_dialogue_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = object.__new__(ChatbotCog)

    monkeypatch.setattr(
        cog,
        '_clean_markov_prompt',
        lambda message: message.content,
    )

    keys = cog._get_markov_fallback_keys(
        MarkovModelScope.SERVER,
        guild_id=123,
        user_id=456,
    )

    assert keys == [
        MarkovModelKey.server(123),
        MarkovModelKey.global_model(),
    ]

    # Dialogue lookup must use only the primary scope.
    primary_key = MarkovModelKey.server(123)

    assert primary_key == keys[0]


async def test_generate_markov_response_prefers_dialogue_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = object.__new__(ChatbotCog)

    monkeypatch.setattr(
        cog,
        '_clean_markov_prompt',
        lambda message: message.content,
    )

    primary_key = MarkovModelKey.user(456)

    memory = MarkovDialogueMemory()
    memory.learn('what is this?', 'remembered reply')

    requested_keys: list[MarkovModelKey] = []

    async def fake_get_dialogue(  # ruff: ignore[unused-async]
        key: MarkovModelKey,
    ) -> MarkovDialogueMemory:
        requested_keys.append(key)
        return memory

    async def fail_generate(*args: object, **kwargs: object) -> None:  # ruff: ignore[unused-async]
        pytest.fail('Markov generation should not run')

    monkeypatch.setattr(
        cog,
        '_get_markov_dialogue',
        fake_get_dialogue,
    )
    monkeypatch.setattr(
        cog,
        '_generate_markov_from_key',
        fail_generate,
    )

    message = cast(
        Message,
        SimpleNamespace(
            guild=SimpleNamespace(id=123),
            author=SimpleNamespace(id=456),
            content='what is this?',
        ),
    )

    result = await cog.generate_markov_response(
        message,
        scope=MarkovModelScope.USER,
    )

    assert result is not None
    assert result.response == 'remembered reply'
    assert result.key == primary_key
    assert requested_keys == [primary_key]
