# ruff: noqa: D101, D102
import asyncio
import fnmatch
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from time import perf_counter
from typing import ClassVar

from discord.ext import commands

from ..infrastructure.logger import get_logger
from ..infrastructure.logger.tracing import start_span

BotLike = commands.Bot | commands.AutoShardedBot

_ignore_words = frozenset({'ignore', 'exclude'})

_wildcards = frozenset({'*', 'all'})


class ExtensionOperation(Enum):
    LOAD = auto()
    UNLOAD = auto()
    RELOAD = auto()

    @property
    def verb(self) -> str:
        return self.name.lower()


class OperationResult(Enum):
    OK = auto()
    FAILED = auto()
    EXCLUDED = auto()
    ALREADY_LOADED = auto()
    ALREADY_UNLOADED = auto()
    NOT_FOUND = auto()


@dataclass(slots=True)
class ExtensionOperationResult:
    result: OperationResult
    extension: str

    affected: int = 0
    failed: int = 0

    operation_time_ms: float = 0.0

    error: str | None = None

    children: list['ExtensionOperationResult'] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.result is OperationResult.OK

    @property
    def skipped(self) -> bool:
        return self.result in {
            OperationResult.ALREADY_LOADED,
            OperationResult.ALREADY_UNLOADED,
            OperationResult.EXCLUDED,
        }

    @property
    def changed(self) -> bool:
        return self.affected > 0


ExtensionCallable = Callable[[BotLike, str], Awaitable[None]]

ProgressCallback = Callable[[ExtensionOperationResult, int, int], Awaitable[None]]


@dataclass(slots=True)
class ExtensionState:
    loaded: bool
    last_operation: ExtensionOperation
    last_error: str | None
    last_operation_ms: float


@dataclass
class ExtensionProgress:
    current: int
    total: int

    loaded: int
    failed: int

    result: ExtensionOperationResult

    @property
    def finished(self) -> bool:
        return self.current == self.total

    @property
    def percent(self) -> float:
        return self.current / self.total * 100


@dataclass
class ExtensionEvent:
    type: str
    progress: ExtensionProgress | None
    result: ExtensionOperationResult | None


