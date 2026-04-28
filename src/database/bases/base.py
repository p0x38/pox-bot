import os
import aiofiles
import asyncpg
from typing import Optional
from logger import logger

class PostgreSQLDatabase:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Standard pool initialization."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=self.dsn,
                    min_size=5,
                    max_size=24,
                    command_timeout=60
                )
                logger.info(f"[{self.__class__.__name__}] PostgreSQL connection pool established.")
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Failed to connect to PostgreSQL: {e}")
                raise e
    
    async def setup(self):
        """
        Main entry point for initialization.
        Workflow: Connect -> on_load hook.
        """
        await self.connect()
        await self.on_load()
        logger.debug(f"[{self.__class__.__name__}] Setup sequence completed.")
    
    async def on_load(self):
        """
        Hook: Override this in inherited classes to run table creation or data prep.
        """
        pass
    
    async def execute_sql_file(self, file_path: str):
        """Helper to run raw SQL files."""
        if not os.path.exists(file_path):
            logger.error(f"SQL file not found: {file_path}")
            return
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                sql = await f.read()
            
            if self.pool:
                async with self.pool.acquire() as conn:
                    await conn.execute(sql)
                    logger.info(f"Successfully executed SQL file: {file_path}")
            else:
                raise ConnectionError("Connection pool not available")
        except Exception as e:
            logger.error(f"Error thrown while trying to execute \"{file_path}\": {e}")
    
    async def setup_tables_from_folder(self, folder_name: str):
        sql_dir = f"resource/{folder_name}"
        if os.path.exists(sql_dir):
            for filename in sorted(os.listdir(sql_dir)):
                if filename.endswith(".sql"):
                    await self.execute_sql_file(os.path.join(sql_dir, filename))
    
    async def close(self):
        """
        Main entry point for shutdown.
        Workflow: pre_close hook -> Pool close -> post_close hook.
        """
        logger.info(f"[{self.__class__.__name__}] Initiating shutdown...")

        await self.pre_close()

        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.debug(f"[{self.__class__.__name__}] Pool released.")
        
        await self.post_close()
        logger.info(f"[{self.__class__.__name__}] Shutdown sequence completed.")
    
    async def pre_close(self):
        """Hook: Override to perform actions before the database pool is closed."""
        pass

    async def post_close(self):
        """Hook: Override to perform actions after the database pool is closed."""