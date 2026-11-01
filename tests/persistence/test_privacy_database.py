import asyncio
from datetime import date
from typing import TYPE_CHECKING, cast

from sqlalchemy import Table, text
from sqlalchemy.exc import SQLAlchemyError

from poxbot.persistence.database.privacy import PrivacyDatabase
from poxbot.persistence.database.guild_v2 import GuildSettingsDatabase
from poxbot.persistence.database.settings import SettingsDatabase
from poxbot.persistence.database.stats import StatisticsDatabase
from poxbot.persistence.models.economy_orm import (
    EconomyInventory,
    EconomyTransaction,
    EconomyUser,
)
from poxbot.persistence.models.giveaway_orm import Giveaway
from poxbot.persistence.models.global_chat_moderation_orm import (
    GlobalChatModerationCase,
)
from poxbot.persistence.models.guild_settings_v2 import GuildConfigV2
from poxbot.persistence.models.guild_settings_v2_orm import ActiveTicket, GuildSettings
from poxbot.persistence.models.orm.moderation import ModerationEntry
from poxbot.persistence.models.stats_orm import (
    DailyUserActivity,
    UserStatistics,
)
from poxbot.persistence.models.user_profile_orm import UserActivity, UserProfile
from poxbot.persistence.models.user_settings import SettingsData
from poxbot.persistence.models.user_settings_orm import UserPreference
from poxbot.shared.bases import Base

if TYPE_CHECKING:
    from poxbot.application.bot import PoxBot
    from poxbot.services.i18n import I18nManager


TABLES: list[Table] = [
    UserStatistics.__table__,
    DailyUserActivity.__table__,
    UserProfile.__table__,
    UserActivity.__table__,
    UserPreference.__table__,
    EconomyUser.__table__,
    EconomyInventory.__table__,
    EconomyTransaction.__table__,
    ActiveTicket.__table__,
    GuildSettings.__table__,
    Giveaway.__table__,
    ModerationEntry.__table__,
    GlobalChatModerationCase.__table__,
]


async def create_database(path) -> PrivacyDatabase:
    database = PrivacyDatabase(
        cast('PoxBot', None),
        f'sqlite+aiosqlite:///{path}',
    )

    async with database.engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=TABLES,
            ),
        )

    return database


def test_export_only_contains_requested_user_data(tmp_path) -> None:
    async def run() -> None:
        database = await create_database(tmp_path / 'privacy-export.db')

        target_user_id = 1001
        other_user_id = 2002

        async with database.async_session() as session, session.begin():
            session.add_all(
                [
                    UserStatistics(
                        user_id=target_user_id,
                        xp=500,
                        total_messages=50,
                        level=4,
                    ),
                    UserStatistics(
                        user_id=other_user_id,
                        xp=900,
                        total_messages=90,
                        level=5,
                    ),
                    UserProfile(
                        user_id=target_user_id,
                        description='Example profile',
                        nickname='Example',
                    ),
                    UserPreference(
                        user_id=target_user_id,
                        data=SettingsData(
                            embed_color='#123456',
                        ),
                    ),
                    DailyUserActivity(
                        user_id=target_user_id,
                        guild_id=3003,
                        activity_date=date(2026, 11, 1),
                        message_count=10,
                        character_count=100,
                        xp_gained=100,
                    ),
                    EconomyUser(
                        user_id=target_user_id,
                        wallet=100,
                        bank=500,
                    ),
                    EconomyInventory(
                        user_id=target_user_id,
                        item_id='test-item',
                        quantity=2,
                    ),
                    EconomyTransaction(
                        id=1,
                        user_id=target_user_id,
                        tx_type='deposit',
                        amount=100,
                        description='Test transaction',
                    ),
                    ActiveTicket(
                        channel_id=4004,
                        user_id=target_user_id,
                        guild_id=3003,
                    ),
                    Giveaway(
                        message_id=5005,
                        channel_id=6006,
                        guild_id=3003,
                        end_time=1900000000,
                        winners=1,
                        prize='Test prize',
                        host_id=target_user_id,
                    ),
                ],
            )

        data = await database.export_user_data(target_user_id)

        assert data['user']['discord_id'] == str(target_user_id)
        assert data['statistics']['xp'] == 500
        assert data['profile']['nickname'] == 'Example'
        assert data['preferences']['embed_color'] == '#123456'

        assert len(data['daily_activity']) == 1
        assert data['daily_activity'][0]['guild_id'] == '3003'

        assert data['economy']['account']['wallet'] == 100
        assert len(data['economy']['inventory']) == 1
        assert len(data['economy']['transactions']) == 1

        assert len(data['tickets']) == 1
        assert len(data['hosted_giveaways']) == 1

        serialized = str(data)

        assert str(other_user_id) not in serialized
        assert '900' not in str(data['statistics'])

        await database.engine.dispose()

    asyncio.run(run())


