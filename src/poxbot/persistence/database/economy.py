from typing import TYPE_CHECKING

from sqlalchemy import select

from ...shared.bases import BaseDatabase
from ...shared.bases.base_orm_model import Base
from ...shared.utils import Cache
from ..models.economy_orm import (
    EconomyInventory,
    EconomyItem,
    EconomyTransaction,
    EconomyUser,
)

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class EconomyDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str):
        super().__init__(bot, dsn)
        self._cache = Cache(ttl=300)

    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.debug('Initialized tables')

    async def get_user(self, user_id: int) -> EconomyUser:
        cached = self._cache.get(user_id)
        if cached:
            return cached

        async with self.async_session() as session, session.begin():
            user = await session.get(EconomyUser, user_id)
            if not user:
                user = EconomyUser(user_id=user_id)
                session.add(user)

            self._cache.set(user_id, user)
            return user

    async def save_user(self, user: EconomyUser):
        self._cache.set(user.user_id, user)
        async with self.async_session() as session, session.begin():
            await session.merge(user)

    async def get_shop_items(self) -> list[EconomyItem]:
        async with self.async_session() as session:
            result = await session.execute(
                select(EconomyItem).where(EconomyItem.price.is_not(None)),
            )
            return list(result.scalars().all())

    async def get_item(self, item_id: str) -> EconomyItem | None:
        async with self.async_session() as session:
            return await session.get(EconomyItem, item_id)

    async def modify_inventory(self, user_id: int, item_id: str, amount: int):
        async with self.async_session() as session, session.begin():
            stmt = select(EconomyInventory).where(
                EconomyInventory.user_id == user_id,
                EconomyInventory.item_id == item_id,
            )
            res = await session.execute(stmt)
            inv = res.scalar_one_or_none()

            if inv:
                inv.quantity += amount
                if inv.quantity <= 0:
                    await session.delete(inv)
            elif amount > 0:
                session.add(
                    EconomyInventory(user_id=user_id, item_id=item_id, quantity=amount),
                )

    async def get_inventory(self, user_id: int) -> list[EconomyInventory]:
        async with self.async_session() as session:
            result = await session.execute(
                select(EconomyInventory).where(EconomyInventory.user_id == user_id),
            )
            return list(result.scalars().all())

    async def log_tx(self, user_id: int, tx_type: str, amount: int, desc: str):
        async with self.async_session() as session, session.begin():
            tx = EconomyTransaction(
                user_id=user_id,
                tx_type=tx_type,
                amount=amount,
                description=desc,
            )
            session.add(tx)

    async def get_history(
        self,
        user_id: int,
        limit: int = 5,
    ) -> list[EconomyTransaction]:
        async with self.async_session() as session:
            stmt = (
                select(EconomyTransaction)
                .where(EconomyTransaction.user_id == user_id)
                .order_by(EconomyTransaction.id.desc())
                .limit(min(max(1, limit), 12))
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
