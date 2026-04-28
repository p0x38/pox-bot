from typing import Optional

from src.database.bases import PostgreSQLDatabase
from logger import logger
from src.models import UserStats, LeaderboardData

class StatsDatabase(PostgreSQLDatabase):
    async def on_load(self):
        await self.execute_sql_file("resources/sqls/user_stats.sql")
        logger.info("[UserStatsDatabase] Tables verified.")
    
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
                level AS new_level;
            """
            return await self.pool.fetchrow(query, user_id, count)
        return False
    
    async def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        if not self.pool:
            return None
        row = self.pool.fetchrow("SELECT * FROM user_stats WHERE user_id = $1", user_id)
        return UserStats.from_row(row)
    
    async def get_leaderboard(self, sort_by: str = "xp", limit: int = 10):
        if self.pool:
            query = f"SELECT user_id, xp, level FROM user_stats ORDER BY {sort_by} DESC LIMIT $1"
            rows = await self.pool.fetch(query, limit)
            return LeaderboardData.from_rows(rows, sort_by)
        return LeaderboardData()