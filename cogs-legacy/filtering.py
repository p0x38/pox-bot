from discord.ext import commands
from discord import Interaction, app_commands

from bot import PoxBot

class FilterCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="config_server", description="Config set for server.")

    async def toggle_key_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=key, value=key) for key in self.bot.available_togglers if current in key]

    @group.command(name="enable", description="Enables a toggle.")
    @app_commands.guild_only()
    @app_commands.autocomplete(key=toggle_key_autocomplete)
    async def enabler(self, interaction: Interaction, key: str):
        if interaction.guild is None: return await interaction.response.send_message("This command should be runned as Guild-Install.")
        if not key in self.bot.available_togglers: return await interaction.response.send_message("You're tried to toggle the key which is not allowed.")

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)

        obj = self.bot.servers_data

        server_data = obj.get(guild_id, {})

        keydata = server_data.get(key)

        if keydata is not None and keydata == True:
            return await interaction.followup.send("Hmm, this server has already turned on.")
        
        server_data[key] = True

        self.bot.servers_data[guild_id] = server_data

        return await interaction.followup.send("Operation completed.")

    @group.command(name="disable", description="Disables a toggle.")
    @app_commands.guild_only()
    @app_commands.autocomplete(key=toggle_key_autocomplete)
    async def disabler(self, interaction: Interaction, key: str):
        if interaction.guild is None: return await interaction.response.send_message("This command should be runned as Guild-Install.")
        if not key in self.bot.available_togglers: return await interaction.response.send_message("You're tried to toggle the key which is not allowed.")

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)

        obj = self.bot.servers_data

        server_data = obj.get(guild_id, {})

        keydata = server_data.get(key)

        if keydata is not None and keydata == False:
            return await interaction.followup.send("Hmm, this server has already turned off.")
        
        server_data[key] = False

        self.bot.servers_data[guild_id] = server_data

        return await interaction.followup.send("Operation completed.")

async def setup(bot):
    await bot.add_cog(FilterCog(bot))