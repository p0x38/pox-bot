import random
import time
from os.path import exists, join

import aiofiles
from aiohttp import ClientConnectionError
from discord import (
    Activity,
    ActivityType,
    ConnectionClosed,
    CustomActivity,
    HTTPException,
    Status,
)
from discord.ext import commands, tasks

from logger import logger
from src.bot import PoxBot


class InactivityCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.PRIMARY_INACTIVITY_THRESHOLD = 60 * 2.5
        self.SECONDARY_INACTIVITY_THRESHOLD = 60 * 1
        self.FINAL_INACTIVITY_THRESHOLD = 60 * 5
        self.last_activity_time = time.time()
        self.current_state = 0
        self.inactivity_enabled = False
        self.status_message_path = join(self.bot.root_path, "assets/status.txt")
        self.status_messages = ["Well, I could take your right eye."]

        self.status_check_loop.start()

    async def cog_load(self) -> None:
        if not exists(self.status_message_path):
            logger.warning("status.txt not found.")
            self.status_messages = [":/"]
            return

        async with aiofiles.open(self.status_message_path, encoding="utf-8") as f:
            content = await f.read()
            self.status_messages = [line.strip() for line in content.splitlines() if line.strip()]

    async def cog_unload(self):
        self.status_check_loop.cancel()

    async def generate_status(self):
        total_guilds = len(self.bot.guilds)

        if self.status_messages:
            chosen = random.choice(self.status_messages)
        else:
            logger.warning("status_messages is empty. Fallback to default message")
            chosen = "It seems there's no status messages been loaded."

        rand = random.random()

        if rand > .7:
            return {
                "status": Status.online,
                "activity": Activity(
                    type=ActivityType.watching,
                    name="You."
                )
            }
        else:
            return {
                "status": Status.online,
                "activity": CustomActivity(
                    name=f"{total_guilds} {chosen}"
                )
            }

    @tasks.loop(seconds=30.0)
    async def status_check_loop(self):
        await self.bot.wait_until_ready()

        try:
            presence_data = await self.generate_status()

            if "status" in presence_data and "activity" in presence_data:
                await self.bot.change_presence(
                    status=presence_data['status'],
                    activity=presence_data['activity']
                )
            else:
                logger.warning("Failed to verify the generated presence_data")
        except (ConnectionClosed, ClientConnectionError, HTTPException):
            logger.warning("Connection has been closed unexpectedly", exc_info=True)
        except Exception as e:
            logger.error("Exception thrown while trying to change presence", exc_info=True)
            raise e from e
    # @tasks.loop(seconds=30.0)
    # async def status_check_loop(self):
    #    await self.bot.wait_until_ready()
    #    await self.bot.change_presence(
    #        activity=CustomActivity(
        # name="".join(random.choices(string.ascii_letters + string.digits, k=16)))
    #    )


async def setup(bot):
    await bot.add_cog(InactivityCog(bot))
