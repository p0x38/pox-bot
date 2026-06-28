from sqlalchemy import and_, select

from src.bases import BaseDatabase
from src.models.guild_settings_v2_orm import ActiveTicket


class TicketDatabase(BaseDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)

    async def get_ticket(self, channel_id: int) -> ActiveTicket | None:
        async with self.async_session() as session:
            return await session.get(ActiveTicket, channel_id)

    async def get_user_tickets(self, user_id: int, guild_id: int) -> list[ActiveTicket]:
        async with self.async_session() as session:
            stmt = select(ActiveTicket).where(
                and_(
                    ActiveTicket.user_id == user_id,
                    ActiveTicket.guild_id == guild_id
                )
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_ticket_with_log(self, channel_id: int, user_id: int, guild_id: int):
        async with self.async_session() as session, session.begin():
            session.add(ActiveTicket(
                channel_id=channel_id,
                user_id=user_id,
                guild_id=guild_id
            ))
