import asyncio
import fnmatch
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from time import perf_counter

from discord.ext import commands

from ..logger_factory import setup_logger

extension_logger = setup_logger(__name__)

BotLike = commands.Bot | commands.AutoShardedBot

_ignore_words = frozenset({"ignore", "exclude"})

_wildcards = frozenset({"*", "all"})


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

    children: list["ExtensionOperationResult"] = field(default_factory=list)

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

ProgressCallback = Callable[
    [ExtensionOperationResult, int, int],
    Awaitable[None]
]


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
    OP_MAP = {
        ExtensionOperation.LOAD: lambda b, x: b.load_extension(x),
        ExtensionOperation.UNLOAD: lambda b, x: b.unload_extension(x),
        ExtensionOperation.RELOAD: lambda b, x: b.reload_extension(x),
    }

    def __init__(
        self,
        cogs_path: str = "./src/extensions",
        package: str = "src.extensions",
        excluded_extensions: list[str] | None = None,
    ):
        self.cogs_path = Path(cogs_path)
        self.package = package
        self.excluded_extensions = set(excluded_extensions or [])

        self.states: dict[str, ExtensionState] = {}
        self._paths: dict[str, str] = {}

        self._load_ext_ignore_file()

    def _load_ext_ignore_file(self) -> None:
        ignore_file_path = Path("src/assets/.ext-ignore")

        if not ignore_file_path.is_file():
            return

        try:
            with ignore_file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    clean_line = line.strip()

                    if not clean_line or clean_line.startswith("#"):
                        continue

                    self.excluded_extensions.add(clean_line)
        except Exception as e:
            extension_logger.error(f"Failed to read .ext-ignore: {e}")

    def should_ignore(self, extension_name: str) -> bool:
        return any(
            fnmatch.fnmatch(extension_name, pattern)
            for pattern in self.excluded_extensions
        )

    def is_wildcard(
        self,
        extension_name: str,
    ) -> bool:
        return extension_name in _wildcards

    def get_extension_path(
        self,
        extension_name: str,
    ) -> str:
        return self._paths.setdefault(
            extension_name,
            f"{self.package}.{extension_name}"
        )

    def _map_error(self, e: Exception) -> OperationResult:
        if isinstance(e, commands.ExtensionAlreadyLoaded):
            return OperationResult.ALREADY_LOADED
        if isinstance(e, commands.ExtensionNotLoaded):
            return OperationResult.ALREADY_UNLOADED
        if isinstance(e, commands.ExtensionNotFound):
            return OperationResult.NOT_FOUND
        return OperationResult.FAILED

    def resolve_extensions(
        self,
        bot: BotLike,
        target: str,
        operation: ExtensionOperation,
    ) -> list[str]:
        if self.is_wildcard(target):
            if operation is ExtensionOperation.LOAD:
                resolved = []
                for f in self.cogs_path.glob("*.py"):
                    if f.stem == "__init__":
                        continue
                    
                    if ".ignore" in f.name:
                        continue

                    ext_name = f.stem

                    if self.should_ignore(ext_name):
                        continue

                    resolved.append(ext_name)
                return resolved
            return list(bot.extensions.keys())
        return [target]

    def _elapsed_ms(self, start: float) -> float:
        return (perf_counter() - start) * 1000

    async def _run_operation(
        self,
        operation: ExtensionCallable, *,
        bot: BotLike,
        extension: str,
        operation_type: ExtensionOperation,
    ) -> ExtensionOperationResult:
        start = perf_counter()

        try:
            module = self.get_extension_path(extension)
            await operation(bot, module)

            elapsed = self._elapsed_ms(start)

            self.update_state(
                extension,
                loaded=operation_type is not ExtensionOperation.UNLOAD,
                elapsed_ms=elapsed,
                operation=operation_type,
            )

            extension_logger.debug(
                '%s "%s" completed in %.2f ms',
                operation_type.verb.capitalize(),
                extension,
                elapsed
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

            extension_logger.exception(
                'Failed to %s "%s": Extension already loaded',
                operation_type.verb,
                extension
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

            extension_logger.exception(
                'Failed to %s "%s": Extension is not loaded',
                operation_type.verb,
                extension
            )

            return ExtensionOperationResult(
                result=OperationResult.ALREADY_UNLOADED,
                extension=extension,
                operation_time_ms=elapsed,
            )
        except commands.ExtensionNotFound:
            elapsed = self._elapsed_ms(start)

            extension_logger.exception(
                'Failed to %s "%s": Extension does not exist',
                operation_type.verb,
                extension
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

            extension_logger.exception(
                'Failed to %s "%s"',
                operation_type.verb,
                extension
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

            extension_logger.exception(
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
        queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue()
        results: list[ExtensionOperationResult] = []
        state = {
            "completed": 0,
            "loaded": 0,
            "failed": 0,
            "total_elapsed_time_ms": 0,
        }
        lock = asyncio.Lock()

        start = perf_counter()
        targets_list = list(targets)
        total = len(targets_list)

        for i, ext in enumerate(targets_list, start=1):
            queue.put_nowait((i, ext))

        async def worker(worker_id: int):
            while True:
                item = await queue.get()

                if item is None:
                    queue.task_done()
                    break

                queue_session_start = perf_counter()
                index, ext = item

                try:
                    op = self.OP_MAP[operation]

                    result = await self._run_operation(
                        op,
                        bot=bot,
                        extension=ext,
                        operation_type=operation
                    )
                except Exception as e:
                    extension_logger.exception(
                        "worker %s failed on %s",
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

                    state["completed"] += 1
                    state["loaded"] += result.affected
                    state["failed"] += result.failed

                    current = state["completed"]

                if progress_queue:
                    await progress_queue.put(
                        ExtensionProgress(
                            current=current,
                            total=total,
                            loaded=state['loaded'],
                            failed=state['failed'],
                            result=result,
                        )
                    )

                if callback:
                    try:
                        await callback(result, index, total)
                    except Exception:
                        extension_logger.exception("callback failed")

                queue.task_done()

        workers = [
            asyncio.create_task(worker(i))
            for i in range(concurrency)
        ]

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
            extension="*",
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
            )
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
        callback: ProgressCallback | None = None
    ) -> ExtensionOperationResult:
        targets = self.resolve_extensions(bot, "*", ExtensionOperation.LOAD)

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
        targets = self.resolve_extensions(bot, extension_name, ExtensionOperation.UNLOAD)
        return await self.run_operation(bot, ExtensionOperation.UNLOAD, targets)

    async def reload(
        self,
        bot: BotLike,
        extension_name: str,
    ) -> ExtensionOperationResult:
        targets = self.resolve_extensions(bot, extension_name, ExtensionOperation.RELOAD)
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

    def get_state(
        self,
        extension: str
    ) -> ExtensionState | None:
        return self.states.get(extension)

    def add_exclusion(self, extension_name: str):
        self.excluded_extensions.add(extension_name)
        extension_logger.info(f"Added '{extension_name}' to exclusion list.")

    def remove_exclusion(self, extension_name: str):
        self.excluded_extensions.discard(extension_name)
        extension_logger.info(f"Removed '{extension_name}' from exclusion list.")

    @property
    def exclusions(self) -> set[str]:
        return self.excluded_extensions
