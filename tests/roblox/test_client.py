from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import poxbot.features.roblox.client as client_module
from poxbot.features.roblox.client import RobloxClient, RobloxUser


@pytest.mark.asyncio
async def test_resolve_user_without_thumbnail(monkeypatch) -> None:
    record = SimpleNamespace(
        id=156,
        name='builderman',
        display_name='builderman',
        requested_username='builderman',
    )

    fake_client = SimpleNamespace(
        requests=SimpleNamespace(
            session=SimpleNamespace(aclose=AsyncMock()),
        ),
        get_users_by_usernames=AsyncMock(return_value=[record]),
        thumbnails=SimpleNamespace(
            get_user_avatar_thumbnails=AsyncMock(return_value=[]),
        ),
    )

    monkeypatch.setattr(
        client_module,
        'Client',
        lambda: fake_client,
    )

    client = RobloxClient()

    users = await client.resolve_users(['builderman'])

    assert users == [
        RobloxUser(
            user_id=156,
            username='builderman',
            display_name='builderman',
            avatar_url=None,
        ),
    ]

    await client.close()
    fake_client.requests.session.aclose.assert_awaited_once()
