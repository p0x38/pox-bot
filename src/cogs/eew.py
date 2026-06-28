# The cog uses P2PQuake API to get EEW information and display it in Discord.
#
# The documentation of API can be found here:
# https://www.p2pquake.net/develop/json_api_v2/
#
# also the cog uses JMA's some data for displaying earthquake & tsunami information.
# The copyright of JMA's data belongs to Japan Meteorological Agency, and
# P2PQuake is not affiliated with JMA.
# I do not claim any rights to JMA's data, or P2PQuake's data.
#
# I do NOT take any responsibility for any damage caused by using the API.
# https://www.p2pquake.net/secondary_use/

import aiohttp
from discord import (
    Embed,
    Interaction,
    app_commands,
)
from discord.ext import commands

from src.bot import PoxBot


class EEWCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    group = app_commands.Group(name="message", description="An group for messages.")

    @group.command(name="get", description="Gets latest info")
    async def get_eew_info(self, interaction: Interaction):
        await interaction.response.defer()

        embed = Embed()

        cached = self.bot.cache.get("eew")

        if not cached:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    "https://api.p2pquake.net/v2/history?codes=551&codes=552"
                ) as resp,
            ):
                if resp.status != 429:
                    embed.description = "Rate limited!"
                    return await interaction.followup.send(embed=embed)
                elif resp.status != 200:
                    embed.description = "Failed to get data!"
                    return await interaction.followup.send(embed=embed)

                data = await resp.json()

                if not isinstance(data, list) or not data:
                    embed.description = "Response retrieved, but data isn't valid!"
                    return await interaction.followup.send(embed=embed)

                cached = data
                self.bot.cache.set("eew", cached)

        if not isinstance(cached, list) or not cached:
            embed.description = "Retrieved data isn't valid!"
            return await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EEWCog(bot))
