import re
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.logger_factory.logger import setup_logger


class BaseDatabase:
    _engine = None

    def __init__(self, dsn: str):
        self.logger = setup_logger(__name__, self.__class__.__name__)

        validated_dsn = self._validate_and_patch_dsn(dsn)

        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,
            "pool_recycle": 1200,
        }

        if dsn.startswith("sqlite"):
            engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs["pool_size"] = 12
            engine_kwargs["max_overflow"] = 16

        if BaseDatabase._engine is None:
            BaseDatabase._engine = create_async_engine(
                validated_dsn, **engine_kwargs
            )

        self.engine = BaseDatabase._engine
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    def _validate_and_patch_dsn(self, dsn: str) -> str:
        if dsn.startswith("postgresql://") and not dsn.startswith("postgresql+asyncpg://"):
            patched = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
            self.logger.warning(f"DSN Patched to use asyncpg driver: {patched.split('@')[-1]}")
            return patched
        elif dsn.startswith("mysql://") and not dsn.startswith("mysql+asyncmy://"):
            patched = dsn.replace("mysql://", "mysql+asyncmy://", 1)
            self.logger.warning(f"DSN patched to use asyncmy driver: {patched.split('@')[-1]}")
            return patched
        elif dsn.startswith("sqlite://") and not dsn.startswith("sqlite+aiosqlite://"):
            patched = dsn.replace("sqlite://", "sqlite+aiosqlite://", 1)
            self.logger.warning(f"DSN patched to use aiosqlite driver: {patched.split('@')[-1]}")
            return patched
        return dsn

    async def setup(self):
        """Abstract the initialization process"""
        await self.on_load()
        self.logger.info("Setup sequence completed.")

    async def on_load(self):
        pass

    async def connect(self):
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            self.logger.info("Database connection established successfully.")

    async def execute_raw_file(self, file_path: Path):
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        raw_sql = file_path.read_text(encoding='utf-8')

        clean_sql = re.sub(r'--.*$', '', raw_sql, flags=re.MULTILINE)
        queries = [q.strip() for q in clean_sql.split(";") if q.strip()]

        async with self.async_session() as session, session.begin():
            for query in queries:
                await session.execute(text(query))

        self.logger.info(f"Successfully executed: {file_path.name}")

    async def run_query(self, query: str, params: dict | None = None):
        async with self.async_session() as session:
            result = await session.execute(text(query), params or {})
            return result.mappings().all()

    async def execute_query(self, query: str, params: dict | None = None):
        async with self.async_session() as session, session.begin():
            await session.execute(text(query), params or {})

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close(self):
        await self.engine.dispose()
        self.logger.info("Database engine disposed.")
