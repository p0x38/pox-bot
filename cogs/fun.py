import re
from typing import Optional, Union

from aiocache import cached
from discord.ext.commands import Cog
from discord import Embed, Member, User, app_commands, Interaction
import random

from bot import PoxBot

from logger import logger
import asyncio

from logger import logger
import stuff

def ship_names(name1, name2):
    n1 = name1.lower()
    n2 = name2.lower()
    
    match1 = re.search(r'[aeiou]', n1)
    split1 = match1.start() + 1 if match1 else len(n1) // 2
    
    indices = [m.start() for m in re.finditer(r'[aeiou]', n2)]
    split2 = indices[-1] if indices else len(n2) // 2
    
    combined = n1[:split1] + n2[split2:]
    
    return combined.capitalize()

class Fun(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="fun", description="Fun stuff.")
    
    @group.command(name="guess_game", description="Starts a new number guessing game (1 ~ 100)")
    async def guess_game(self, interaction: Interaction):
        user_id = interaction.user.id

        if user_id in self.bot.active_games:
            return await interaction.response.send_message("You already have an active game going.")
        
        secret_number = random.randint(1,100)
        self.bot.active_games[user_id] = {
            'number': secret_number,
            'attempts': 0,
            'recent': 0,
            'score': 100,
        }

        logger.debug(self.bot.active_games)

        return await interaction.response.send_message(
            f"Guessing game started."
            f"Use /guess <number> to guess."
        )
    
    @group.command(name='guess', description="Guess the number.")
    async def make_guess(self, interaction: Interaction, number: int):
        user_id = interaction.user.id

        if user_id not in self.bot.active_games:
            return await interaction.response.send_message("You haven't started a game yet.")
        
        game_data = self.bot.active_games[user_id]
        
        secret_number = game_data['number']
        game_data['attempts'] += 1
        attempts = game_data['attempts']

        if number < 1 or number > 100:
            return await interaction.response.send_message("Not that so far.")
        
        game_data['recent'] = number

        recent_guess = game_data['recent']

        if attempts < 16:
            if number < secret_number:
                game_data['score'] /= 1.5
                return await interaction.response.send_message("Too low.")
            elif number > secret_number:
                game_data['score'] /= 1.5
                return await interaction.response.send_message("Too high.")
            else:
                del self.bot.active_games[user_id]
                return await interaction.response.send_message(
                    f"Congrats {interaction.user.name}. You've guessed my number {secret_number} in just {attempts} attempts.\nYou can play the guessing game by typing `/guess_game`."
                )
        else:
            special = ""
            distance_from_number = abs(secret_number - number)
            if distance_from_number < 2:
                special = "You were very very close to the number..."
            elif distance_from_number < 2 and distance_from_number > 8:
                special = "You were so close to the number..."
            elif distance_from_number < 8 and distance_from_number > 16:
                special = "You were a bit close to the number..."
            elif distance_from_number > 16:
                special = "You were not even close to the number."
            
            return await interaction.response.send_message(f"You failed to guess. {special}\n It was {secret_number}. Your score is {game_data['score']}. Try again.")
    
    @group.command(name="stopguess", description="Stops the current guessing game.")
    async def stop_guessing(self, interaction: Interaction):
        user_id = interaction.user.id

        if user_id in self.bot.active_games:
            secret = self.bot.active_games[user_id]['number']
            del self.bot.active_games[user_id]
            return await interaction.response.send_message(f"Aw... It was {secret}.")
        else:
            return await interaction.response.send_message(f"You've not even started the guess.")

    @cached(300)
    @group.command(name="job_application",description="yeah")
    async def a_job_message(self, ctx):
        try:
            await ctx.response.send_message("Today, I'll be talking about one of humanity's biggest fears.")
            await asyncio.sleep(2)
            return await ctx.followup.send("# A J*B.")
        except Exception as e:
            logger.error(e)
    
    @group.command(name="boop_member",description="boops someone")
    @app_commands.describe(user="Member to boop")
    async def boop_member(self, ctx: Interaction, user: Member):
        return await ctx.response.send_message(f"<@{user.id}> boop.")
    
    @group.command(name="dice", description="Rolls dice.")
    async def roll_dice(self, interaction: Interaction, dices: int, sides: int):
        await interaction.response.defer()

        dices = stuff.clamp(dices, 1, 128)
        sides = stuff.clamp(sides, 1, 128)

        dice_results = [random.randint(1,sides) for dice in range(dices)]
        dice_sum = sum(dice_results)
        dice_avg = dice_sum / len(dice_results)
        dice_str = [str(result) for result in dice_results]
        lalapapa = ", ".join(dice_str) + f"\nSum: {dice_sum}\nAverage: {dice_avg}"
        embed = Embed(title="Dice roll", description=lalapapa)

        return await interaction.followup.send(embed=embed)
    
    @group.command(name="ship", description="Calculates the love rate between two users")
    async def ship_users(self, interaction: Interaction, user1: Member, user2: Optional[Member] = None):
        if not user2:
            if interaction.guild:
                try:
                    user2 = interaction.guild.get_member(interaction.user.id)
                    if not user2: raise Exception()
                except:
                    return await interaction.response.send_message("Error occured.")
            else: return await interaction.response.send_message("The command should've to ran with guild")
        
        rand_seed = user1.id + user2.id
        random.seed(rand_seed)
        rand = random.random()
        
        await interaction.response.defer()
        
        e = Embed(title="Ship stuff with them yuh")
        rows_to_add = [
            f"Ship name: {ship_names(user1.display_name, user2.display_name)}"
            f"Ship format: {user1.mention} x {user2.mention}",
            f"\"LOVE\" Possibility: {round(rand*100)} %"
        ]
        
        e.description = "\n".join(rows_to_add)
        e.set_footer(text="W.I.P.")
        
        await interaction.followup.send(embed=e)
    
async def setup(bot):
    await bot.add_cog(Fun(bot))