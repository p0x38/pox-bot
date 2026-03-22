import json
import os
from typing import Optional
import aiofiles
from discord import Embed, Interaction, Member, app_commands
from discord.ext import commands
from logger import logger

from bot import PoxBot
import stuff

class RatingCog(commands.Cog):
    group = app_commands.Group(name="rating", description="Group for Rating members.")

    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.data: dict[int, dict[int, float]] = {}
        self.file_path = os.path.join(self.bot.root_path, "data/rating.json")
        self.loaded = False
    
    async def save(self):
        data_to_save = {str(k): v for k, v in self.data.items()}

        try:
            async with aiofiles.open(self.file_path, mode='w+', encoding='utf-8') as f:
                await f.write(json.dumps(data_to_save, indent=4))
            logger.info(f"Saved data into {self.file_path}")
        except Exception as e:
            logger.exception(f"Error saving welcome.json asynchronously: {e}")
    
    async def load(self):
        if not os.path.exists(self.file_path):
            logger.warning(f"{self.file_path} found. Starting with empty...")
            return {}
        
        try:
            async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            
            raw_data = json.loads(content)
            self.data = {int(k): v for k, v in raw_data.items()}
            self.loaded = True
            logger.info(f"Loaded data from {self.file_path}")
        except json.JSONDecodeError:
            logger.error("Error decoding JSON. Starting with empty data.")
            self.data = {}
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Loading database...")
        await self.load()
    
    async def cog_unload(self) -> None:
        logger.info("Saving data")
        await self.save()
    
    @group.command(name="rate_user", description="Rate member.")
    @app_commands.guild_only()
    @app_commands.describe(rate="A floating point number to rate member between 0 to 100.")
    async def rate_member(self, interaction: Interaction, member: Member, rate: float, override: Optional[bool] = False):
        if interaction.guild is None: return await interaction.response.send_message("You cannot set welcome channel unless the bot is for guild.")
        if member == interaction.user: return await interaction.response.send_message("You can't rate yourself.")
        if override is None: override = False

        rate = stuff.clamp_f(rate, 0, 100)

        user_data = self.data.setdefault(member.id, {})

        if interaction.user.id in user_data.keys():
            if not override:
                return await interaction.response.send_message(f"You already rated to `{member.display_name}`!")
            else:
                user_data[interaction.user.id] = rate
                return await interaction.response.send_message(f"You have been overwritten the rating for `{member.display_name}` to {rate}!")

        user_data[interaction.user.id] = rate

        return await interaction.response.send_message(f"You gave `{member.display_name}` rate of {rate}.")
    
    @group.command(name="user_rating", description="Gets member's rating info.")
    @app_commands.guild_only()
    async def get_rating_info(self, interaction: Interaction, member: Member):
        if interaction.guild is None: return await interaction.response.send_message("You cannot set welcome channel unless the bot is for guild.")
        embed = Embed(title=f"{member.display_name}'s ratings")
        user_data = self.data.get(member.id)

        if not user_data:
            embed.description = "This user doesn't have any of rating from any of user!"
            return await interaction.response.send_message(embed=embed)
        
        sum = 0

        sorted_dict = dict(sorted(user_data.items(), key=lambda item: item[1], reverse=True))

        for rating in sorted_dict.values(): sum += rating

        average = (sum / len(sorted_dict))

        embed.add_field(name="Average Rating",value=average)

        return await interaction.response.send_message(embed=embed)
async def setup(bot):
    await bot.add_cog(RatingCog(bot))