from discord.ext import commands
from discord import Color, app_commands, Interaction, Embed

from typing import Optional

import random
from bot import PoxBot
import data

from logger import logger
from src.translator import translator_instance as i18n

class UtilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    @app_commands.command(name=app_commands.locale_str("8ball", extras={"key": "command.8ball.name"}), description=app_commands.locale_str("Gives a random, classic magic 8-ball response to a user's question.", extras={"key": "command.8ball.description"}))
    @app_commands.describe(question="Question to answer by 8ball.")
    async def eight_ball(self, interaction: Interaction, question: str):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        choice = random.choice(data.possibility_words_keys)
        embed = Embed(color=Color.random())
        
        embed.title = i18n.T("command.8ball.embeds.default.title", loc, {"question": question})
        embed.add_field(name=i18n.T("label.answer", loc), value=i18n.T(choice, loc), inline=True)
        
        return await interaction.followup.send(embed=embed)

    @app_commands.command(name="yes_or_no", description="Gives yes or no to your ask")
    @app_commands.describe(question="Question")
    async def yes_or_no(self, interaction: Interaction, question: str):
        choice = random.choice(["Yeah","Nope"])

        e = Embed(
            title=f"Question: `{question}`",
            description=f"Result: {choice}",
        )

        await interaction.response.send_message(embed=e)
    
    @app_commands.command(name="coinflip", description="Flips a coin and says 'Heads' or 'Tails'.")
    @app_commands.describe(input="Text to desire.")
    async def coin_flip(self, interaction: Interaction, input: Optional[str] = None):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        result = i18n.T("text.coinflip.true" if random.randint(0, 1) == 1 else "text.coinflip.false")

        e = Embed(color=Color.random())

        if input:
            e.title = f"`{input}`"
        
        e.description = f"Result: {result}"

        await interaction.response.send_message(embed=e)

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))