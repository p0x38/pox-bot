from aiocache import cached
from discord.ext import commands
from discord import Embed, Interaction, Status, app_commands

from bot import PoxBot

class CountsCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="count", description="An group for Counters.")

    @cached(60)
    @group.command(name="users", description="Get count of users.")
    @app_commands.guild_only()
    async def count_members(self, interaction: Interaction):
        if interaction.guild is None: return await interaction.response.send_message("The commands are usable when the bot is in guild.")

        lines = []

        members = len(interaction.guild.members)
        users = len([
            user
            for user in interaction.guild.members
            if user.bot is not True
        ])
        bots = len([
            bot
            for bot in interaction.guild.members
            if bot.bot
        ])

        lines.append("Total: {}".format(members))
        lines.append("Members: {}".format(users))
        lines.append("Bots: {}".format(bots))
        lines.append("Bot ratio: {} %".format(round((bots / members) * 100)))

        embed = Embed(title="Server counter: users & extras", description="\n".join(lines))

        await interaction.response.send_message(embed=embed)

    @cached(60)
    @group.command(name="online_users", description="Get count of online users.")
    @app_commands.guild_only()
    async def count_online_members(self, interaction: Interaction):
        if interaction.guild is None: return await interaction.response.send_message("The commands are usable when the bot is in guild.")

        lines = []

        members = [member for member in interaction.guild.members if member.bot is not True]

        online = []

        for member in members:
            member2 = interaction.guild.get_member(member.id)

            if member2 is not None:
                if member2.status != Status.invisible or member2.status != Status.offline:
                    online.append(member2)
            del member2
        
        for on in online:
            lines.append(f"<@{on.id}>")

        embed = Embed(title="Server counter: online user", description="\n".join(lines))

        await interaction.response.send_message(embed=embed)

    @cached(60)
    @group.command(name="roles", description="Get count of roles.")
    @app_commands.guild_only()
    async def count_roles(self, interaction: Interaction):
        if interaction.guild is None: return await interaction.response.send_message("The commands are usable when the bot is in guild.")

        lines = []

        roles = len(interaction.guild.roles)
        managed_roles = len([
            managed
            for managed in interaction.guild.roles
            if managed.managed or managed.is_bot_managed()
        ])

        lines.append("Roles: {}".format(roles))
        lines.append("Bot roles: {}".format(managed_roles))
        lines.append("Bot role ratio: {}".format((managed_roles / roles) * 100))

        embed = Embed(title="Server counter: roles & extras", description="\n".join(lines))
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(CountsCog(bot))