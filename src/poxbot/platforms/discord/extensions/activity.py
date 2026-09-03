from datetime import datetime

import aiofiles
import numpy as np
from aiohttp.client_exceptions import ClientConnectionError
from discord import (
    Activity,
    ActivityType,
    ConnectionClosed,
    CustomActivity,
    HTTPException,
    Status,
)
from discord.ext import commands, tasks
from pytz import UTC

from ....application.bot import PoxBot


class ActivityCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.rng = np.random.default_rng()
        self.last_activity_timestamp = datetime.now(UTC)
        self.status_message_path = bot.resources.get_asset_path('texts/status.txt')
        self.status_messages = ['Well, I could take your lungs.']

        self.status_check_loop.start()

    async def cog_load(self) -> None:
        if not self.status_message_path.exists():
            self.bot.logger.warning('%s not found.', self.status_message_path.resolve())
            self.status_messages = ['This will shown when activity errored :/']
            return

        async with aiofiles.open(self.status_message_path, encoding='utf-8') as f:
            content = await f.read()
            self.status_messages = [
                line.strip() for line in content.splitlines() if line.strip()
            ]

    async def cog_unload(self):
        self.status_check_loop.cancel()

    async def generate_status(self):
        if self.status_messages:
            chosen = self.rng.choice(self.status_messages)
        else:
            self.bot.logger.warning(
                'status_messages is empty. Fallback to default message',
            )
            chosen = "It seems there's no status messages been loaded."

        rand = self.rng.random()

        if rand > 0.7:
            return {
                'status': Status.online,
                'activity': Activity(
                    type=ActivityType.watching,
                    name='You.',
                ),
            }
        return {
            'status': Status.online,
            'activity': CustomActivity(
                name=chosen,
            ),
        }

    @tasks.loop(seconds=30.0)
    async def status_check_loop(self):
        await self.bot.wait_until_ready()

        try:
            presence_data = await self.generate_status()

            if 'status' in presence_data and 'activity' in presence_data:
                await self.bot.change_presence(
                    status=presence_data['status'],
                    activity=presence_data['activity'],
                )
            else:
                self.bot.logger.warning('Failed to verify the generated presence_data')
        except (ConnectionClosed, ClientConnectionError, HTTPException) as e:
            self.bot.logger.warning(
                'Connection has been closed unexpectedly, with exception %s',
                e,
                exc_info=False,
            )
        except Exception as e:
            self.bot.logger.exception(
                'Exception thrown while trying to change presence',
            )
            raise e from e


async def setup(bot: PoxBot):
    await bot.add_cog(ActivityCog(bot))
