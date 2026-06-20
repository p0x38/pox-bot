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
    
    async def update_profile(self, user_id: int, description: str | None = None, nickname: str | None = None):
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn, conn.transaction():
                await conn.execute("""
                    INSERT INTO user_profiles (user_id, description, nickname)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id) DO UPDATE SET
                        description = COALESCE(EXCLUDED.description, user_profiles.description),
                        nickname = COALESCE(EXCLUDED.nickname, user_profiles.nickname),
                        updated_at = CURRENT_TIMESTAMP
                """, user_id, description, nickname)
    
    async def get_activity_stats(self, user_id: int) -> dict | None:
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_activity WHERE user_id $1",
                user_id
            )
            return dict(row) if row else None