import asyncio
from typing import TYPE_CHECKING, cast

from sqlalchemy import Table

from poxbot.persistence.database.guild_v2 import GuildSettingsDatabase
from poxbot.persistence.models.global_chat_moderation_orm import (
    GlobalChatModerationCase,
)

if TYPE_CHECKING:
    from poxbot.application.bot import PoxBot


def test_global_chat_moderation_cases_are_persistent_and_single_resolution():
    async def run():
        database = GuildSettingsDatabase(
            cast('PoxBot', None),
            'sqlite+aiosqlite:///:memory:',
        )
        async with database.engine.begin() as connection:
            await connection.run_sync(
                cast(Table, GlobalChatModerationCase.__table__).create,
            )

        await database.create_global_chat_moderation_case(
            message_id=1001,
            guild_id=2001,
            channel_id=3001,
            author_id=4001,
            reason_codes=['image_decode_failed'],
            message_fingerprint='a' * 64,
        )

        cases = await database.get_pending_global_chat_moderation_cases(2001)
        assert len(cases) == 1
        assert cases[0].message_id == 1001
        assert cases[0].reason_codes == ['image_decode_failed']
        assert (await database.get_global_chat_moderation_case(9999, 1001)) is None

        assert await database.resolve_global_chat_moderation_case(
            guild_id=2001,
            message_id=1001,
            status='approved',
            reviewer_id=5001,
        )
        assert not await database.resolve_global_chat_moderation_case(
            guild_id=2001,
            message_id=1001,
            status='denied',
            reviewer_id=5002,
        )
        assert await database.get_pending_global_chat_moderation_cases(2001) == []
        await database.engine.dispose()

    asyncio.run(run())
