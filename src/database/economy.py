from datetime import datetime
from typing import List, Optional
from src.database import PostgreSQLDatabase
from src.models import EconomyData
from src.utils import Cache
from logger import logger

class EconomyDatabase(PostgreSQLDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._cache = Cache(ttl=300)
    
    async def on_load(self):
        await self.execute_sql_file("resources/sqls/economy.sql")
    
    async def post_close(self):
        logger.info("[EconomyDatabase] Cleanup complete.")
    
    async def pre_close(self):
        logger.info("[EconomyDatabase] Clearing caches...")
        self._cache.clear()
    
    async def get_user(self, user_id: int) -> EconomyData:
        cached = self._cache.get(user_id)
        if cached: return cached

        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM economy_users WHERE user_id = $1", user_id)
                user_obj = EconomyData.from_row(row)
                if not row:
                    user_obj.user_id = user_id

                self._cache.set(user_id, user_obj)
                return user_obj
        return EconomyData(user_id=user_id)
    
    async def save_user(self, user: EconomyData):
        self._cache.set(user.user_id, user)
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO economy_users (user_id, wallet, bank, last_daily, last_work)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE SET
                        wallet = EXCLUDED.wallet,
                        bank = EXCLUDED.bank,
                        last_daily = EXCLUDED.last_daily
                        last_work = EXCLUDED.last_work
                """, user.user_id, user.wallet, user.bank, user.last_daily, user.last_work)
    
    async def get_shop_items(self) -> List[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM economy_items WHERE buy_price IS NOT NULL")
                return [dict(r) for r in rows]
        return []
    
    async def get_item(self, item_id: str) -> Optional[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM economy_items WHERE id = $1", item_id)
                return dict(row) if row else None
        return None
    
    async def modify_inventory(self, user_id: int, item_id: str, amount: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO economy_inventory (user_id, item_id, quantity)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, item_id) DO UPDATE
                    SET quantity = economy_inventory.quantity + EXCLUDED.quantity
                """, user_id, item_id, amount)

                await conn.execute("DELETE FROM economy_inventory WHERE quantity <= 0")
    
    async def get_inventory(self, user_id: int) -> List[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT i.name, inv.quantity, i.description 
                    FROM economy_inventory inv
                    JOIN economy_items i ON inv.item_id = i.id
                    WHERE inv.user_id = $1
                """, user_id)
                return [dict(r) for r in rows]
        return []
    
    async def log_tx(self, user_id: int, tx_type: str, amount: int, desc: str):
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO economy_transactions (user_id, type, amount, description, timestamp)
                    VALUES ($1, $2, $3, $4)
                """, user_id, tx_type, amount, desc, int(datetime.now().timestamp()))
    
    async def get_history(self, user_id: int, limit: int = 5) -> List[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                limit = max(1, min(12, limit))
                rows = await conn.fetch("""
                    SELECT type, amount, timestamp, description
                    FROM economy_transactions
                    WHERE user_id = $1
                    ORDER BY id DESC LIMIT $2
                """, user_id, limit)
                return [dict(r) for r in rows]
        return []