from __future__ import annotations

import pytest

from poxbot.features.markov.model import (
    MarkovGenerationResult,
    MarkovModel,
    MarkovModelKey,
)
from poxbot.persistence.models.guild_settings_v2 import MarkovModelScope


def test_markov_model_rejects_invalid_order() -> None:
    with pytest.raises(ValueError, match='order must be >= 1'):
        MarkovModel(order=0)


def test_markov_model_train_updates_statistics() -> None:
    model = MarkovModel(order=2)

    model.train(['hello', 'world'])

    assert model.message_count == 1
    assert model.token_count == 2
    assert model.state_count > 0


def test_markov_model_train_empty_tokens_does_nothing() -> None:
    model = MarkovModel(order=2)

    model.train([])

    assert model.message_count == 0
    assert model.token_count == 0
    assert model.state_count == 0


def test_markov_model_clear() -> None:
    model = MarkovModel(order=2)

    model.train(['hello', 'world'])
    model.clear()

    assert model.message_count == 0
    assert model.token_count == 0
    assert model.state_count == 0


def test_markov_model_key_global() -> None:
    key = MarkovModelKey.global_model()

    assert key.scope is MarkovModelScope.GLOBAL
    assert key.scope_id == 0


def test_markov_model_key_server() -> None:
    guild_id = 123456789012345678

    key = MarkovModelKey.server(guild_id)

    assert key.scope is MarkovModelScope.SERVER
    assert key.scope_id == guild_id


def test_markov_model_key_user() -> None:
    user_id = 987654321098765432

    key = MarkovModelKey.user(user_id)

    assert key.scope is MarkovModelScope.USER
    assert key.scope_id == user_id


def test_markov_model_keys_are_hashable() -> None:
    key = MarkovModelKey.server(123)

    mapping = {key: 'model'}

    assert mapping[key] == 'model'


def test_markov_generation_result() -> None:
    key = MarkovModelKey.server(123)

    result = MarkovGenerationResult(
        response='hello world',
        key=key,
    )

    assert result.response == 'hello world'
    assert result.key == key
    assert result.key.scope is MarkovModelScope.SERVER
    assert result.key.scope_id == 123
