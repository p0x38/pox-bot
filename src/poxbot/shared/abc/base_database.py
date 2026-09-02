import contextlib
import re
from abc import ABC
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path as StdPath
from time import perf_counter
from typing import TYPE_CHECKING, Any, ClassVar

from anyio import Path as AsyncPath
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from ...infrastructure.logger import get_logger
from ..exceptions import SQLFileError

if TYPE_CHECKING:
    from ...application.bot import PoxBot
    from ..utils.metrics import Metrics


class BaseDatabase(ABC):  # ruff: ignore[abstract-base-class-without-abstract-method]
    """An abstract base class representing a database using SQLAlchemy.

    This class defines the core asynchronous interface and connection management
    that all specific database implementations must use. It automatically
    handles engine pooling configurations and patches synchronous drivers to
    their async counterparts.

    Do not instantiate this class directly! :3

    Attributes:
        logger (LoggerAdapter): The logger instance configured for the specific
            subclass.
        engine (AsyncEngine): The underlying SQLAlchemy asynchronous engine.
        async_session (async_sessionmaker): A factory for generating AsyncSession
            instances.
    """

    _engines: ClassVar[dict[str, Any]] = {}

    def __init__(self, bot: 'PoxBot', dsn: str):
        """Initialize database settings and creates the async engine.

        Args:
            bot (PoxBot): The main bot instance for metrics.
            dsn: The Data Source Name (connection string) for the database.
        """
        self.logger = get_logger(__name__, prefix=self.__class__.__name__)
        self.bot = bot

        validated_dsn = self._validate_and_patch_dsn(dsn)

        engine_kwargs = {
            'echo': False,
            'pool_pre_ping': True,
            'pool_recycle': 1200,
        }

        if dsn.startswith('sqlite'):
            engine_kwargs['poolclass'] = StaticPool
        else:
            engine_kwargs['pool_size'] = 12
            engine_kwargs['max_overflow'] = 16

        if validated_dsn not in BaseDatabase._engines:
            BaseDatabase._engines[validated_dsn] = create_async_engine(
                validated_dsn, **engine_kwargs
            )

        self.engine = BaseDatabase._engines[validated_dsn]
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    def _validate_and_patch_dsn(self, dsn: str) -> str:
        """Validate the DSN and patch sync drivers to async equivalents.

        Checks if the provided DSN uses standard synchronous prefixes
        (like postgresql://) and switches them to required async
        drivers (like postgresql+asyncpg://).

        Args:
            dsn: The raw connection string to evalute.

        Returns:
            The patched or verified asynchronous DSN string.
        """

        def clean_log_endpoint(url: str) -> str:
            return (
                url.rsplit('@', maxsplit=1)[-1]
                if '@' in url
                else url.rsplit('://', maxsplit=1)[-1]
            )

        if dsn.startswith('postgresql://') and not dsn.startswith(
            'postgresql+asyncpg://',
        ):
            patched = dsn.replace('postgresql://', 'postgresql+asyncpg://', 1)
            self.logger.warning(
                'DSN Patched to use asyncpg driver: %s',
                clean_log_endpoint(patched),
            )
            return patched

        if dsn.startswith('mysql://') and not dsn.startswith('mysql+asyncmy://'):
            patched = dsn.replace('mysql://', 'mysql+asyncmy://', 1)
            self.logger.warning(
                'DSN patched to use asyncmy driver: %s',
                clean_log_endpoint(patched),
            )
            return patched

        if dsn.startswith('sqlite://') and not dsn.startswith('sqlite+aiosqlite://'):
            patched = dsn.replace('sqlite://', 'sqlite+aiosqlite://', 1)
            self.logger.warning(
                'DSN patched to use aiosqlite driver: %s',
                clean_log_endpoint(patched),
            )
            return patched
        return dsn

    async def setup(self):
        """Run the initialization sequence by triggering lifecycle hooks."""
        await self.on_load()
        self.logger.info('Setup sequence completed.')

    async def on_load(self):  # ruff: ignore[empty-method-without-abstract-decorator]
        """Provide a lifecycle hook executed during setup.

        Subclasses should override this method to perform initial tasks
        like table initialization or seeding.
        """
        pass

    async def connect(self):
        """Test the database connection by executing a trivial query."""
        async with self.engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
            self.logger.info('Database connection established successfully.')

    async def execute_raw_file(self, file_path: str | StdPath):
        """Parse and execute a local raw SQL file inside a transaction.

        Splits statements by semicolons and strips out inline SQL comments.

        Args:
            file_path: The Path object pointing to the target .sql file.

        Raises:
            FileNotFoundError: If the specified SQL file does not exist.
        """
        async_path = AsyncPath(file_path)
        if not await async_path.exists():
            raise SQLFileError(str(file_path))

        raw_sql = await async_path.read_text(encoding='utf-8')

        clean_sql = re.sub(r'--.*$', '', raw_sql, flags=re.MULTILINE)
        queries = [q.strip() for q in clean_sql.split(';') if q.strip()]

        async with self.async_session() as session, session.begin():
            for query in queries:
                await session.execute(text(query))

        self.logger.info('Successfully executed: %s', async_path.name)

    async def run_query(self, query: str, params: dict | None = None):
        """Execute a read-only query and return all matching rows.

        Args:
            query: The raw SQL query string to run.
            params: Optional dictionary containing query parameters.

        Returns:
            A list of dictionary-like mappings representing the returned rows.
        """
        query_label = query.strip().split('\n')[0][:40]
        metrics_mgr: Metrics | None = getattr(self.bot, 'metrics', None)

        span_context = (
            metrics_mgr.span_async('bot_database_run_query', query=query_label)
            if metrics_mgr
            else asynccontextmanager(lambda: (yield))()
        )

        async with span_context:
            start_time = perf_counter()
            status = 'success'
            try:
                async with self.async_session() as session, session.begin():
                    result = await session.execute(text(query), params or {})
                    return result.mappings().all()
            except Exception:
                status = 'error'
                raise
            finally:
                if metrics_mgr:
                    latency = perf_counter() - start_time
                    metrics_mgr.record_histogram(
                        name='bot_database_query_duration_seconds',
                        description='Database query execution time in seconds',
                        value=latency,
                        labels={
                            'operation': 'run_query',
                            'status': status,
                            'query': query_label,
                        },
                        unit='s',
                    )
                    metrics_mgr.increment_counter(
                        name='bot_database_queries_total',
                        description='Total number of executed database queries',
                        labels={'operation': 'run_query', 'status': status},
                    )

    async def execute_query(self, query: str, params: dict | None = None):
        """Execute a modifying query whithin a transaction block.

        Args:
            query: The raw SQL statement string to run.
            params: Optional dictionary containing query parameters.
        """
        query_label = query.strip().split('\n')[0][:40]
        metrics_mgr: Metrics | None = getattr(self.bot, 'metrics', None)

        span_context = (
            metrics_mgr.span_async('bot_database_run_query', query=query_label)
            if metrics_mgr
            else asynccontextmanager(lambda: (yield))()
        )

        async with span_context:
            start_time = perf_counter()
            status = 'success'
            try:
                async with self.async_session() as session, session.begin():
                    await session.execute(text(query), params or {})
            except Exception:
                status = 'error'
                raise
            finally:
                if metrics_mgr:
                    latency = perf_counter() - start_time
                    metrics_mgr.record_histogram(
                        name='bot_database_query_duration_seconds',
                        description='Database query execution time in seconds',
                        value=latency,
                        labels={
                            'operation': 'execute_query',
                            'status': status,
                            'query': query_label,
                        },
                        unit='s',
                    )
                    metrics_mgr.increment_counter(
                        name='bot_database_queries_total',
                        description='Total number of executed database queries',
                        labels={'operation': 'execute_query', 'status': status},
                    )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide an asynchronous session generator context manager.

        Yields:
            An active AsyncSession instance.
        """
        async with self.async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close(self):
        """Dispose of the database engine and release all connections."""
        if not BaseDatabase._engines:
            return

        for dsn, engine in list(BaseDatabase._engines.items()):
            with contextlib.suppress(Exception):
                await engine.dispose()
                self.logger.info('Database engine disposed for DSN endpoint: "%s"', dsn)
        BaseDatabase._engines.clear()
