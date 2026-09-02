import asyncio
import contextlib
import logging
from importlib.metadata import version

from .bootstrap import Bootstrap

__version__ = version('pox-bot')


async def main(bootstrap: Bootstrap):
    """Run the bot runtime lifecycle and optional Textual dashboard."""
    context = await bootstrap.create_context()
    dashboard = context.dashboard
    dashboard_task = None

    if dashboard is not None:
        dashboard.set_status('Starting Textual dashboard')
        dashboard_task = asyncio.create_task(dashboard.run_async())
        await asyncio.sleep(0.05)

    context.logger.info('Starting web api...')
    web_server_task = asyncio.create_task(context.fastapi_class.start_server())

    try:
        while True:
            bot = await bootstrap.create_bot()

            async with bot:
                try:
                    bot.context.logger.info('Starting bot...')
                    await bot.start(bootstrap.token)
                except Exception:
                    bot.context.logger.exception(
                        'Exception occured while running the bot',
                    )
                    break

            if not bot.should_restart:
                break

            bot.context.logger.info('Bot instance will restart in 5 seconds...')
            await asyncio.sleep(5)
    finally:
        web_server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await web_server_task

        if dashboard_task is not None and dashboard is not None:
            dashboard.stop()
            with contextlib.suppress(asyncio.CancelledError):
                await dashboard_task


def run(namespace: object | None = None):
    """Execute the bot entry point and optionally enable a Textual dashboard."""
    textual_enabled = (
        bool(getattr(namespace, 'textual', False)) if namespace is not None else False
    )
    bootstrap = Bootstrap(show_textual=textual_enabled)

    try:
        asyncio.run(main(bootstrap))
    except KeyboardInterrupt:
        pass
    except Exception:
        if bootstrap._context is not None:
            bootstrap.context.logger.exception('Uncaught exception!')
        else:
            logging.getLogger(__name__).exception('Uncaught exception!')
    finally:
        if bootstrap._context is not None:
            bootstrap.context.logger.info('Bot has been closed.')
