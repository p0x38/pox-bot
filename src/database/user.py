from src.database import PostgreSQLDatabase


class UserDatabase(PostgreSQLDatabase):
    async def get_full_profile(self, user_id: int) -> dict | None:
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_profile_full WHERE user_id = $1",
                user_id
            )
            
            return dict(row) if row else None
    
    async def get_activity_stats(self, user_id: int) -> dict | None:
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_activity WHERE user_id $1",
                user_id
            )
            return dict(row) if row else None