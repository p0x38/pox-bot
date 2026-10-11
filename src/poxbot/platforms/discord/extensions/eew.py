from discord import Interaction, app_commands
from discord.ext import commands

from ....application.bot import PoxBot
from ....features.earthquake.embed_builder import P2PQuakeEmbedBuilder
from ....shared.utils.parsers.parser import Parser


class EarthquakeCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot

    group = app_commands.Group(
        name='eew',
        description=app_commands.locale_str('command.eew.description'),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True,
            dm_channel=True,
            private_channel=True,
        ),
    )

    @group.command(
        name='retrieve',
        description=app_commands.locale_str('command.eew.retrieve.description'),
    )
    @app_commands.describe(
        codes=app_commands.locale_str('command.eew.retrieve.parameters.codes')
    )
    async def retrieve_eew_items(
        self, interaction: Interaction, codes: str | None = None
    ) -> None:
        locale = await self.bot.get_locale(interaction)

        code_list = Parser.convert(codes, tuple) if codes else ()

        events = self.bot.quake_manager.get_cached_events(
            limit=16,
            codes=code_list,
        )

        builder = P2PQuakeEmbedBuilder(
            self.bot.internal_translator,
            locale,
        )

        if not events:
            await interaction.response.send_message(
                self.bot.internal_translator.T(
                    'earthquake_reports.jma.embed.rows.empty',
                    locale,
                ),
                ephemeral=True,
            )
            return

        pages = builder.build_rows(events)

        await interaction.response.send_message(embed=pages[0])

        for page in pages[1:]:
            await interaction.followup.send(embed=page)


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(EarthquakeCog(bot))
