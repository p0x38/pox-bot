import time
from discord.ext import commands
from discord import app_commands, Interaction, Embed

from bot import PoxBot
from thefuzz import process

from stuff import truncate

class SearchIndexMaker(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="builtin_search", description="Just for no reason")

    @group.command(name="add_query", description="Add query to database.")
    async def add_query(self, interaction: Interaction, value: str):
        await interaction.response.defer()

        if self.bot.db_connection:
            try:
                await self.bot.db_connection.execute("INSERT INTO custom (query,author_id,timestamp) VALUES (?,?,?)", (value, interaction.user.id, time.time()))
                await interaction.followup.send(f"Your query has been added.", ephemeral=True, silent=True)
            except Exception as e:
                await interaction.followup.send(f"Failed to process. {e}", ephemeral=True)
                return
        else:
            await interaction.followup.send("The bot has not connected with Database.")
            return
         
    @group.command(name="remove_query", description="Remove query from database.")
    async def remove_query(self, interaction: Interaction, value: str):
        await interaction.response.defer()

        if self.bot.db_connection:
            try:
                await self.bot.db_connection.execute(f"DELETE FROM custom WHERE query = \"{value}\"")
                await interaction.followup.send(f"The query has been removed.", ephemeral=True, silent=True)
            except Exception as e:
                await interaction.followup.send(f"Failed to process. {e}", ephemeral=True)
                return
        else:
            await interaction.followup.send("The bot has not connected with Database.")
            return
    
    @group.command(name="count", description="Get query count.")
    async def query_count(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)

        if self.bot.db_connection:
            try:
                async with self.bot.db_connection.execute("SELECT query FROM custom") as cursor:
                    all_query = await cursor.fetchall()
                count = 0

                for query in all_query:
                    count += 1

                embed = Embed(
                    title=f"Count of query in Database",
                    description=f"{count} query in database."
                )

                await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"Failed to process. {e}")
                return
        else:
            await interaction.followup.send("The bot has not connected with Database.")
            return

    @group.command(name="list", description="Get list of query.")
    async def query_list(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)

        if self.bot.db_connection:
            try:
                async with self.bot.db_connection.execute("SELECT query FROM custom") as cursor:
                    all_query = await cursor.fetchall()
                lines = []

                for query in all_query:
                    lines.append(query[0])
                embed = Embed(
                    title=f"Count of query in Database",
                    description=truncate(", ".join(lines)),
                )

                await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"Failed to process. {e}")
                return
        else:
            await interaction.followup.send("The bot has not connected with Database.")
            return

    @group.command(name="search_query", description="Search query as fuzzy search")
    async def search_query(self, interaction: Interaction, needle: str):
        await interaction.response.defer(thinking=True)

        if self.bot.db_connection:
            try:
                async with self.bot.db_connection.execute("SELECT query FROM custom") as cursor:
                    all_query = await cursor.fetchall()
                
                desc = []

                data = process.extract(needle, all_query, limit=24)

                for item in data:
                    desc.append(f"{item[0][0]}: {item[1]}")
                
                embed = Embed(
                    title=f"Fuzzy Match: {needle}",
                    description="\n".join(desc)
                )

                await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"Failed to process. {e}")
                return
        else:
            await interaction.followup.send("The bot has not connected with Database.")
            return
async def setup(bot):
    await bot.add_cog(SearchIndexMaker(bot))