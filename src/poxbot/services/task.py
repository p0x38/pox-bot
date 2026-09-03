import asyncio

from ..infrastructure.logger.setup import get_logger


class TaskManager:
    def __init__(self):
        self.logger = get_logger(__name__, prefix='TaskManager')
        self.tasks: set[asyncio.Task] = set()

    def create(self, name: str, coro):
        task = asyncio.create_task(coro)

        self.tasks.add(task)
        task.set_name(name)
        self.logger.info(
            'task.spawned',
            extra={
                'task': name,
            },
        )
        task.add_done_callback(
            lambda t: self.logger.info(
                'task.finished',
                extra={'task': t.get_name()},
            )
        )
        return task

    def cancel(self, name: str):
        matched = [t for t in self.tasks if t.get_name() == name]

        if matched:
            for task in matched:
                task.cancel()

    def cancell_all(self):
        for t in self.tasks:
            t.cancel()
