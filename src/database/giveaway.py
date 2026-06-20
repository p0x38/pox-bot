import datetime

from pytz import UTC

from logger import logger
from src.database import PostgreSQLDatabase
from src.models import GiveawayData


class GiveawayDatabase(PostgreSQLDatabase):
    async def on_load(self):
        await self.run_migrations("resources/migrations")
        logger.info("[GiveawayDatabase] Migration suite completed.")

    async def get_active_giveaways(self) -> list[GiveawayData | None]:
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM active_giveaways WHERE end_time > $1",
                int(datetime.datetime.now(UTC).timestamp()),
            )
        return [GiveawayData.from_row(row) for row in rows if GiveawayData.from_row(row) is not None]

    async def save_giveaway(self, giveaway: GiveawayData):
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO active_giveaways (message_id, channel_id, guild_id, end_time, winners, prize, host_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (message_id) DO UPDATE SET
                    channel_id = EXCLUDED.channel_id,
                    guild_id = EXCLUDED.guild_id,
                    end_time = EXCLUDED.end_time,
                    winners = EXCLUDED.winners,
                    prize = EXCLUDED.prize,
                    host_id = EXCLUDED.host_id
                """,
                giveaway.message_id,
                giveaway.channel_id,
                giveaway.guild_id,
                giveaway.end_time,
                giveaway.winners,
                giveaway.prize,
                giveaway.host_id,
            )

    async def delete_giveaway(self, message_id: int):
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM active_giveaways WHERE message_id = $1",
                message_id,
            )
