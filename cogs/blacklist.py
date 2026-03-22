from discord.ext import commands
from discord import Embed, Interaction, app_commands

from bot import PoxBot

class Blacklister(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="blacklist", description="Blacklister.")

    @group.command(name="add", description="Adds blacklisted word to server.")
    @app_commands.checks.has_permissions(manage_messages=True,manage_guild=True)
    @app_commands.guild_only()
    async def add_blacklisted_word(self, interaction: Interaction, word: str):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in Guild-install.")
            return
        await interaction.response.defer()
        guild_id = str(interaction.guild.id)
        word = word.lower()

        blacklisted = self.bot.blacklisted_words

        serverwords = blacklisted.get(guild_id, [])

        if word in serverwords:
            await interaction.followup.send(f"The word {word} is already blacklisted.")
            return
        
        serverwords.append(word)
        blacklisted[guild_id] = serverwords

        await interaction.followup.send(f"Added {word} to the server's blacklisted words.\nIf you want this feature works, make sure the bot to higher than members.")
    

    @group.command(name="remove", description="Removes blacklisted word from server.")
    @app_commands.checks.has_permissions(manage_messages=True,manage_guild=True)
    @app_commands.guild_only()
    async def remove_blacklisted_word(self, interaction: Interaction, word: str):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in Guild-install.")
            return
        await interaction.response.defer()
        guild_id = str(interaction.guild.id)
        word = word.lower()

        blacklisted = self.bot.blacklisted_words

        serverwords = blacklisted.get(guild_id, [])

        if not word in serverwords:
            await interaction.followup.send(f"The word {word} is not blacklisted.")
            return
        
        serverwords.remove(word)

        blacklisted[guild_id] = serverwords

        await interaction.followup.send(f"Removed {word} from the server's blacklisted words.\nIf you want this feature works, make sure the bot to higher than members.")
    
    @group.command(name="list", description="Lists banned words.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True, manage_guild=True)
    async def list_blacklisted_words(self, interaction: Interaction):
        if not interaction.guild: raise Exception("No guild found from interaction data")
        
        embed = Embed(title="Banned words")
        lines = ["Banned words in this server listed below:"]
        banned_words = self.bot.blacklisted_words.get(str(interaction.guild.id), [])

        if len(banned_words) > 0:
            for word in banned_words:
                lines.append(word)
        else:
            lines.append("No banned words were found from Database.")
        
        embed.description = "\n".join(lines)
        embed.set_footer(text="If you want this feature works, make sure the bot to higher than members.")

        await interaction.response.send_message(embed=embed)
async def setup(bot):
    await bot.add_cog(Blacklister(bot))