import numpy as np
import psutil
from discord import Color, Embed, Interaction, app_commands
from discord.abc import Messageable
from discord.ext import commands

from ....application import PoxBot


class UtilityCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.rng = np.random.default_rng()

    @app_commands.command(
        name='listapps',
        description=app_commands.locale_str('command.utility.listapps.description'),
    )
    @app_commands.checks.cooldown(
        1, 10.0, key=lambda i: i.guild.id if i.guild else i.user.id,
    )
    async def list_all_opened_applications(self, interaction: Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                'This command must be used in a server.',
            )

        await interaction.response.defer()

        paginator = commands.Paginator()
        paginator.add_line(f'{"PID":<8} | {"Application Name":<30}')
        paginator.add_line('-' * 45)

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                p_info = proc.info
                paginator.add_line(f'{p_info["pid"]:<8} | {p_info["name"]:<30}')
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        for page in paginator.pages[:4]:
            if (
                isinstance(interaction.channel, Messageable)
                and interaction.channel.permissions_for(
                    interaction.guild.me,
                ).send_messages
            ):
                await interaction.channel.send(page)
        return None

    @app_commands.command(
        name='8ball', description=app_commands.locale_str('command.8ball.description'),
    )
    @app_commands.describe(question='Question to answer by 8ball.')
    async def eight_ball(self, interaction: Interaction, question: str):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if (
                hasattr(self.bot, 'database')
                and self.bot.database
                and self.bot.database.settings
            )
            else interaction.locale
        )
        await interaction.response.defer()

        choices = np.array(
            [
                'It is certain.',
                'Without a doubt.',
                'You may rely on it.',
                'Ask again later.',
                'Better not tell you now.',
                'Cannot predict now.',
                "Don't count on it.",
                'My sources say no.',
            ],
            dtype=object,
        )
        answer = self.rng.choice(choices)

        embed = Embed(color=Color.random())
        embed.title = self.bot.internal_translator.T(
            'command.8ball.embeds.default.title', loc, {'question': question},
        )
        embed.add_field(
            name=self.bot.internal_translator.T('label.answer', loc),
            value=answer,
            inline=True,
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name='yes_or_no', description='Gives yes or no to your ask')
    @app_commands.describe(question='Question')
    async def yes_or_no(self, interaction: Interaction, question: str):
        result = self.rng.choice(np.array(['Yeah', 'Nope'], dtype=object))

        embed = Embed(
            title=f'Question: `{question}`',
            description=f'Result: {result}',
            color=Color.random(),
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name='coinflip', description="Flips a coin and says 'Heads' or 'Tails'.",
    )
    @app_commands.describe(input='Optional label for the flip')
    async def coin_flip(self, interaction: Interaction, input: str | None = None):
        await interaction.response.defer()
        result = self.rng.choice(np.array(['Heads', 'Tails'], dtype=object))
        text = self.bot.internal_translator.T(
            'text.coinflip.true' if result == 'Heads' else 'text.coinflip.false',
        )

        embed = Embed(color=Color.random())
        if input:
            embed.title = f'`{input}`'
        embed.description = f'Result: {text}'

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name='roll', description='Roll one or more dice and show the result.',
    )
    @app_commands.describe(
        sides='Number of sides on each die', rolls='How many dice to roll',
    )
    async def roll(self, interaction: Interaction, sides: int = 6, rolls: int = 1):
        if sides < 2 or rolls < 1:
            return await interaction.response.send_message(
                'Sides must be at least 2 and rolls must be at least 1.',
            )

        if rolls > 1000:
            rolls = 1000

        await interaction.response.defer()

        results = self.rng.integers(1, sides + 1, size=rolls)
        mean = float(np.mean(results))
        distribution = np.bincount(results, minlength=sides + 1)[1:]

        description = [f'Rolled {rolls}d{sides}: mean {mean:.2f}']
        if rolls == 1:
            description.append(f'Result: {int(results[0])}')
        else:
            distribution_lines = [
                f'{value}: {count}'
                for value, count in enumerate(distribution, start=1)
                if count
            ]
            description.extend(distribution_lines[:10])

        await interaction.followup.send(
            embed=Embed(
                title='Dice Roll',
                description='\n'.join(description),
                color=Color.random(),
            ),
        )
        return None


async def setup(bot: PoxBot):
    await bot.add_cog(UtilityCog(bot))
