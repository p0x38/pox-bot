import random
import time
import aiofiles
from discord.ext import commands, tasks
from discord import Activity, ActivityType, CustomActivity, Status
from os.path import exists, join

from bot import PoxBot
from logger import logger

class InactivityCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.PRIMARY_INACTIVITY_THRESHOLD = 60 * 2.5
        self.SECONDARY_INACTIVITY_THRESHOLD = 60 * 1
        self.FINAL_INACTIVITY_THRESHOLD = 60 * 5
        self.last_activity_time = time.time()
        self.current_state = 0
        self.inactivity_enabled = False
        self.status_message_path = join(self.bot.root_path, "resources/status.txt")
        self.status_messages = ["Well, I could take your right eye."]
        self.type = 0

        self.status_check_loop.start()
    
    async def cog_load(self) -> None:
        if not exists(self.status_message_path):
            logger.warning("status.txt not found.")
            self.status_messages = [":/"]
            return
        
        async with aiofiles.open(self.status_message_path, "r", encoding="utf-8") as f:
            content = await f.read()
            self.status_messages = [line.strip() for line in content.splitlines() if line.strip()]
    
    async def cog_unload(self):
        self.status_check_loop.cancel()
    
    @tasks.loop(seconds=30.0)
    async def status_check_loop(self):
        await self.bot.wait_until_ready()
        total = len(self.bot.guilds)
        active = len([guild for guild in self.bot.guilds if not guild.unavailable])
        
        if self.status_messages:
            choosen = random.choice(self.status_messages)
        else:
            logger.warning("status_messages is empty. Skipping update")
            choosen = "It seems there's no status messages been loaded."
        
        self.type = random.randint(0,10)
        if self.type > 7:
            await self.bot.change_presence(
                status=Status.online,
                activity=Activity(type=ActivityType.watching, name="You.")
            )
        else:
            await self.bot.change_presence(
                status=Status.online,
                activity=CustomActivity(name=f"{total}/{active} servers; {choosen}")
            )
    #@tasks.loop(seconds=30.0)
    #async def status_check_loop(self):
    #    await self.bot.wait_until_ready()
    #    await self.bot.change_presence(
    #        activity=CustomActivity(name="".join(random.choices(string.ascii_letters + string.digits, k=16)))
    #    )

async def setup(bot):
    await bot.add_cog(InactivityCog(bot))