from src.database import PostgreSQLDatabase
from src.models import TicketData


class TicketDatabase(PostgreSQLDatabase):
    async def get_ticket(self, channel_id: int) -> TicketData | None:
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM active_tickets WHERE channel_id = $1",
                channel_id
            )
            return TicketData.from_row(row) if row else None
    
    async def get_user_tickets(self, user_id: int, guild_id: int) -> list[TicketData]:
        if not self.pool:
            return []
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM active_tickets WHERE user_id = $1 AND guild_id = $2 AND status = 'open'",
                user_id, guild_id
            )
            return [ticket for row in rows if (ticket := TicketData.from_row(row)) is not None]
    
    async def create_ticket_with_log(self, channel_id: int, user_id: int, guild_id: int):
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("""
                    INSERT INTO active_tickets (channel_id, user_id, guild_id)
                    VALUES ($1, $2, $3)
                """, channel_id, user_id, guild_id)