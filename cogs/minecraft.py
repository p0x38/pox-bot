from datetime import datetime
from io import BytesIO
import uuid

from aiocache import cached
from discord import Embed, File, Interaction, app_commands
from discord.ext import commands

from mcstatus import JavaServer
import mojang
from minepi import Player

from src.translator import translator_instance as i18n
from bot import PoxBot

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False
    return False

class MinecraftCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot: PoxBot = bot
    
    minecraft_group = app_commands.Group(name="minecraft", description="Sub-group")
    
    @cached(60)
    @minecraft_group.command(name="server", description=app_commands.locale_str("command.minecraft.server.description"))
    async def minecraft_server_lookup(self, interaction: Interaction, address: str):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        embed = Embed(title=f"Information for \"{address}\"")
        
        try:
            row_to_add = {}
            server = await JavaServer.async_lookup(address)
            
            status = await server.async_status()
            embed.description = status.motd.to_plain()
            row_to_add = {
                "minecraft_server_version": status.version.name,
                "minecraft_server_protocol": status.version.protocol,
                "minecraft_server_latency": f"{status.latency:2f} ms",
                "minecraft_server_players": f"{status.players.online}/{status.players.max}"
            }
            
            try:
                query = server.query()
                
                if query.motd:
                    embed.description = query.motd.to_plain()
                
                if query.players and query.players.list:
                    row_to_add["minecraft_server_playerlist"] = ', '.join(query.players.list)
            except Exception:
                if status.players.sample:
                    names = [p.name for p in status.players.sample]
                    row_to_add["minecraft_server_playerlist"] = ', '.join(names)
                else:
                    row_to_add["minecraft_server_playerlist"] = i18n.T("text.unknown", loc)
            
            row_to_add = i18n.translate_map(row_to_add, loc)
            
            for key, value in row_to_add.items():
                embed.add_field(name=key, value=value)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed.title = i18n.T("error.embeds.minecraft_lookup_failed.title", loc)
            embed.description = i18n.T("error.embeds.minecraft_lookup_failed.description", loc, {"address": address, "e": e})
            return await interaction.followup.send(embed=embed)
    
    @cached(300)
    @minecraft_group.command(name="profile", description=app_commands.locale_str("command.minecraft.profile.description"))
    async def user(self, interaction: Interaction, query: str):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        
        embed = Embed(timestamp=datetime.now())
        
        await interaction.response.defer()
        is_uuid = is_valid_uuid(query)
        try:
            if is_uuid:
                player = Player(uuid=query)
            else:
                player = Player(name=query)
                
            await player.initialize()
                
            files = []
                
            head = await player.skin.render_head(ratio=20, vr=0, hr=0) if player.skin else None
            body = await player.skin.render_skin() if player.skin else None
                
            if head:
                with BytesIO() as head_binary:
                    head.save(head_binary, 'PNG')
                    head_binary.seek(0)
                    files.append(File(fp=head_binary, filename="head.png"))
                
            if body:
                with BytesIO() as body_binary:
                    body.save(body_binary, 'PNG')
                    body_binary.seek(0)
                    files.append(File(fp=body_binary, filename="body.png"))
                
            embed.title = i18n.T("command.minecraft.profile.embeds.default.title", loc, {"name": player.name})
            if head: embed.set_thumbnail(url="attachment://head.png")
            if body: embed.set_image(url="attachment://body.png")
                
            embed.add_field(name="UUID", value=f"`{player.uuid}`", inline=False)
                
            await interaction.followup.send(embed=embed, files=files)
        except Exception as e:
            embed.description = i18n.T("error.embeds.minecraft_user_not_found.description", loc, {"query": query})
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MinecraftCog(bot))