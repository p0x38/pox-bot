from discord import guild

from logger import logger
from src.database.bases import PostgreSQLDatabase
from src.models import LeaderboardData, UserStats


class StatsDatabase(PostgreSQLDatabase):
    async def on_load(self):
        await self.run_migrations("resources/migrations")
        logger.info("[StatsDatabase] Migration suite completed.")
    
    async def add_xp(self, user_id: int, count: int):
        if self.pool:
            query = """
            INSERT INTO user_stats (user_id, xp, total_messages, level)
            VALUES ($1, $2, 1, 1)
            ON CONFLICT (user_id) DO UPDATE SET
                xp = user_stats.xp + $2,
                total_messages = user_stats.total_messages + 1,
                level = CASE
                    WHEN floor(pow(user_stats.xp + $2, 0.25)) > user_stats.level
                    THEN floor(pow(user_stats.xp + $2, 0.25))
                    ELSE user_stats.level
                END
            RETURNING
                (floor(pow(user_stats.xp + $2, 0.25)) > (SELECT level FROM user_stats WHERE user_id = $1)) AS leveled_up,
                CAST(level AS INTEGER) AS new_level;
            """
            return await self.pool.fetchrow(query, user_id, count)
        return False
    
    async def get_user_stats(self, user_id: int) -> UserStats | None:
        if not self.pool:
            return None
        row = await self.pool.fetchrow("SELECT * FROM user_stats WHERE user_id = $1", user_id)
        return UserStats.from_row(row)
    
    async def get_leaderboard(self, sort_by: str = "xp", limit: int = 10):
        if self.pool:
            query = f"SELECT user_id, xp, level FROM user_stats ORDER BY {sort_by} DESC LIMIT $1"
            rows = await self.pool.fetch(query, limit)
            return LeaderboardData.from_rows(rows, sort_by)
        return LeaderboardData()
    
    async def cache_message(self, message_id: int, channel_id: int, guild_id: int, author_id: int, content: str):
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO m_cache (message_id, channel_id, guild_id, author_id, content)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (message_id) DO UPDATE SET content = EXCLUDED.content
            """, message_id, channel_id, guild_id, author_id, content)
            
            await conn.execute("""
                DELETE FROM m_cache
                WHERE channel_id = $1 AND message_id NOT IN (
                    SELECT message_id FROM m_cache
                    WHERE channel_id = $1
                    ORDER BY message_id DESC LIMIT 15000
                )
            """, channel_id)
    
    async def get_cached_messages(self, channel_id: int, limit: int) -> list:
        if not self.pool:
            return []
        
        rows = await self.pool.fetch("""
            SELECT content FROM m_cache
            WHERE channel_id = $1
            ORDER BY message_id DESC LIMIT $2
        """, channel_id, limit)
        return rows
    
    async def get_active_pattern(self, channel_id: int, target_user_id: int | None = None) -> list:
        if not self.pool:
            return []

        if target_user_id:
            query = """
                SELECT EXTRACT(HOUR FROM created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tokyo')::INT AS hour, COUNT(*) AS count
                FROM m_cache
                WHERE channel_id = $1 AND author_id = $2
                GROUP BY hour
                ORDER BY hour;
            """
            rows = await self.pool.fetch(query, channel_id, target_user_id)
        else:
            query = """
                SELECT EXTRACT(HOUR FROM created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tokyo')::INT AS hour, COUNT(*) AS count
                FROM m_cache
                WHERE channel_id = $1
                GROUP BY hour
                ORDER BY hour;
            """
            rows = await self.pool.fetch(query, channel_id)

        return rows