def test_delete_only_removes_requested_user_data(tmp_path) -> None:
    async def run() -> None:
        database = await create_database(tmp_path / 'privacy-delete.db')

        target_user_id = 1001
        other_user_id = 2002

        async with database.async_session() as session, session.begin():
            session.add_all(
                [
                    UserStatistics(
                        user_id=target_user_id,
                        xp=100,
                        total_messages=10,
                        level=3,
                    ),
                    UserStatistics(
                        user_id=other_user_id,
                        xp=200,
                        total_messages=20,
                        level=4,
                    ),
                    EconomyUser(
                        user_id=target_user_id,
                        wallet=100,
                        bank=200,
                    ),
                    EconomyUser(
                        user_id=other_user_id,
                        wallet=300,
                        bank=400,
                    ),
                    Giveaway(
                        message_id=5005,
                        channel_id=6006,
                        guild_id=3003,
                        end_time=1900000000,
                        winners=1,
                        prize='Test prize',
                        host_id=target_user_id,
                    ),
                    ModerationEntry(
                        item_type='user',
                        value=str(target_user_id),
                        item_scope=3003,
                        reasons=['Test restriction'],
                    ),
                ],
            )

        report = await database.delete_user_data(target_user_id)

        async with database.async_session() as session:
            assert (
                await session.get(
                    UserStatistics,
                    target_user_id,
                )
                is None
            )

            other_user = await session.get(
                UserStatistics,
                other_user_id,
            )
            assert other_user is not None
            assert other_user.xp == 200

            assert (
                await session.get(
                    EconomyUser,
                    target_user_id,
                )
                is None
            )

            assert (
                await session.get(
                    EconomyUser,
                    other_user_id,
                )
                is not None
            )

            giveaway = await session.get(Giveaway, 5005)
            assert giveaway is not None
            assert giveaway.host_id is None

            # Moderation restriction remains, as specified by the policy.
            restrictions = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM moderation_entries
                    WHERE item_type = 'user'
                    AND value = :user_id
                    """,
                ),
                {'user_id': str(target_user_id)},
            )
            assert restrictions.scalar_one() == 1

        assert report['deleted']['statistics'] == 1
        assert report['deleted']['economy_account'] == 1
        assert report['anonymized']['giveaway_host_references'] == 1
        assert report['retained']['moderation_restrictions'] == 1

        # Deleting the same user again should be safe.
        second_report = await database.delete_user_data(target_user_id)

        assert second_report['deleted']['statistics'] == 0
        assert second_report['deleted']['economy_account'] == 0

        await database.engine.dispose()

    asyncio.run(run())


def test_delete_rolls_back_when_a_table_delete_fails(tmp_path) -> None:
    async def run() -> None:
        database = await create_database(tmp_path / 'privacy-rollback.db')

        target_user_id = 1001

        async with database.async_session() as session, session.begin():
            session.add_all(
                [
                    UserStatistics(
                        user_id=target_user_id,
                        xp=100,
                        total_messages=10,
                        level=3,
                    ),
                    UserPreference(
                        user_id=target_user_id,
                        data=SettingsData(),
                    ),
                ],
            )

        # Force a failure after the statistics deletion has been attempted.
        async with database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    CREATE TRIGGER fail_preference_delete
                    BEFORE DELETE ON user_preferences
                    BEGIN
                        SELECT RAISE(ABORT, 'forced test failure');
                    END;
                    """,
                ),
            )

        try:
            await database.delete_user_data(target_user_id)
        except SQLAlchemyError:
            pass
        else:
            raise AssertionError('Expected the deletion to fail.')

        async with database.async_session() as session:
            statistics = await session.get(
                UserStatistics,
                target_user_id,
            )
            preference = await session.get(
                UserPreference,
                target_user_id,
            )

            # Both rows must remain because the transaction rolled back.
            assert statistics is not None
            assert preference is not None

        await database.engine.dispose()

    asyncio.run(run())


