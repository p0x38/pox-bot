import asyncio
from typing import TYPE_CHECKING, cast

from sqlalchemy import Table

from poxbot.persistence.database.guild_v2 import GuildSettingsDatabase
from poxbot.persistence.models.orm.global_chat_message_reference import (
    GlobalChatMessageReference,
)

if TYPE_CHECKING:
    from poxbot.application.bot import PoxBot


def test_global_chat_message_references_resolve_across_guilds() -> None:
    async def run() -> None:
        database = GuildSettingsDatabase(
            cast('PoxBot', None),
            'sqlite+aiosqlite:///:memory:',
        )
        async with database.engine.begin() as connection:
            await connection.run_sync(
                cast(Table, GlobalChatMessageReference.__table__).create,
            )

        await database.save_global_chat_message_reference(
            origin_message_id=1001,
            replica_message_id=1001,
            replica_guild_id=2001,
            replica_channel_id=3001,
        )
        await database.save_global_chat_message_reference(
            origin_message_id=1001,
            replica_message_id=4001,
            replica_guild_id=5001,
            replica_channel_id=6001,
        )

        assert await database.get_global_chat_origin_message_id(4001) == 1001
        assert await database.get_global_chat_origin_message_id(9999) is None
        assert await database.get_global_chat_replicas(1001) == {
            2001: (3001, 1001),
            5001: (6001, 4001),
        }

        # Re-saving the same origin/guild updates that guild's replica.
        await database.save_global_chat_message_reference(
            origin_message_id=1001,
            replica_message_id=4002,
            replica_guild_id=5001,
            replica_channel_id=6002,
        )

        assert await database.get_global_chat_origin_message_id(4001) is None
        assert await database.get_global_chat_origin_message_id(4002) == 1001
        assert await database.get_global_chat_replicas(1001) == {
            2001: (3001, 1001),
            5001: (6002, 4002),
        }

        await database.delete_global_chat_message_references(1001)

        assert await database.get_global_chat_replicas(1001) == {}
        assert await database.get_global_chat_origin_message_id(4002) is None

        await database.engine.dispose()

    asyncio.run(run())
