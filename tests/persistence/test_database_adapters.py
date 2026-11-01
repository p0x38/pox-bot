import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy import Table

from poxbot.persistence.database.economy import EconomyDatabase
from poxbot.persistence.database.giveaway import GiveawayDatabase
from poxbot.persistence.database.settings import SettingsDatabase
from poxbot.persistence.database.stats import StatisticsDatabase
from poxbot.persistence.database.user import UserDatabase
from poxbot.persistence.models.economy_orm import (
    EconomyInventory,
    EconomyItem,
    EconomyTransaction,
    EconomyUser,
)
from poxbot.persistence.models.giveaway_orm import Giveaway
from poxbot.persistence.models.stats_orm import DailyUserActivity, UserStatistics
from poxbot.persistence.models.user_profile_orm import UserActivity, UserProfile
from poxbot.persistence.models.user_settings import SettingsData
from poxbot.persistence.models.user_settings_orm import UserPreference
from poxbot.shared.bases import Base


async def _create_tables(database: Any, tables: list[Table]) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=tables,
            ),
        )


def _dsn(tmp_path: Path, name: str) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / name}"


def test_economy_database_user_inventory_shop_and_history(tmp_path: Path) -> None:
    async def run() -> None:
        database = EconomyDatabase(
            cast("PoxBot", None),
            _dsn(tmp_path, "economy.db"),
        )
        await _create_tables(
            database,
            [
                EconomyUser.__table__,
                EconomyInventory.__table__,
                EconomyItem.__table__,
                EconomyTransaction.__table__,
            ],
        )

        user = await database.get_user(1001)
        assert user.wallet == 0
        user.wallet = 250
        await database.save_user(user)
        database.invalidate_user(1001)

        refreshed = await database.get_user(1001)
        assert refreshed.wallet == 250

        await database.modify_inventory(1001, "apple", 2)
        await database.modify_inventory(1001, "apple", 1)
        inventory = await database.get_inventory(1001)
        assert [(item.item_id, item.quantity) for item in inventory] == [("apple", 3)]

        await database.modify_inventory(1001, "apple", -3)
        assert await database.get_inventory(1001) == []

        async with database.async_session() as session, session.begin():
            session.add_all(
                [
                    EconomyItem(
                        id="shop-item",
                        name="Shop item",
                        description="For sale",
                        price=10,
                    ),
                    EconomyItem(
                        id="unpriced-item",
                        name="Unpriced item",
                        description="Not for sale",
                        price=None,
                    ),
                    EconomyTransaction(
                        id=1,
                        user_id=1001,
                        tx_type="deposit",
                        amount=50,
                        description="Test deposit",
                    ),
                    EconomyTransaction(
                        id=2,
                        user_id=1001,
                        tx_type="withdraw",
                        amount=10,
                        description="Test withdrawal",
                    ),
                ],
            )

        assert [item.id for item in await database.get_shop_items()] == ["shop-item"]
        assert (await database.get_item("shop-item")).name == "Shop item"
        assert await database.get_item("missing") is None

        history = await database.get_history(1001, limit=1)
        assert len(history) == 1
        assert history[0].tx_type == "withdraw"

        await database.engine.dispose()

    asyncio.run(run())


def test_giveaway_database_filters_active_and_deletes_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def run() -> None:
        monkeypatch.setattr(
            "poxbot.persistence.database.giveaway.time",
            lambda: 1000,
        )
        database = GiveawayDatabase(
            cast("PoxBot", None),
            _dsn(tmp_path, "giveaways.db"),
        )
        await _create_tables(database, [Giveaway.__table__])

        await database.save_giveaway(
            Giveaway(
                message_id=1,
                channel_id=2,
                guild_id=3,
                end_time=1001,
                winners=1,
                prize="Active",
                host_id=4,
            ),
        )
        await database.save_giveaway(
            Giveaway(
                message_id=5,
                channel_id=6,
                guild_id=7,
                end_time=999,
                winners=1,
                prize="Expired",
                host_id=8,
            ),
        )

        active = await database.get_active_giveaways()
        assert [giveaway.message_id for giveaway in active] == [1]

        await database.delete_giveaway(1)
        assert await database.get_active_giveaways() == []

        await database.engine.dispose()

    asyncio.run(run())


def test_settings_database_persists_and_invalidates_preferences(tmp_path: Path) -> None:
    async def run() -> None:
        manager = SimpleNamespace(
            normalize_language_code=lambda locale: f"normalized:{locale}",
        )
        database = SettingsDatabase(
            cast("PoxBot", None),
            _dsn(tmp_path, "settings.db"),
            cast("I18nManager", manager),
        )
        await _create_tables(database, [UserPreference.__table__])

        default = await database.get_settings(1001)
        assert default.locale == "en"

        settings = SettingsData(_locale="ja_JP", embed_color="#123456")
        await database.set_settings(1001, settings)

        cached = await database.get_settings(1001)
        stored = await database.get_settings(1001, use_cache=False)
        assert cached.locale == "ja_JP"
        assert stored.embed_color == "#123456"

        database.invalidate_user(1001)
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=1001),
            locale="en_US",
        )
        assert await database.get_locale(interaction) == "normalized:ja_JP"

        await database.engine.dispose()

    asyncio.run(run())


def test_user_database_updates_profiles_and_activity(tmp_path: Path) -> None:
    async def run() -> None:
        database = UserDatabase(
            cast("PoxBot", None),
            _dsn(tmp_path, "users.db"),
        )
        await _create_tables(
            database,
            [UserProfile.__table__, UserActivity.__table__],
        )

        await database.update_profile(
            1001,
            description="First description",
            nickname="Pox",
        )
        await database.update_profile(1001, nickname="Updated Pox")

        profile = await database.get_full_profile(1001)
        assert profile is not None
        assert profile.description == "First description"
        assert profile.nickname == "Updated Pox"

        await database.increment_activity(1001, "command")
        await database.increment_activity(1001, "message")
        activity = await database.get_activity_stats(1001)

        assert activity is not None
        assert activity.commands_run == 1
        assert activity.messages_sent == 1

        await database.increment_activity(1001, "unknown")
        unchanged = await database.get_activity_stats(1001)
        assert unchanged is not None
        assert unchanged.commands_run == 1
        assert unchanged.messages_sent == 1

        await database.engine.dispose()

    asyncio.run(run())


def test_statistics_database_tracks_xp_and_daily_activity(tmp_path: Path) -> None:
    async def run() -> None:
        database = StatisticsDatabase(
            cast("PoxBot", None),
            _dsn(tmp_path, "statistics.db"),
        )
        await _create_tables(
            database,
            [UserStatistics.__table__, DailyUserActivity.__table__],
        )

        first = await database.add_xp(1001, 80, guild_id=3003)
        second = await database.add_xp(1001, 20, guild_id=3003)

        assert first == {"leveled_up": True, "new_level": 2}
        assert second == {"leveled_up": True, "new_level": 3}

        statistics = await database.get_user_statistics(1001)
        assert statistics is not None
        assert statistics.xp == 100
        assert statistics.total_messages == 2

        today = datetime.now(UTC).date()
        activity = await database.get_daily_activity(today, today, guild_id=3003)

        assert activity == [
            {
                "date": today,
                "messages": 2,
                "characters": 100,
                "xp": 100,
            },
        ]

        leaderboard = await database.get_leaderboard(sort_by="unknown")
        assert [user.user_id for user in leaderboard] == [1001]

        await database.engine.dispose()

    asyncio.run(run())