def test_guild_configuration_references_are_exported_and_removed(tmp_path) -> None:
    async def run() -> None:
        database = await create_database(tmp_path / 'privacy-guild-config.db')

        target_user_id = 1001
        other_user_id = 2002
        guild_id = 3003

        config = GuildConfigV2.from_dict(
            {
                'features': {
                    'filtering': {
                        'last_executor': target_user_id,
                        'filters': {
                            'anti_message': {
                                'blocked_user_ids': [
                                    target_user_id,
                                    other_user_id,
                                ],
                            },
                        },
                    },
                    'global_chat': {
                        'last_executor': target_user_id,
                        'whitelisted_user_ids': [
                            target_user_id,
                            other_user_id,
                        ],
                    },
                    'logs': {
                        'last_executor': target_user_id,
                    },
                    'userphone': {
                        # This is a guild ID, not a user ID.
                        'current_partner_id': 9009,
                    },
                },
            },
        )

        async with database.async_session() as session, session.begin():
            session.add(GuildSettings(guild_id=guild_id, config=config))

        exported = await database.export_user_data(target_user_id)
        references = exported['server_configuration_references']

        assert references == [
            {
                'guild_id': str(guild_id),
                'last_executor_features': ['filtering', 'global_chat', 'logs'],
                'anti_message_blocklist': True,
                'global_chat_whitelist': True,
            },
        ]

        report = await database.delete_user_data(target_user_id)

        async with database.async_session() as session:
            guild_settings = await session.get(GuildSettings, guild_id)
            assert guild_settings is not None

            config_data = guild_settings.config.to_dict()
            features = config_data['features']

            assert features['filtering']['filters']['anti_message'][
                'blocked_user_ids'
            ] == [other_user_id]
            assert features['global_chat']['whitelisted_user_ids'] == [
                other_user_id,
            ]
            assert features['filtering']['last_executor'] is None
            assert features['global_chat']['last_executor'] is None
            assert features['logs']['last_executor'] is None

            # Guild IDs must not be treated as user IDs.
            assert features['userphone']['current_partner_id'] == 9009

        assert report['deleted']['guild_config_blocked_user_references'] == 1
        assert report['deleted']['guild_config_global_chat_whitelist_references'] == 1
        assert report['anonymized']['guild_config_last_executor_references'] == 3

        await database.engine.dispose()

    asyncio.run(run())


def test_settings_cache_can_be_invalidated(tmp_path) -> None:
    async def run() -> None:
        database = SettingsDatabase(
            cast('PoxBot', None),
            f'sqlite+aiosqlite:///{tmp_path / "settings-cache.db"}',
            cast('I18nManager', None),
        )
        user_id = 1001
        cached_settings = object()

        database.settings_cache.set(user_id, cached_settings)
        assert database.settings_cache.get(user_id) is cached_settings

        database.invalidate_user(user_id)

        assert database.settings_cache.get(user_id) is None
        await database.engine.dispose()

    asyncio.run(run())


def test_statistics_database_drops_legacy_message_cache(tmp_path) -> None:
    async def run() -> None:
        database = StatisticsDatabase(
            cast('PoxBot', None),
            f'sqlite+aiosqlite:///{tmp_path / "legacy-message-cache.db"}',
        )

        async with database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    CREATE TABLE m_cache (
                        message_id BIGINT PRIMARY KEY,
                        channel_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        author_id BIGINT NOT NULL,
                        content TEXT NOT NULL
                    )
                    """,
                ),
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO m_cache (
                        message_id,
                        channel_id,
                        guild_id,
                        author_id,
                        content
                    ) VALUES (1, 2, 3, 4, 'legacy message')
                    """,
                ),
            )

        await database.on_load()

        async with database.engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'm_cache'",
                ),
            )
            assert result.scalar_one_or_none() is None

        await database.engine.dispose()

    asyncio.run(run())



def test_guild_settings_cache_can_be_invalidated(tmp_path) -> None:
    async def run() -> None:
        database = GuildSettingsDatabase(
            cast('PoxBot', None),
            f'sqlite+aiosqlite:///{tmp_path / "guild-settings-cache.db"}',
        )
        guild_id = 3003
        cached_config = object()

        database._cache.set(guild_id, cached_config)
        assert database._cache.get(guild_id) is cached_config

        database.invalidate_config_cache()

        assert database._cache.get(guild_id) is None
        await database.engine.dispose()

    asyncio.run(run())
