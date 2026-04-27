from discord import Embed, Interaction, Member, Status, TextChannel, app_commands
from discord.ext import commands

from typing import Optional

from bot import PoxBot
from logger import logger

class CheckerCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    checker_group = app_commands.Group(name="check",description="group for checker cog")
    
    @checker_group.command(name="channel", description="Checks channel information.")
    @app_commands.guild_only()
    async def check_channel_info(self, interaction: Interaction, channel: TextChannel):
        await interaction.response.defer(thinking=True)
        try:
            if interaction.guild:
                temp1 = {
                    'Channel ID': channel.id,
                    'Name': channel.name,
                    'Topic': channel.topic,
                    'Category': channel.category,
                    'Created on': channel.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'Last message': f"{channel.last_message.content} by {channel.last_message.author.display_name}" if channel.last_message else "None",
                    'Position': channel.position,
                }
                
                e = Embed(title=f"Information for #{channel.name}")

                lines = []

                for key,value in temp1.items():
                    lines.append(f"{key}: `{value}`")
                    
                e.description = "\n".join(lines)

                await interaction.followup.send(embed=e)
            else:
                await interaction.followup.send("Channel not found.")
        except Exception as e:
            await interaction.followup.send(f"Error. {e}")
            logger.error(f"Error: {e}")

    @checker_group.command(name="online",description="Returns online members. This will not shows invisible members.")
    @app_commands.guild_only()
    async def get_online(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Online list",description="")
        
        if interaction.guild:
            memb = []
            embed.description = '\n'.join([
                f"<@{m.id}>"
                for m in interaction.guild.members
                if m.status not in (Status.offline, Status.invisible) and not m.bot
            ])
        else:
            embed.description = "Not guild"
            await interaction.followup.send(embed=embed)
            return
        
        await interaction.followup.send(embed=embed)
        
    @checker_group.command(name="bot_list",description="Returns bot list.")
    @app_commands.guild_only()
    async def get_bot_list(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Bot list",description="")
        
        if interaction.guild:
            memb = []
            embed.description = '\n'.join([
                m.name
                for m in interaction.guild.members
                if m.bot
            ])
        else:
            embed.description = "Not guild"
            await interaction.followup.send(embed=embed)
            return
        
        await interaction.followup.send(embed=embed)
    
    @checker_group.command(name="bot_count", description="Returns total bot count.")
    @app_commands.guild_only()
    async def get_bot_count(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Bot count in this server",description="")
        
        if interaction.guild:
            embed.description = f"{len([
                m
                for m in interaction.guild.members
                if m.bot
            ])} is in this server."
        else:
            embed.description = "You're not in guild."
            await interaction.followup.send(embed=embed)
            return
        
        await interaction.followup.send(embed=embed)
        
    @checker_group.command(name="usercount", description="Returns member count.")
    @app_commands.guild_only()
    async def get_user_count(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Member count in this server",description="")
        
        if interaction.guild:
            embed.description = f"{len([
                m
                for m in interaction.guild.members
                if not m.bot
            ])} is in this server."
        else:
            embed.description = "You're not in guild."
            await interaction.followup.send(embed=embed)
            return
        
        await interaction.followup.send(embed=embed)
    
    @checker_group.command(name="count", description="Returns total members")
    @app_commands.guild_only()
    async def get_total_members(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Total members",description="")
        
        if interaction.guild:
            embed.description = f"{len(interaction.guild.members)} is in this server."
        else:
            embed.description = "You're not in guild."
            await interaction.followup.send(embed=embed)
            return
        
        await interaction.followup.send(embed=embed)
    
    @checker_group.command(name="even_or_odd", description="Check if User is even or odd (User ID)")
    @app_commands.guild_only()
    async def get_even_or_odd(self, interaction: Interaction, member: Optional[Member] = None):
        if interaction.guild is None: return await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)

        await interaction.response.defer()
        if member is None:
            member = interaction.guild.get_member(interaction.user.id)
        
        if not member:
            return await interaction.followup.send("Member not found.")

        if member.id % 2 == 0:
            return await interaction.followup.send(f"{member.display_name}'s is even.")
        else:
            return await interaction.followup.send(f"{member.display_name}'s is odd.")
async def setup(bot):
    await bot.add_cog(CheckerCog(bot))