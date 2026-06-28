import random

from aiocache import cached
from discord import Embed, Interaction, Member, User, app_commands
from discord.ext import commands

from src.bot import PoxBot
from stuff import check_map


class DetectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    detector_group = app_commands.Group(
        name="detect",
        description=app_commands.locale_str("command.detect.description"),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True))

    @cached(300)
    @detector_group.command(
        name="how_gay",
        description=app_commands.locale_str("command.detect.how_gay.description"))
    @app_commands.describe(member="Member to check")
    async def gay_detector(self, interaction: Interaction, member: Member | User):
        await interaction.response.defer(thinking=True)
        # randum = int(random.random()*100)
        # dac = check_map(randum,100)
        dac = check_map()

        e = Embed(title=f"Is {member.name} gay?", description=f"{dac}")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(
        name="how_slop",
        description=app_commands.locale_str("command.detect.how_slop.description"))
    @app_commands.describe(member="Member to check")
    async def retroslop_detector(self, interaction: Interaction, member: Member | User):
        await interaction.response.defer(thinking=True)
        # randum = int(random.random()*100)
        # dac = check_map(randum,100)
        dac = check_map()

        e = Embed(title=f"Is {member.name} slop?", description=f"{dac}")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(
        name="how_femboy",
        description=app_commands.locale_str("command.detect.how_femboy.description"))
    @app_commands.describe(member="Member to check")
    async def femboy_detector(self, interaction: Interaction, member: Member | User):
        await interaction.response.defer(thinking=True)
        # randum = int(random.random()*100)
        # dac = check_map(randum,100)
        dac = check_map()

        e = Embed(title=f"Is {member.name} femboy?", description=f"{dac}")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(
        name="how_freaky",
        description=app_commands.locale_str("command.detect.how_freaky.description"))
    @app_commands.describe(member="Member to check")
    async def freaky_detector(self, interaction: Interaction, member: Member | User):
        await interaction.response.defer(thinking=True)
        # randum = int(random.random()*100)
        # dac = check_map(randum,100)
        dac = check_map()

        e = Embed(title=f"Is {member.name} freaky?", description=f"{dac}")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(
        name="how_silly",
        description=app_commands.locale_str("command.detect.how_freaky.description"))
    @app_commands.describe(member="Member to check")
    async def silly_detector(self, interaction: Interaction, member: Member | User):
        await interaction.response.defer(thinking=True)

        random.seed(member.id)
        rand = random.random()

        e = Embed(title=f"How silly {member.name} is?", description=f"{round(rand * 1000) / 10}%")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(
        name="vibecheck",
        description=app_commands.locale_str("command.detect.vibecheck.description"))
    @app_commands.describe(member="Member to check")
    async def vibe_check(self, interaction: Interaction, member: Member | User | None = None):
        await interaction.response.defer(thinking=True)
        if member is None:
            if interaction.message is not None:
                member = interaction.message.author
            else:
                await interaction.followup.send("Message isn't available")
                return

        rand = round(random.randrange(0, 100))

        e = Embed(title=f"How much {member.name} is vibing", description=f"He is {rand}% vibing.")
        e.set_footer(text="Don't take the results too seriously.")
        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(
        name="custom_member",
        description=app_commands.locale_str("command.detect.custom_member.description"))
    @app_commands.describe(member="Member to check")
    async def custom_detection(self, interaction: Interaction, member: Member | User, *,
                               custom: str):
        await interaction.response.defer(thinking=True)
        # randum = int(random.random()*100)
        # dac = check_map(randum,100)
        dac = check_map()

        e = Embed(title=f"Is {member.name} {custom}?", description=f"{dac}")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)

    @cached(300)
    @detector_group.command(name="custom2",
                            description=app_commands.locale_str("command.detect.custom2.description"))
    async def custom_detection2(self, interaction: Interaction, custom: str):
        await interaction.response.defer(thinking=True)
        # randum = int(random.random()*100)
        # dac = check_map(randum,100)
        dac = check_map()

        e = Embed(title=f"Is {custom}?", description=f"{dac}")
        e.set_footer(text="Don't take the results too seriously.")

        await interaction.followup.send(embed=e)


async def setup(bot):
    await bot.add_cog(DetectionCog(bot))
