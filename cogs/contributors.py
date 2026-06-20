from os.path import dirname, join
from pathlib import Path
from typing import Any

import aiofiles
from discord import Color, Embed, File, Interaction, app_commands
from discord.ext.commands import Cog

import data
from bot import PoxBot
from src.translator import translator_instance


class ContributorsCog(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.contributor_list: list[dict[str, Any]] = data.get_contributors_v2()

    group = app_commands.Group(name="contributors", description=app_commands.locale_str("command.contributors.description"))
    
    async def safe_get_user(self, user_id: int):
        user = self.bot.get_user(user_id)
        if user:
            return user
        try:
            user = await self.bot.fetch_user(user_id)
            return user
        except Exception:
            return None
    
    @group.command(name="list", description=app_commands.locale_str("Lists all contributors.", extras={"key": "command.contributors.list.description"}))
    async def list_contributors(self, interaction: Interaction):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(title=translator_instance.T("command.contributors.list.embeds.default.title", loc), description=translator_instance.T("command.contributors.list.embeds.default.description", loc))
        
        await interaction.response.defer()
        
        hmmm = []

        for contributor in self.contributor_list:
            user_id = contributor.get("id", None)
            if not user_id: continue
               
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
            embed.title = translator_instance.T("error.embeds.contributor_not_found.title", loc)
            embed.title = translator_instance.T("error.embeds.contributor_not_found.description", loc, {"contributor": contributor_id})
    
async def setup(bot):
    await bot.add_cog(ContributorsCog(bot))