from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import PoxBot


async def shutdown(bot: PoxBot) -> None:
    operations = (
        ('counters', bot.counter_manager.save_async),
        ('database', bot.database.close),
        ('resources', bot.resources.close),
        ('quake_manager', bot.quake_manager.close),
    )

    errors: list[Exception] = []

    for name, operation in operations:
        try:
            await operation()
        except Exception as error:
            bot.logger.exception(
                'Failed to close %s during application shutdown.',
                name,
            )
            errors.append(error)

    if errors:
        raise ExceptionGroup(
            'One or more application shutdown operations failed.',
            errors,
        )
