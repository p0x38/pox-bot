import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from poxbot.services.privacy import PrivacyService


def _service(*, delete_result=None, delete_error=None):
    privacy_database = SimpleNamespace(
        export_user_data=AsyncMock(return_value={"user": {"discord_id": "1001"}}),
        delete_user_data=AsyncMock(return_value=delete_result),
    )
    if delete_error is not None:
        privacy_database.delete_user_data.side_effect = delete_error

    economy = SimpleNamespace(invalidate_user=Mock())
    settings = SimpleNamespace(invalidate_user=Mock())
    guild = SimpleNamespace(invalidate_config_cache=Mock())
    database = SimpleNamespace(
        privacy=privacy_database,
        economy=economy,
        settings=settings,
        guild=guild,
    )
    return (
        PrivacyService(cast(Any, database)),
        privacy_database,
        economy,
        settings,
        guild,
    )


def test_export_delegates_to_privacy_database() -> None:
    async def run() -> None:
        service, privacy_database, *_ = _service()

        exported = await service.export_user_data(1001)

        assert exported == {"user": {"discord_id": "1001"}}
        privacy_database.export_user_data.assert_awaited_once_with(1001)

    asyncio.run(run())


def test_delete_invalidates_all_related_caches_after_success() -> None:
    async def run() -> None:
        report = {"deleted": {"profile": 1}, "anonymized": {}, "retained": {}}
        service, privacy_database, economy, settings, guild = _service(
            delete_result=report,
        )

        result = await service.delete_user_data(1001)

        assert result == report
        privacy_database.delete_user_data.assert_awaited_once_with(1001)
        economy.invalidate_user.assert_called_once_with(1001)
        settings.invalidate_user.assert_called_once_with(1001)
        guild.invalidate_config_cache.assert_called_once_with()

    asyncio.run(run())


def test_delete_does_not_invalidate_caches_when_database_fails() -> None:
    async def run() -> None:
        service, _, economy, settings, guild = _service(
            delete_error=RuntimeError("database unavailable"),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await service.delete_user_data(1001)

        economy.invalidate_user.assert_not_called()
        settings.invalidate_user.assert_not_called()
        guild.invalidate_config_cache.assert_not_called()

    asyncio.run(run())


def test_export_and_delete_fail_when_privacy_database_is_unavailable() -> None:
    async def run() -> None:
        service = PrivacyService(cast(Any, SimpleNamespace(privacy=None)))

        with pytest.raises(RuntimeError, match="unavailable"):
            await service.export_user_data(1001)

        with pytest.raises(RuntimeError, match="unavailable"):
            await service.delete_user_data(1001)

    asyncio.run(run())