class ExtensionManager:
    OP_MAP: ClassVar[dict[ExtensionOperation, ExtensionCallable]] = {
        ExtensionOperation.LOAD: lambda b, x, /: b.load_extension(x),
        ExtensionOperation.UNLOAD: lambda b, x, /: b.unload_extension(x),
        ExtensionOperation.RELOAD: lambda b, x, /: b.reload_extension(x),
    }

    def __init__(
        self,
        cogs_path: str = './src/poxbot/platforms/discord/extensions',
        package: str = 'poxbot.platforms.discord.extensions',
        excluded_extensions: list[str] | None = None,
    ):
        self.extension_logger = get_logger(__name__, prefix='ExtensionManager')
        self.extension_logger.debug('INIT')
        self.extension_logger.debug('cogs_path(raw)=%s', cogs_path)
        self.extension_logger.debug('package=%s', package)
        self.cogs_path = Path(cogs_path)
        self.package = package
        self.excluded_extensions = set(excluded_extensions or [])

        self.states: dict[str, ExtensionState] = {}
        self._paths: dict[str, str] = {}

        self._load_ext_ignore_file()

    def _load_ext_ignore_file(self) -> None:
        ignore_file_path = Path('src/poxbot/assets/.ext-ignore')
        self.extension_logger.debug(
            'loading .ext-ignore from %s', ignore_file_path.resolve(),
        )

        if not ignore_file_path.is_file():
            self.extension_logger.debug(
                'no .ext-ignore file found at %s', ignore_file_path,
            )
            return

        try:
            with ignore_file_path.open('r', encoding='utf-8') as f:
                for line in f:
                    clean_line = line.strip()
                    self.extension_logger.debug('ignore line=%r', clean_line)

                    if not clean_line or clean_line.startswith('#'):
                        continue

                    if not clean_line.replace('_', '').replace('-', '').isalnum():
                        continue

                    self.extension_logger.debug('ignore pattern loaded: %s', clean_line)
                    self.excluded_extensions.add(clean_line)
        except Exception as e:
            self.extension_logger.exception('Failed to read .ext-ignore', exc_info=e)

    def should_ignore(self, extension_name: str) -> bool:
        return any(
            fnmatch.fnmatch(extension_name, pattern)
            for pattern in self.excluded_extensions
        )

    def is_wildcard(
        self,
        extension_name: str,
    ) -> bool:
        self.extension_logger.debug('cogs_path resolved=%s', self.cogs_path.resolve())
        return extension_name in _wildcards

    def get_extension_path(
        self,
        extension_name: str,
    ) -> str:
        extension_name = self.normalize_extension(extension_name)

        return self._paths.setdefault(
            extension_name,
            f'{self.package}.{extension_name}',
        )

    def is_loaded(self, bot: BotLike, ext: str) -> bool:
        ext = self.normalize_extension(ext)
        return any(self.normalize_extension(k) == ext for k in bot.extensions)

    def _map_error(self, e: Exception) -> OperationResult:
        if isinstance(e, commands.ExtensionAlreadyLoaded):
            return OperationResult.ALREADY_LOADED
        if isinstance(e, commands.ExtensionNotLoaded):
            return OperationResult.ALREADY_UNLOADED
        if isinstance(e, commands.ExtensionNotFound):
            return OperationResult.NOT_FOUND
        return OperationResult.FAILED

    def normalize_extension(self, name: str) -> str:
        if name.startswith(self.package):
            return name.rsplit('.', maxsplit=1)[-1]
        return name

    def resolve_extensions(
        self,
        bot: BotLike,
        target: str,
        operation: ExtensionOperation,
    ) -> list[str]:
        if self.is_wildcard(target):
            available_in_folder = []
            self.extension_logger.debug(
                'FILES RAW: %s', list(self.cogs_path.rglob('*.py')),
            )
            for f in self.cogs_path.rglob('*.py'):
                if f.name.startswith('_'):
                    continue

                self.extension_logger.debug('FILE FOUND: %s', f)
                if f.stem == '__init__' or '.ignore' in f.name:
                    continue
                ext_name = f.stem
                self.extension_logger.debug('EXT STEM: %s', ext_name)
                if self.should_ignore(ext_name):
                    self.extension_logger.debug('IGNORED %s', ext_name)
                    continue
                available_in_folder.append(ext_name)

            if operation is ExtensionOperation.LOAD:
                return available_in_folder

            if operation is ExtensionOperation.RELOAD:
                current_loaded = {self.normalize_extension(e) for e in bot.extensions}
                new_extensions = [
                    ext for ext in available_in_folder if ext not in current_loaded
                ]

                return list(current_loaded) + new_extensions
            return list(bot.extensions.keys())
        return [self.normalize_extension(target)]

    def _elapsed_ms(self, start: float) -> float:
        return (perf_counter() - start) * 1000

    async def _run_operation(
        self,
        operation: ExtensionCallable,
        *,
        bot: BotLike,
        extension: str,
        operation_type: ExtensionOperation,
    ) -> ExtensionOperationResult:
        self.extension_logger.debug(
            '_run_operation: ext=%s op=%s',
            extension,
            operation_type,
        )
        start = perf_counter()
        module = self.get_extension_path(extension)

        self.extension_logger.debug('resolved module path=%s', module)

        actual_op: ExtensionCallable = operation
        self.extension_logger.info(
            'Detected new extension "%s". Loading for the first time!',
            extension,
        )

        try:
            await actual_op(bot, module)

            elapsed = self._elapsed_ms(start)

            self.update_state(
                extension,
                loaded=operation_type != ExtensionOperation.UNLOAD,
                elapsed_ms=elapsed,
                operation=operation_type,
            )

            self.extension_logger.debug(
                '%s "%s" completed in %.2f ms',
                operation_type.verb.capitalize(),
                extension,
                elapsed,
            )

            return ExtensionOperationResult(
                result=OperationResult.OK,
                affected=1,
                extension=extension,
                operation_time_ms=elapsed,
            )
        except commands.ExtensionAlreadyLoaded:
            elapsed = self._elapsed_ms(start)

            self.update_state(
                extension,
                loaded=True,
                elapsed_ms=elapsed,
                operation=operation_type,
            )

            self.extension_logger.exception(
                'Failed to %s "%s": Extension already loaded',
                operation_type.verb,
                extension,
            )

            return ExtensionOperationResult(
                result=OperationResult.ALREADY_LOADED,
                extension=extension,
                operation_time_ms=elapsed,
            )
        except commands.ExtensionNotLoaded:
            elapsed = self._elapsed_ms(start)

            self.update_state(
                extension,
                loaded=False,
                elapsed_ms=elapsed,
                operation=operation_type,
            )

            self.extension_logger.exception(
                'Failed to %s "%s": Extension is not loaded',
                operation_type.verb,
                extension,
            )

            return ExtensionOperationResult(
                result=OperationResult.ALREADY_UNLOADED,
                extension=extension,
                operation_time_ms=elapsed,
            )
        except commands.ExtensionNotFound:
            elapsed = self._elapsed_ms(start)

            self.extension_logger.exception(
                'Failed to %s "%s": Extension does not exist',
                operation_type.verb,
                extension,
            )

            return ExtensionOperationResult(
                result=OperationResult.NOT_FOUND,
                extension=extension,
                operation_time_ms=elapsed,
            )
        except commands.ExtensionError as e:
            elapsed = self._elapsed_ms(start)

            self.update_state(
                extension,
                loaded=False,
                elapsed_ms=elapsed,
                error=str(e),
                operation=operation_type,
            )

            self.extension_logger.exception(
                'Failed to %s "%s"',
                operation_type.verb,
                extension,
            )

            return ExtensionOperationResult(
                result=OperationResult.FAILED,
                failed=1,
                extension=extension,
                operation_time_ms=elapsed,
                error=str(e),
            )
        except Exception as e:
            elapsed = self._elapsed_ms(start)

            self.update_state(
                extension,
                loaded=False,
                elapsed_ms=elapsed,
                error=str(e),
                operation=operation_type,
            )

            self.extension_logger.exception(
                'Failed to %s "%s"',
                operation_type.verb,
                extension,
            )

            return ExtensionOperationResult(
                result=OperationResult.FAILED,
                failed=1,
                extension=extension,
                operation_time_ms=elapsed,
                error=str(e),
            )

    async def run_operation(
        self,
        bot: BotLike,
        operation: ExtensionOperation,
        targets: Iterable[str],
        *,
        callback: ProgressCallback | None = None,
        concurrency: int = 5,
        progress_queue: asyncio.Queue | None = None,
    ) -> ExtensionOperationResult:
        self.extension_logger.debug(
            'RUN OPERATION START op=%s targets=%s', operation, list(targets),
        )
        lock = asyncio.Lock()

        start = perf_counter()
        targets_list = list(targets)
        total = len(targets_list)

        with start_span('extension.batch.run') as span:
            span.set_attribute('operation', operation.value)
            span.set_attribute('total_targets', total)
            span.set_attribute('concurrency', concurrency)

            queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue()

            results: list[ExtensionOperationResult] = []
            state = {
                'completed': 0,
                'loaded': 0,
                'failed': 0,
                'total_elapsed_time_ms': 0,
            }
            for i, ext in enumerate(targets_list, start=1):
                queue.put_nowait((i, ext))

            async def worker(worker_id: int):
                while True:
                    item = await queue.get()

                    if item is None:
                        queue.task_done()
                        break

                    self.extension_logger.debug(
                        '[worker %d] got item=%s', worker_id, item,
                    )

                    queue_session_start = perf_counter()
                    index, ext = item

                    self.extension_logger.debug(
                        '[worker %d] executing ext=%s', worker_id, ext,
                    )

                    with start_span('extension.worker.execute') as span:
                        span.set_attribute('worker_id', worker_id)
                        span.set_attribute('extension', ext)

                        try:
                            op = self.OP_MAP[operation]
                            self.extension_logger.debug(
                                'operation mapped: %s -> %s', operation, op,
                            )

                            result = await self._run_operation(
                                op,
                                bot=bot,
                                extension=ext,
                                operation_type=operation,
                            )
                        except Exception as e:
                            self.extension_logger.exception(
                                'worker %s failed on %s',
                                worker_id,
                                ext,
                            )

                            queue_elapsed = self._elapsed_ms(queue_session_start)

                            result = ExtensionOperationResult(
                                result=OperationResult.FAILED,
                                operation_time_ms=queue_elapsed,
                                extension=ext,
                                error=str(e),
                                failed=1,
                            )

                    async with lock:
                        results.append(result)

                        state['completed'] += 1
                        state['loaded'] += result.affected
                        state['failed'] += result.failed

                        current = state['completed']

                    if progress_queue:
                        await progress_queue.put(
                            ExtensionProgress(
                                current=current,
                                total=total,
                                loaded=state['loaded'],
                                failed=state['failed'],
                                result=result,
                            ),
                        )

                    if callback:
                        try:
                            await callback(result, index, total)
                        except Exception:
                            self.extension_logger.exception('callback failed')

                    queue.task_done()

            workers = [asyncio.create_task(worker(i)) for i in range(concurrency)]
            self.extension_logger.debug('spawned %d workers', len(workers))

            for _ in range(concurrency):
                queue.put_nowait(None)

            await queue.join()
            await asyncio.gather(*workers, return_exceptions=True)

            if progress_queue:
                await progress_queue.put(None)

            affected = sum(r.affected for r in results)
            failed = sum(r.failed for r in results)

            return ExtensionOperationResult(
                result=OperationResult.OK if failed == 0 else OperationResult.FAILED,
                extension='*',
                affected=affected,
                failed=failed,
                operation_time_ms=self._elapsed_ms(start),
                children=results,
            )

    async def stream_operation(
        self,
        bot: BotLike,
        operation: ExtensionOperation,
        targets: Iterable[str],
        *,
        concurrency: int = 5,
        callback: ProgressCallback | None = None,
        exclusions: Iterable[str] | None = None,
    ) -> AsyncIterator[ExtensionProgress]:
        temp_exclusions = set(exclusions or [])
        full_exclusions = self.excluded_extensions | temp_exclusions

        filtered_targets = [t for t in targets if t not in full_exclusions]

        queue: asyncio.Queue[ExtensionProgress] = asyncio.Queue()

        task = asyncio.create_task(
            self.run_operation(
                bot,
                operation,
                filtered_targets,
                concurrency=concurrency,
                callback=callback,
                progress_queue=queue,
            ),
        )

        while True:
            item = await queue.get()

            if item is None:
                break

            yield item

        await task

    async def load_extensions(
        self,
        bot: BotLike,
        callback: ProgressCallback | None = None,
    ) -> ExtensionOperationResult:
        targets = self.resolve_extensions(bot, '*', ExtensionOperation.LOAD)

        return await self.run_operation(
            bot,
            ExtensionOperation.LOAD,
            targets,
            callback=callback,
        )

    async def load_single(
        self,
        bot: BotLike,
        extension_name: str,
    ) -> ExtensionOperationResult:
        targets = self.resolve_extensions(bot, extension_name, ExtensionOperation.LOAD)
        return await self.run_operation(bot, ExtensionOperation.LOAD, targets)

    async def unload(
        self,
        bot: BotLike,
        extension_name: str,
    ) -> ExtensionOperationResult:
        targets = self.resolve_extensions(
            bot,
            extension_name,
            ExtensionOperation.UNLOAD,
        )
        return await self.run_operation(bot, ExtensionOperation.UNLOAD, targets)

    async def reload(
        self,
        bot: BotLike,
        extension_name: str,
    ) -> ExtensionOperationResult:
        targets = self.resolve_extensions(
            bot,
            extension_name,
            ExtensionOperation.RELOAD,
        )
        return await self.run_operation(bot, ExtensionOperation.RELOAD, targets)

    def update_state(
        self,
        extension: str,
        *,
        loaded: bool,
        elapsed_ms: float,
        operation: ExtensionOperation,
        error: str | None = None,
    ) -> None:
        self.states[extension] = ExtensionState(
            loaded=loaded,
            last_operation=operation,
            last_error=error,
            last_operation_ms=elapsed_ms,
        )

    def get_state(self, extension: str) -> ExtensionState | None:
        return self.states.get(extension)

    def add_exclusion(self, extension_name: str):
        self.excluded_extensions.add(extension_name)
        self.extension_logger.info("Added '%s' to exclusion list.", extension_name)

    def remove_exclusion(self, extension_name: str):
        self.excluded_extensions.discard(extension_name)
        self.extension_logger.info("Removed '%s' from exclusion list.", extension_name)

    @property
    def exclusions(self) -> set[str]:
        return self.excluded_extensions
