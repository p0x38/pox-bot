import glob
from itertools import islice
import os
from pathlib import Path
import tempfile
from time import time
import uuid
from aiocache import cached
import aiofiles
from discord.ext.commands import Cog
from discord import DMChannel, HTTPException, Message, TextChannel, app_commands, Embed, Interaction, File
from discord.app_commands import locale_str
import markovify
from io import BytesIO
from datetime import datetime
import random
from os.path import dirname, join
from typing import Optional

from bot import PoxBot
from logger import logger
import stuff

class AdminCog(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    @Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or message.author.system: return

        if isinstance(message.channel, DMChannel):

            if message.author.id == self.bot.owner_id:
                args = message.content.split()
                
                if args[0] == "_adm":
                    match (args[1]):
                        case "leave":
                            guild_id = stuff.get_int(args[2])

                            if guild_id in [0,-1]:
                                await message.reply("Invalid guild ID.")
                                return
                            
                            try:
                                guild = self.bot.get_guild(guild_id)

                                if guild:
                                    await guild.leave()
                                    await message.reply("Operation successful")
                            except Exception as e:
                                logger.exception(e)
                        case _:
                            await message.reply("Invalid command!")
                            
async def setup(bot):
    await bot.add_cog(AdminCog(bot))