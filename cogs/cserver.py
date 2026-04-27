from aiocache import cached
from discord import AuditLogAction, ButtonStyle, Color, Embed, Guild, Interaction, NSFWLevel, SelectOption, app_commands, ui
from discord.app_commands import locale_str
from discord.ext import commands
from enum import IntFlag, auto

from bot import PoxBot
from logger import logger

from src.translator import translator_instance as i18n

class LoggingView(ui.View):
    def __init__(self, data_dict, user, default):
        super().__init__(timeout=60)
        self.data_dict = data_dict
        self.user = user
        self.categories = list(data_dict.keys())
        
        if isinstance(default, str):
            self.current_category = default
        else:
            self.current_category = self.categories[default]
        
        self.current_page = 0
        self.items_per_page = 10
    
    def get_total_pages(self):
        data_len = len(self.data_dict[self.current_category])
        return max(1, (data_len - 1) // self.items_per_page + 1)
    
    def create_embed(self):
        category_data = self.data_dict[self.current_category]
        total_pages = self.get_total_pages()
        
        embed = Embed(title=f"Guild history: {self.current_category}")
        
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = category_data[start:end]
        
        if not page_items:
            embed.description = "No history found for this category."
        else:
            description = ""
            for i, entry in enumerate(page_items, start + 1):
                description += f"**{i}.** {entry}\n"
            embed.description = description
        
        embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages} | {self.current_category}")
        return embed
    
    @ui.button(label="Prev", style=ButtonStyle.gray)
    async def previous_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("You're on the first page.", ephemeral=True)
    
    @ui.button(label="Next", style=ButtonStyle.gray)
    async def next_page(self, interaction: Interaction, button: ui.Button):
        total_pages = self.get_total_pages()
        if self.current_page < total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("You're on the last page 3:", ephemeral=True)
    
    @ui.select(placeholder="Select history type", options=[
        SelectOption(label="Kicks", value="kicks", emoji="👟"),
        SelectOption(label="Bans", value="bans", emoji="🔨"),
        SelectOption(label="Timeouts", value="timeouts", emoji="🚫")
    ])
    async def select_category(self, interaction: Interaction, select: ui.Select):
        self.current_category = select.values[0]
        self.current_page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("Your not executor of this menu idiot.", ephemeral=True)
            return False
        return True

class GuildCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    checker_group = app_commands.Group(name="guild",description="group for checker cog")
    
    @checker_group.command(name="info", description="checks current server information")
    @app_commands.guild_only()
    async def check_server_info(self, interaction: Interaction):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        guild = interaction.guild
        
        await interaction.response.defer(thinking=True)
        
        if guild:
            temp1 = {
                'Description': guild.description if guild.description else "No description.",
                'Preferred Locale': guild.preferred_locale.language_code,
                'Owner': guild.owner.mention if guild.owner else "Unknown",
                'Members': f"{len(guild.members):,} members",
                'Created on': guild.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'Current Shard': guild.shard_id if guild.shard_id else "N/A",
                'Over 250?': "Yes" if guild.large == True else "No",
                'Roles': f"{len(guild.roles):,} roles",
                'Emojis': f"{len(guild.emojis):,} emojis",
                'Stickers': f"{len(guild.stickers):,} stickers",
                'Boost Level': f"Level {guild.premium_tier}",
                'Boosts': f"{guild.premium_subscription_count:,} boosts",
                'Channels': f"{len(guild.channels):,} channels",
                'Categories': f"{len(guild.categories):,} categories",
                'Chunked': f"{'Yes' if guild.chunked else 'No'}",
            }
            e = Embed(title=f"Information for {guild.name}", color=Color.blue())
            e.set_footer(text=f"Guild ID: {guild.id}")
            e.set_author(name=f"By {guild.owner.name if guild.owner else 'Unknown'}", icon_url=guild.owner.avatar.url if guild.owner and guild.owner.avatar else None)

            for key,value in temp1.items():
                e.add_field(name=key, value=value, inline=True)

            if guild.icon:
                e.set_thumbnail(url=guild.icon.url)
            return await interaction.followup.send(embed=e)
        else:
            return await interaction.followup.send("Guild not found.")
    
    @checker_group.command(name="kickmembers", description="Kicks real user members")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def kick_all_realusers(self, interaction: Interaction):
        guild = interaction.guild
        
        await interaction.response.defer(thinking=True)
        
        if guild:
            for member in guild.members:
                try:
                    if member.bot: continue
                    await member.kick(reason="Kicked via command")
                except Exception as e:
                    logger.exception(e)
            return await interaction.followup.send("kicked")
        else:
            return await interaction.followup.send("Guild not found.")
    
    @cached(300)
    @checker_group.command(name="nsfw_level",description="Checks if server has NSFW Level")
    @app_commands.guild_only()
    async def check_nsfw_level(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Is server NSFW?",description="")
        if interaction.guild:
            match (interaction.guild.nsfw_level):
                case NSFWLevel.default:
                    embed.description = "Not NSFW"
                case NSFWLevel.explicit:
                    embed.description = "Explicit"
                case NSFWLevel.safe:
                    embed.description = "Safe"
                case NSFWLevel.age_restricted:
                    embed.description = "Age restricted"
                case _:
                    embed.description = "Unknown"
        else:
            return await interaction.followup.send("Guild not found.")
        
        return await interaction.followup.send(embed=embed)
    
    @cached(300)
    @checker_group.command(name="icon", description="Gets server icon.")
    @app_commands.guild_only()
    async def get_server_icon(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        if interaction.guild and interaction.guild.icon:
            return await interaction.followup.send(embed=Embed(title="Server Icon")
                .set_image(url=interaction.guild.icon.url))
        else:
            return await interaction.followup.send("No icon found.")
    
    @checker_group.command(name="count", description="Gets count of members by usertype, and calculates")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def get_member(self, interaction: Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            return await interaction.followup.send(embed=Embed(title="Error", description=locale_str("error.GuildOnly"), color=Color.red()))
        
        embed = Embed(
            title=f"{interaction.guild.name}'s member count data",
            description="",
            color=Color.green()
        )
        
        total_members = 0
        bots = 0
        nitros = 0
        
        for member in interaction.guild.members:
            total_members += 1
            if member.bot: bots += 1
            if member.premium_since: nitros += 1
        
        lines = []
        
        if total_members > 0:
            lines.append(f"Total: {total_members}")
            lines.append("Bot ratio: {}%".format(round((bots/total_members) * 100)))
            lines.append(f"Nitro users: {nitros}")
    
    @cached(60)
    @checker_group.command(name="members_list", description="Retrieves memebers in this guild.")
    @app_commands.guild_only()
    async def get_members(self, interaction: Interaction, include_bot: bool = False, include_member: bool = True):
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(embed=Embed(title="Error", description=locale_str("error.GuildOnly"), color=Color.red()))
        
        embed = Embed(
            title=f"{interaction.guild.name}'s members",
            description="",
            color=Color.green()
        )

        members = []

        if include_bot == False and include_member == False:
            embed.color = Color.red()
            embed.description = "You cannot exclude both!"
            return await interaction.followup.send(embed=embed)
        
        for member in sorted(interaction.guild.members, key=lambda r: r.top_role.position, reverse=True):
            if include_bot and member.bot:
                members.append(f"{member.top_role.mention}: {member.mention}")
            
            if include_member and not member.bot:
                members.append(f"{member.top_role.mention}: {member.mention}")
        
        if len(members) == 0:
            embed.color = Color.purple()
            embed.description = "Not found"
            return await interaction.followup.send(embed=embed)
        else:
            embed.description = "\n".join(members)
            return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @checker_group.command(name="search_members", description="Searches members by keyword.")
    @app_commands.guild_install()
    async def search_members(self, interaction: Interaction, keyword: str):
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(embed=Embed(title="Error", description=locale_str("error.GuildOnly"), color=Color.red()))
        
        embed = Embed(
            title=f"Member contains with '{keyword}' by username in {interaction.guild.name}",
            description="",
            color=Color.green()
        )

        result = []

        for member in interaction.guild.members:
            if keyword in member.name:
                result.append(member.mention)
        
        if len(result) == 0:
            embed.color = Color.purple()
            embed.description = f"User starts with {keyword} not found from this guild."
            return await interaction.followup.send(embed=embed)
        else:
            embed.description = ", ".join(result)
            return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @checker_group.command(name="role_list", description="Retrieves list of roles.")
    @app_commands.guild_install()
    async def get_roles(self, interaction: Interaction):
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send(embed=Embed(title="Error", description=locale_str("error.GuildOnly"), color=Color.red()))
        
        embed = Embed(
            title=f"List of roles in {interaction.guild.name}",
            description="\n".join([role.mention for role in sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True) if not role.managed and role.name != "@everyone"]),
            color=Color.green()
        )

        return await interaction.followup.send(embed=embed)
    
    @cached(60)
    async def fetch_guild_history(self, guild: Guild):
        history = {
            "kicks": [], "bans": [], "timeouts": []
        }
        
        async for entry in guild.audit_logs(limit=128):
            target = entry.target
            user = entry.user
            reason = entry.reason or "No reason provided"
            
            if entry.action == AuditLogAction.kick:
                history['kicks'].append(f"**Target:** {target} | **Mod:** {user}\n- *Reason: {reason}*")
            elif entry.action == AuditLogAction.ban:
                history['bans'].append(f"**Target:** {target} | **Mod:** {user}\n- *Reason: {reason}*")
            elif entry.action == AuditLogAction.member_update:
                if hasattr(entry.after, 'communication_disabled_until'):
                    if entry.after.communication_disabled_until:
                        until = entry.after.communication_disabled_until.strftime("%Y-%m-%d %H:%M")
                        history["timeouts"].append(f"**Target:** {target} | **Until:** {until}\n- *Reason: {reason}*")
        
        return history
    
    @checker_group.command(name="logs", description="Shows a menu to get history of kicks, bans and timeouts.")
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def show_history(self, interaction: Interaction):
        if not interaction.guild: return await interaction.response.send_message("Must be in guild.")
        history_data = await self.fetch_guild_history(interaction.guild)
        
        view = LoggingView(history_data, interaction.user, 'kicks')
        await interaction.response.send_message(embed=view.create_embed(), view=view)

async def setup(bot):
    await bot.add_cog(GuildCog(bot))