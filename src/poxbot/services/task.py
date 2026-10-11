import asyncio
from collections.abc import Coroutine
from typing import Any

from ..infrastructure.logger.setup import get_logger


class TaskManager:
    def __init__(self):
        self.logger = get_logger(__name__, prefix='TaskManager')
        self.tasks: set[asyncio.Task[Any]] = set()

    def create(
        self,
        name: str,
        coro: Coroutine[Any, Any, Any],
    ) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)

        self.logger.info(
            'task.spawned',
            extra={
                'task': name,
            },
        )

        task.add_done_callback(self._on_task_done)

        return task

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)

        extra = {'task': task.get_name()}

        if task.cancelled():
            self.logger.debug('task.cancelled', extra=extra)
            return

        exception = task.exception()

        if exception is None:
            self.logger.info('task.finished', extra=extra)
            return

        self.logger.error(
            'task.failed',
            exc_info=(
                type(exception),
                exception,
                exception.__traceback__,
            ),
            extra=extra,
        )

    def cancel(self, name: str) -> None:
        for task in tuple(self.tasks):
            if task.get_name() == name:
                task.cancel()

    async def cancell_all(self) -> None:
        tasks = tuple(self.tasks)

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
