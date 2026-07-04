import asyncio
import contextlib
from importlib.metadata import version

from .bootstrap import Bootstrap

__version__ = version('pox-bot')


async def main(bootstrap: Bootstrap):
    context = await bootstrap.create_context()
    
    context.logger.info("Starting web api...")
    web_server_task = asyncio.create_task(context.fastapi_class.start_server())
    
    while True:
        bot = await bootstrap.create_bot()
        
        async with bot:
            try:
                bot.context.logger.info("Starting bot...")
                await bot.start(bootstrap.token)
            except Exception:
                bot.context.logger.exception("Exception occured while running the bot")
                break
        
        if not bot.should_restart:
            break
        
        bot.context.logger.info("Bot instance will restart in 5 seconds...")
        await asyncio.sleep(5)
    
    web_server_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await web_server_task


def run():
    bootstrap = Bootstrap()
    
    try:
        asyncio.run(main(bootstrap))
    except KeyboardInterrupt:
        pass
    except Exception:
        bootstrap.context.logger.exception("Uncaught exception!")
    finally:
        if bootstrap._context is not None:
            bootstrap.context.logger.info("Bot has been closed.")
