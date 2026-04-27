import asyncio
import json
import random
from re import I
import aiofiles
import discord
from discord.ext import commands
from discord import ButtonStyle, CategoryChannel, Color, Embed, Forbidden, Interaction, Member, PermissionOverwrite, Role, TextChannel, TextStyle, app_commands
from os.path import join, exists

from bot import PoxBot

from logger import logger

class TicketData:
    def __init__(self, bot, file_path):
        self.bot = bot
        self.file_path = file_path
        self.data = {}
        self.lock = asyncio.Lock()
    
    async def load(self):
        if not exists(self.file_path):
            self.data = {}
            return
        
        async with self.lock:
            try:
                async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                    self.data = json.loads(content)
                
                logger.info(f"Data loaded successfully from {self.file_path}")
            except (IOError, json.JSONDecodeError) as e:
                logger.exception(f"Error loading ticket data: {e}. Starting with empty data")
                self.data = {}
    
    async def save(self):
        async with self.lock:
            content = json.dumps(self.data, indent=4)

            try:
                async with aiofiles.open(self.file_path, mode='w+', encoding="utf-8") as f:
                    await f.write(content)
                logger.info(f"Data saved successfully to {self.file_path}")
            except IOError as e:
                logger.exception(f"Error saving ticket data: {e}")
    
    def get_guild_data(self, guild_id):
        return self.data.setdefault(str(guild_id), {
            'master_channel_id': None,
            'ticket_category_id': None,
            'manager_role_ids': [],
            'tickets': {}
        })

class TicketCloseButton(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(label="Close ticket", style=ButtonStyle.red, custom_id="persistent_ticket_close")
    async def close_button_callback(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.close_ticket(interaction)

class TicketReasonModal(discord.ui.Modal, title="Open a new support ticket"):
    reason_input = discord.ui.TextInput(
        label="What's your reason for opening this ticket?",
        placeholder="e.g., I need help with server roles, or I found a bug...",
        style=TextStyle.paragraph,
        max_length=500,
        required=True
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: Interaction):
        reason = self.reason_input.value
        await self.cog.process_ticket_creation(interaction, reason)

class TicketPanel(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Open new ticket", style=discord.ButtonStyle.green, custom_id="persistent_ticket_create")
    async def create_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketReasonModal(self.cog))

class TicketSystemCog(commands.Cog):
    group = app_commands.Group(name="ticket", description="An group for TicketGroup.")
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.db = TicketData(bot, join(self.bot.root_path, "data/tickets.json"))
    
    async def cog_load(self):
        await self.db.load()
        self.bot.add_view(TicketPanel(self))
        self.bot.add_view(TicketCloseButton(self))
        logger.info("TicketSystem: Persistent views initialized")
    
    async def cog_unload(self):
        await self.db.save()
    
    async def process_ticket_creation(self, interaction: Interaction, reason: str):
        if interaction.guild is None: return await interaction.response.send_message("The ticket system cannot be used in User-mode.")
        
        guild = interaction.guild
        member = interaction.user
        guild_data = self.db.get_guild_data(guild.id)

        category_id = guild_data.get('ticket_category_id')
        manager_role_ids = guild_data.get('manager_role_ids', [])

        if not category_id or not manager_role_ids:
            return await interaction.response.send_message(
                "The ticket system is not fully set up for this server. Use /ticket setup to setup.",
                ephemeral=True
            )
        
        for ticket_channel_id, ticket_data in guild_data['tickets'].items():
            if int(ticket_data.get("user_id")) == member.id:
                existing_channel = guild.get_channel(int(ticket_channel_id))
                if existing_channel:
                    return await interaction.response.send_message(
                        f"You already have an active ticket: {existing_channel.mention}",
                        ephemeral=True
                    )
        
        await interaction.response.defer(ephemeral=True)

        category = guild.get_channel(category_id)

        if not category or not isinstance(category, CategoryChannel):
            return await interaction.followup.send("Error: ticket category not found.", ephemeral=True)
        
        overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            member: PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: PermissionOverwrite(read_messages=True, send_messages=True),
        }

        for role_id in manager_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel_name = f"ticket-{member.name.lower()[:10]}-{random.randint(0,9999)}"
        try:
            new_channel = await guild.create_text_channel(
                ticket_channel_name,
                category=category,
                overwrites=overwrites
            )
        except Forbidden:
            return await interaction.followup.send("I don't have permission to create ticket >:(", ephemeral=True)
        
        guild_data['tickets'][str(new_channel.id)] = {
            "user_id": str(member.id),
            "reason": reason
        }
        await self.db.save()

        embed = discord.Embed(
            title="Ticket opened.",
            description=f"Welcome {member.mention}! Staffs will be with you shortly. Please explain your issue here. \n\nTo close this ticket, press the button below.", 
            color=Color.blue()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Ticket ID: {new_channel.id}")

        await new_channel.send(
            f"{member.mention}",
            embed=embed,
            view=TicketCloseButton(self)
        )

        await interaction.followup.send(f"Your ticket has been created. Head over to {new_channel.mention} :3", ephemeral=True)
    
    async def close_ticket(self, interaction: Interaction):
        channel = interaction.channel

        if not isinstance(channel, TextChannel): return await interaction.response.send_message("Failed to close ticket.")

        guild_data = self.db.get_guild_data(interaction.guild_id)

        manager_role_ids = guild_data.get('manager_role_ids', [])
        
        if not isinstance(interaction.user, Member): return await interaction.response.send_message("The user is not member.")

        is_manager = any(r.id in manager_role_ids for r in interaction.user.roles)
        
        ticket_info = guild_data['tickets'].get(str(channel.id))
        is_creator = ticket_info and int(ticket_info.get("user_id")) == interaction.user.id
        
        if not is_manager and not is_creator:
            return await interaction.response.send_message("You don't have permission to close this ticket! :(", ephemeral=True)

        await interaction.response.send_message(f"Closing the ticket in 5 seconds... Have a great day!", ephemeral=False)

        await asyncio.sleep(5)
        
        if str(channel.id) in guild_data['tickets']:
            del guild_data['tickets'][str(channel.id)]
            await self.db.save()

        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user.name}")
        except discord.Forbidden:
             print(f"Failed to delete channel {channel.name}. Check bot permissions.")
    
    @group.command(name="setup", description="Configures the ticket system. (Work in progress)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(self, interaction: Interaction, panel_chanel: TextChannel, ticket_category: CategoryChannel, staff_role: Role):
        guild = interaction.guild

        if guild is None: return await interaction.response.send_message("You cannot use setup in out of guild-mode.")

        guild_data = self.db.get_guild_data(guild.id)

        guild_data['master_channel_id'] = panel_chanel.id
        guild_data['ticket_category_id'] = ticket_category.id
        guild_data['manager_role_ids'] = [staff_role.id]
        await self.db.save()

        embed = Embed(
            title="Sever support tickets",
            description=f"Need help? click the button below to open a new private support. (Work in progress)",
            color=Color.gold()
        )
        embed.set_footer(text="Thank you for using our weird ticket system :)")

        await panel_chanel.send(embed=embed, view=TicketPanel(self))
        await interaction.response.send_message(
            f"Ticket system configured and panel set up in {panel_chanel.mention}.\n"
            f"Tickets will be created in the **{ticket_category.name}** category and managed by the **{staff_role.name}** role.\n"
            f"(The system is still work in progress, there's may have an bug)",
            ephemeral=True,
        )

async def setup(bot):
    await bot.add_cog(TicketSystemCog(bot))