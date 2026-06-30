import psutil
from discord import Interaction, app_commands
from discord.abc import Messageable
from discord.ext import commands

from src.core.bot import PoxBot


class UtilityCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

    @app_commands.command(name="listapps", description=app_commands.locale_str("command.utility.listapps.description"))
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.guild.id)
    async def list_all_opened_applications(self, interaction: Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Nope")

        await interaction.response.defer()

        paginator = commands.Paginator()

        paginator.add_line(f"{'PID':<8} | {'Application Name':<30}")
        paginator.add_line("-" * 45)

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                p_info = proc.info
                paginator.add_line(f"{p_info['pid']:<8} | {p_info['name']:<30}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        for page in paginator.pages[:4]:
            if (
                isinstance(interaction.channel, Messageable)
                and interaction.channel.permissions_for(interaction.guild.me).send_messages
            ):
                await interaction.channel.send(page)


async def setup(bot: PoxBot):
    await bot.add_cog(UtilityCog(bot))
