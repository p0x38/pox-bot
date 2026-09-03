from time import time
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from ...shared.bases import BaseDatabase
from ...shared.bases.base_orm_model import Base
from ..models.giveaway_orm import Giveaway

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class GiveawayDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str):
        super().__init__(bot, dsn)

    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.debug('Initialized tables')

    async def get_active_giveaways(self) -> list[Giveaway]:
        async with self.async_session() as session, session.begin():
            now = int(time())
            stmt = select(Giveaway).where(Giveaway.end_time > now)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_giveaway(self, giveaway: Giveaway):
        async with self.async_session() as session, session.begin():
            await session.merge(giveaway)

    async def delete_giveaway(self, message_id: int):
        async with self.async_session() as session, session.begin():
            await session.execute(
                delete(Giveaway).where(Giveaway.message_id == message_id),
            )
