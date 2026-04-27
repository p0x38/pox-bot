import json
import time
from typing import Optional
from discord.ext import commands
from discord import Color, Embed, Interaction, Member, Message, app_commands
from os.path import exists, join

import aiofiles

from bot import PoxBot
import data
from logger import logger

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.user_data = {}
        self.XP_COOLDOWN = 10
        self.XP_PER_MESSAGE = 10
        self.path = join(self.bot.root_path, "data/xp.json")
        self.is_loaded = False
    
    group = app_commands.Group(name="level", description="An group for leveling system")

    async def get_user_data(self, user_id):
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "xp": 0,
                "level": 1,
                "last_xp_gain": 0.0
            }
        return self.user_data[user_id]
    
    async def _load_user_data(self):
        if not exists(self.path):
            logger.warning("XP Data file not found. Starting with empty data.")
            self.is_loaded = True
            return {}
        
        try:
            async with aiofiles.open(self.path, mode='r') as f:
                content = await f.read()
            
            raw_data = json.loads(content)
            self.user_data = {int(k): v for k, v in raw_data.items()}
            logger.info("XP Data loaded successfully")
        except json.JSONDecodeError:
            logger.error("Error decoding JSON. Starting with empty data.")
            self.user_data = {}
        
        self.is_loaded = True
        return self.user_data

    async def _save_user_data(self):
        if self.is_loaded != True:
            logger.warning("Data not loaded yet. skipping save.")
            return
        
        data_to_save = {str(k): v for k, v in self.user_data.items()}

        try:
            async with aiofiles.open(self.path, mode='w+') as f:
                await f.write(json.dumps(data_to_save, indent=4))
            #logger.info("XP Data saved successfully")
        except Exception as e:
            logger.exception(f"Error saving XP data asynchronously: {e}")

    async def save_user_data(self):
        await self._save_user_data()
    
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.is_loaded:
            logger.info("Beginning asynchronous data load...")
            await self._load_user_data()
    
    async def cog_unload(self):
        logger.info("Unloading XPSystem Cog. Performing asynchronous final data save...")
        await self._save_user_data()

    def get_required_xp_to_level_up(self, current: int):
        return (5 * (current ** 2)) + (50 * current) + 100
    
    async def check_level_up(self, user_id, channel, guild_id, user_record):
        xp = user_record['xp']
        level = user_record['level']

        leveled_up = False

        while True:
            xp_next = self.get_required_xp_to_level_up(level)

            if xp >= xp_next:
                leveled_up = True
                level += 1

                xp -= xp_next

                user_record['level'] = level
                user_record['xp'] = xp
                await self.save_user_data()

                datainfo = self.bot.servers_data.get(str(guild_id))

                if isinstance(datainfo, dict):
                    if datainfo.get('enable_level_notify') == True:
                        user = self.bot.get_user(user_id)
                        if user:
                            await channel.send(
                                f"{user.mention} has leveled up to {level}."
                            )

                continue
            else:
                break
        return leveled_up
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not self.is_loaded: return
        if message.author.bot or not message.guild: return

        user_id = message.author.id
        user_record = await self.get_user_data(user_id)

        current_time = time.time()

        if current_time - user_record["last_xp_gain"] >= self.XP_COOLDOWN:
            user_record["xp"] += int(self.XP_PER_MESSAGE * (len(message.content) / 32))
            user_record["last_xp_gain"] = current_time
            await self.save_user_data()

            await self.check_level_up(user_id, message.channel, message.guild.id, user_record)
    
    @group.command(name="info", description="Shows info of points for user.")
    async def rank(self, interaction: Interaction, member: Optional[Member] = None):
        if not self.is_loaded:
            return interaction.response.send_message("Bot data is still loading!! 3:")

        target = member or interaction.user
        user_record = await self.get_user_data(target.id)

        level = user_record['level']
        xp = user_record['xp']

        xp_next = self.get_required_xp_to_level_up(level)

        progress_percent = (xp/xp_next)*100

        BAR_LENGTH = 20
        filled_blocks = int((xp/xp_next)*BAR_LENGTH)
        empty_blocks = BAR_LENGTH - filled_blocks
        progress_bar = f"[{'█' * filled_blocks}{'░' * empty_blocks}]"

        embed = Embed(
            title=f"{target.display_name}'s Rank",
            color=Color.green()
        )
        embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)

        embed.add_field(name="Current Level", value=f"{level:,}", inline=True)
        embed.add_field(name="Current XP", value=f"{xp:,}", inline=True)
        embed.add_field(
            name=f"XP to Level {level + 1:,}",
            value=f"{xp_next - xp:,} XP required",
            inline=True
        )
        embed.add_field(
            name="Progress",
            value=f"`{progress_bar}` (`{progress_percent:.2f}%`)",
            inline=False
        )

        embed.set_footer(text=f"Total XP needed for Lvl {level + 1:,}: {xp_next:,}")
        await interaction.response.send_message(embed=embed)
async def setup(bot):
    await bot.add_cog(LevelingCog(bot))