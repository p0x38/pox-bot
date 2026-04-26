import asyncpg
from typing import Optional
from logger import logger

class PostgreSQLDatabase:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=self.dsn,
                    min_size=5,
                    max_size=24,
                    command_timeout=60
                )
                logger.info("PostgreSQL connection pool established.")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise e
    
    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed.")