import asyncio
from typing import TYPE_CHECKING, cast

import orjson
from sqlalchemy import Table, text

from poxbot.persistence.database.guild_v2 import GuildSettingsDatabase
from poxbot.persistence.models.orm.moderation import ModerationEntry

if TYPE_CHECKING:
    from poxbot.application.bot import PoxBot


def test_legacy_moderation_entries_are_migrated():
    async def run():
        database = GuildSettingsDatabase(
            cast('PoxBot', None),
            'sqlite+aiosqlite:///:memory:',
        )
        legacy_config = {
            'version': 4,
            'features': {
                'filtering': {
                    'enabled': True,
                    'filters': {
                        'word': {
                            'enabled': True,
                            'blacklists': [
                                {
                                    'trigger': 'forbidden',
                                    'reason': 'legacy reason',
                                    'type': 2,
                                    'case_insensitive': False,
                                    'executed_by': 17,
                                    'timestamp': 1234.5,
                                },
                            ],
                        },
                        'anti_join': {
                            'enabled': True,
                            'blacklists': [
                                {
                                    'target_id': 987654321,
                                    'scope': 1,
                                    'expires_at': -1,
                                    'reasons': ['repeat evasion'],
                                    'timestamp': 1235.5,
                                    'executed_by': 18,
                                },
                            ],
                        },
                    },
                },
            },
        }

        async with database.engine.begin() as connection:
            await connection.run_sync(
                cast(Table, ModerationEntry.__table__).create,
            )
            await connection.execute(
                text(
                    'CREATE TABLE guild_settings '
                    '(guild_id BIGINT PRIMARY KEY, config JSON NOT NULL)',
                ),
            )
            await connection.execute(
                text(
                    'INSERT INTO guild_settings (guild_id, config) '
                    'VALUES (:guild_id, :config)',
                ),
                {
                    'guild_id': 123,
                    'config': orjson.dumps(legacy_config).decode(),
                },
            )

        await database._migrate_legacy_moderation_entries()

        word_entries = await database.get_moderation_entries('word', 123)
        assert len(word_entries) == 1
        assert word_entries[0].value == 'forbidden'
        assert word_entries[0].item_scope == 123
        assert word_entries[0].reasons == ['legacy reason']
        assert word_entries[0].extras == {
            'match_type': 2,
            'case_insensitive': False,
        }

        global_entries = await database.get_moderation_entries('user', -1)
        assert len(global_entries) == 1
        assert global_entries[0].value == '987654321'
        assert global_entries[0].expires_at is None
        assert global_entries[0].reasons == ['repeat evasion']

        async with database.engine.connect() as connection:
            raw_config = await connection.scalar(
                text('SELECT config FROM guild_settings WHERE guild_id = 123'),
            )
        if isinstance(raw_config, (str, bytes, bytearray, memoryview)):
            raw_config = orjson.loads(raw_config)
        assert (
            'blacklists' not in raw_config['features']['filtering']['filters']['word']
        )
        assert (
            'blacklists'
            not in raw_config['features']['filtering']['filters']['anti_join']
        )

        await database.engine.dispose()

    asyncio.run(run())
