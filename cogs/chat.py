import discord
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from bot import PoxBot

from discord.ext.commands import Cog
from logger import logger

def get_int(i):
    try:
        return int(i)
    except ValueError:
        return 0

class Chat(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

        self.current_channel = None
        self.prompt_session = PromptSession()
    
    async def read(self):
        while True:
            with patch_stdout():
                content = await self.prompt_session.prompt_async("> ")
                args = content.split(" ")
    
                if content.startswith('/'):
                    match (args[0]):
                        case '/setchannel':
                            temp_int = get_int(args[1])
                            if temp_int == 0:
                                logger.warning("maybe you put 0 or returned value error")
                            else:
                                temp = self.bot.get_channel(get_int(temp_int))
                                if temp:
                                    if isinstance(temp, discord.TextChannel):
                                        self.current_channel = temp
                                        logger.info("Set current to {}".format(self.current_channel.name))
                                    else:
                                        logger.warning("Not an text channel")
                                else:
                                    logger.warning("Channel not found")
                        case '/channels':
                            for channel in self.bot.get_all_channels():
                                if channel.permissions_for(channel.guild.me).send_messages:
                                    logger.info(f"[{channel.id}]: {channel.guild.name} - #{channel.name}")
                        case '/servers':
                            for guild in self.bot.guilds:
                                logger.info(f"[{guild.id}]: {guild.name}")
                        case '/info':
                            rows_to_add = {
                                'User ID': self.bot.user.id if self.bot.user else "Unknown",
                                'User name': self.bot.user.name if self.bot.user else "Unknown",
                                'Guild count': len(self.bot.guilds),
                                'Users I can see': len(self.bot.users),
                                'Current channel': f"[{self.current_channel.guild.id}/{self.current_channel.id}]: {self.current_channel.guild.name} - #{self.current_channel.name}" if self.current_channel else 'None',
                            }
    
                            for key,value in rows_to_add.items():
                                logger.info(f"{key}: {value}")
                        case '/exit':
                            await self.bot.close()
                        case _:
                            logger.warning("Unknown command.")
                else:
                    if self.current_channel and isinstance(self.current_channel, discord.TextChannel):
                        try:
                            await self.current_channel.send(content)
                        except Exception as e:
                            logger.exception(f"Error occured: {e}")
                    else:
                        logger.warning("You're in empty channel")
    
    @Cog.listener()
    async def on_ready(self):
        await self.bot.loop.create_task(self.read())
    
    @Cog.listener()
    async def on_message(self, message: discord.Message):
        logger.debug(f"{message.author.name}: {message.clean_content.strip()}")

async def setup(bot):
    await bot.add_cog(Chat(bot))