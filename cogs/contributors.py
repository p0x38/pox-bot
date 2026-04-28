from pathlib import Path
from typing import Any

from discord.ext.commands import Cog
from discord import Color, app_commands, Embed, Interaction, File
from os.path import dirname, join

from prompt_toolkit import contrib

from src.translator import translator_instance

from bot import PoxBot
import data

class ContributorsCog(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.contributor_list: list[dict[str, Any]] = data.get_contributors_v2()

    group = app_commands.Group(name="contributors", description=app_commands.locale_str("A group for contributors.", extras={"key": "command.contributors.description"}))
    
    @group.command(name="list", description=app_commands.locale_str("Lists all contributors.", extras={"key": "command.contributors.list.description"}))
    async def list_contributors(self, interaction: Interaction):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(title=translator_instance.T("command.contributors.list.embeds.default.title", loc), description=translator_instance.T("command.contributors.list.embds.default.description", loc))
        
        await interaction.response.defer()
        
        hmmm = []

        for contributor in self.contributor_list:
            user_id = contributor.get("id", None)
            if not user_id: continue
            
            user = self.bot.get_user(user_id)
            
            display_name = user.display_name if user else translator_instance.T("text.unknown", loc)
            
            name = contributor.get("name", translator_instance.T("text.unknown", loc))
            contribution = contributor.get("description", translator_instance.T("text.unknown", loc))

            hmmm.append(f"**{name}**: {contribution}")
        
        embed.description = "\n".join(hmmm)
        embed.color = Color.blue()
        
        return await interaction.followup.send(embed=embed)
    
    async def contributor_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=contributor['command'], value=contributor['command'])
            for contributor in self.contributor_list
            if not contributor.get("command")
        ]
    
    @group.command(name="view", description=app_commands.locale_str("Shows contributor.", extras={"key": "command.contributors.view.description"}))
    @app_commands.autocomplete(contributor_id=contributor_autocomplete)
    async def view_contributor(self, interaction: Interaction, contributor_id: str):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(title=translator_instance.T("command.contributors.view.embeds.default.title", loc, {"contributor": contributor_id}))
        
        await interaction.response.defer()
        
        contributor_data = next((d for d in self.contributor_list if d.get("command") == contributor_id), None)
        
        if contributor_data:
            embed.set_footer(text=contributor_data.get("quote"))
            
            rows = [
                contributor_data.get("description", translator_instance.T("text.unknown", loc)), "\n\n",
            ]
            
            if contributor_data.get("content"):
                rows.append(contributor_data['content'])
            
            pic = None
            
            if contributor_data.get("thumbnail_url"):
                thumbnail_url = contributor_data['thumbnail_url']
                
                if thumbnail_url.startswith("file:"):
                    path = Path(__file__).parent / thumbnail_url.replace("file:", "", 1)
                    
                    if path.exists() and path.is_file():
                        pic = File(fp=path.resolve(), filename=path.name)
            
            if pic:
                embed.set_thumbnail(url="attachment://" + pic.filename)
                return await interaction.followup.send(embed=embed, file=pic)
            else:
                return await interaction.followup.send(embed=embed)
        else:
            embed.title = translator_instance.T("error.embed.contributor_not_found.title", loc)
            embed.title = translator_instance.T("error.embed.contributor_not_found.description", loc, {"contributor": contributor_id})
    
    @group.command(name="spy_thesinglerunc", description="Special thanks to codigoerror10014")
    async def spy_thesinglerunc(self, interaction: Interaction):
        embed = Embed(title="Special thanks to Spy_TheSingleRunc", description="She gaved ideas to the bot + she play admin house wow lol funny lala kikima-", color=Color.blue())
        embed.set_image(url="attachment://cat.png")
        embed.set_footer(text="Image credit by `codigoerror10014`.")
        
        path = join(dirname(__file__), "../resources/cat_spy.png")

        with open(path, 'rb') as f:
            pic = File(f, filename="cat.png")

        if embed:
            return await interaction.response.send_message(embed=embed,file=pic)

    @group.command(name="annayarik999alt", description=":3 (The image belongs to always_happy_and_smile)")
    async def cat_annayarik13alt(self, interaction: Interaction):
        embed = Embed(title="Special thanks to AnnaYarik999Alt", description="He helped me suggesting the commands", color=Color.yellow())
        embed.set_image(url="attachment://cat.jpg")
        embed.set_footer(text="Image credit by `always_happy_and_smile`. (AnnaYarik999Alt, i guess)")
        
        path = join(dirname(__file__), "../resources/cat_anna.jpg")

        with open(path, 'rb') as f:
            pic = File(f, filename="cat.jpg")

        if embed:
            return await interaction.response.send_message(embed=embed,file=pic)
    
async def setup(bot):
    await bot.add_cog(ContributorsCog(bot))