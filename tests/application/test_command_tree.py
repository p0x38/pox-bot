import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from discord import Interaction

from poxbot.application.command_tree import ModerationCommandTree


def _interaction(client: object) -> SimpleNamespace:
    return SimpleNamespace(
        client=client,
        user=SimpleNamespace(id=1234),
        locale=SimpleNamespace(value="en-US"),
        response=SimpleNamespace(send_message=AsyncMock()),
    )


def _check(interaction: SimpleNamespace) -> bool:
    return asyncio.run(
        ModerationCommandTree.interaction_check(
            cast(ModerationCommandTree, None),
            cast(Interaction, interaction),
        ),
    )


def test_interaction_is_allowed_when_no_ban_checker_exists() -> None:
    interaction = _interaction(SimpleNamespace())

    assert _check(interaction) is True
    interaction.response.send_message.assert_not_awaited()


def test_interaction_is_allowed_when_user_is_not_banned() -> None:
    client = SimpleNamespace(is_bot_banned=AsyncMock(return_value=False))
    interaction = _interaction(client)

    assert _check(interaction) is True
    client.is_bot_banned.assert_awaited_once_with(1234)
    interaction.response.send_message.assert_not_awaited()


def test_banned_user_receives_translated_ephemeral_message() -> None:
    translator = SimpleNamespace(
        T=lambda key, locale: "You cannot use this bot anymore.",
    )
    client = SimpleNamespace(
        is_bot_banned=AsyncMock(return_value=True),
        internal_translator=translator,
    )
    interaction = _interaction(client)

    assert _check(interaction) is False
    interaction.response.send_message.assert_awaited_once_with(
        "You cannot use this bot anymore.",
        ephemeral=True,
    )


def test_banned_user_gets_fallback_when_translation_is_missing() -> None:
    translator = SimpleNamespace(T=lambda key, locale: key)
    client = SimpleNamespace(
        is_bot_banned=AsyncMock(return_value=True),
        internal_translator=translator,
    )
    interaction = _interaction(client)

    assert _check(interaction) is False
    interaction.response.send_message.assert_awaited_once_with(
        "You are restricted from using this bot.",
        ephemeral=True,
    )


def test_banned_user_gets_key_fallback_without_translator() -> None:
    client = SimpleNamespace(is_bot_banned=AsyncMock(return_value=True))
    interaction = _interaction(client)

    assert _check(interaction) is False
    interaction.response.send_message.assert_awaited_once_with(
        "You are restricted from using this bot.",
        ephemeral=True,
    )
