from aiocache import cached
from discord import Embed, Interaction, app_commands
from discord.ext import commands

from mcstatus import JavaServer
import mojang

from roblox import UserNotFound
import roblox
import roblox.users
from roblox.utilities.exceptions import Forbidden, BadRequest, TooManyRequests, InternalServerError, NotFound

from bot import PoxBot

class MinecraftCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot: PoxBot = bot
    
    minecraft_group = app_commands.Group(name="minecraft", description="Sub-group")
    
    @cached(60)
    @minecraft_group.command(name="server_lookup", description="Lookups minecraft server.")
    async def minecraft_server_lookup(self, interaction: Interaction, address: str):
        await interaction.response.defer()
        embed = Embed(title=f"Lookup for \"{address}\"")
        
        try:
            row_to_add = {}
            server = await JavaServer.async_lookup(address)
            
            status = await server.async_status()
            embed.description = status.motd.to_plain()
            row_to_add = {
                "Version": status.version.name,
                "Protocol Version": status.version.protocol,
                "Latency": f"{status.latency:2f} ms",
                "Players": f"{status.players.online}/{status.players.max}"
            }
            
            try:
                query = server.query()
                
                if query.motd:
                    embed.description = query.motd.to_plain()
                
                if query.players and query.players.list:
                    row_to_add["Player list"] = ', '.join(query.players.list)
            except Exception:
                if status.players.sample:
                    names = [p.name for p in status.players.sample]
                    row_to_add["Player list"] = ', '.join(names)
                else:
                    row_to_add["Player list"] = "Not available"
            
            for key, value in row_to_add.items():
                embed.add_field(name=key, value=value)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            return await interaction.followup.send(f"Failed to lookup minecraft server for \"{address}\": {e}")

    @cached(300)
    @minecraft_group.command(name="username_to_uuid", description="Converts Username to UUID.")
    async def username_to_uuid(self, interaction: Interaction, username: str):
        cached = self.bot.cache.get(f"mcid_{username}")
        if cached:
            await interaction.response.send_message(cached)
        else:
            cached = mojang.get_uuid(username)
            
            if cached:
                self.bot.cache.set(f"mcid_{username}",cached)
                await interaction.response.send_message(cached)
            else:
                await interaction.response.send_message("Couldn't resolve the username.")
    
    @cached(300)
    @minecraft_group.command(name="uuid_to_username", description="Converts UUID to Username.")
    async def uuid_to_username(self, interaction: Interaction, uuid: str):
        cached = self.bot.cache.get(f"mcuuid_{uuid}")
        if cached:
            await interaction.response.send_message(cached)
        else:
            cached = mojang.get_username(uuid)
            
            if cached:
                self.bot.cache.set(f"mcuuid_{uuid}",cached)
                await interaction.response.send_message(cached)
            else:
                await interaction.response.send_message("Couldn't resolve the UUID.")

async def setup(bot):
    await bot.add_cog(MinecraftCog(bot))