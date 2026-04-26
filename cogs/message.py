import asyncio
import random
import re
import textwrap
from typing import Optional
from aiocache import cached
from attr import has
import discord
from discord.ext import commands
from discord import Embed, Forbidden, Interaction, Member, Message, TextChannel, TextStyle, app_commands
from bot import PoxBot
from logger import logger
import stuff
from textwrap import shorten

class DMSendModal(discord.ui.Modal):
    def __init__(self, enable_sent_by: bool|None, member) -> None:
        super().__init__(title="Send DM to member", timeout=None, custom_id="dm-sender-modal")

        self.member = member
        #self.member = discord.ui.UserSelect(placeholder="Choose a member...", max_values=1, custom_id="unique_member_selector", required=True)
        self.text_to_send = discord.ui.TextInput(label="Text to send", style=TextStyle.paragraph, required=True)
        self.enable_sent_by = enable_sent_by

        #self.add_item(self.member)
        self.add_item(self.text_to_send)
    
    async def on_submit(self, interaction: Interaction):
        try:
            combine = [self.text_to_send.value]
            sent_by_text = self.enable_sent_by
            if self.member.id == 1321324137850994758: combine.append(f"Sent by `{interaction.user.name}` with sent_by_text is {sent_by_text}.")
            elif sent_by_text == True: combine.append(f"\nSent by `{interaction.user.name}`.")
            #combine.append(f"\nUID: `{''.join(random.choices(string.ascii_letters + string.digits, k=24))}`")
            await self.member.send("\n".join(combine))
            if self.member.id == 1321324137850994758 and sent_by_text == False: await interaction.response.send_message(f"Your message sent as DM, but you cannot disable the sent_by_text for DM that directs to Creator of the bot, due to security issue.")
            else: await interaction.response.send_message(f"Your message sent as DM.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to send DM. {e}", ephemeral=True)
            logger.error(f"Error. {e}")

class MessageGroup(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    group = app_commands.Group(name="message", description="An group for messages.")
    
    @group.command(name="say", description="Makes the bot say something in current channel.")
    @app_commands.guild_only()
    async def say_something(self, ctx: Interaction, *, msg: str):
        await ctx.response.send_message(f"{msg}")

    @group.command(name="send", description="Sends a message.")
    @app_commands.guild_only()
    async def send_message(self, interaction: Interaction, channel: TextChannel, message: str):
        try:
            await channel.send(f"{message}\nSent by {interaction.user.name}")
        except Forbidden:
            return await interaction.response.send_message("Failed to send: I do not have permission to send it.")
        except Exception:
            raise

    @group.command(name="mass_delete", description="Deletes messages before specified messages.")
    @app_commands.describe(limit="How much range bot will delete.")
    @app_commands.checks.has_permissions(manage_channels=True, manage_messages=True)
    @app_commands.guild_only()
    async def mass_delete_messages(self, interaction: Interaction, limit: Optional[int] = 100):
        await interaction.response.defer()
        
        if limit is None:
            limit = 100
        
        def check_messages(m):
            return not m == interaction.message
        
        if isinstance(interaction.channel, discord.TextChannel):
            while True:
                deleted = await interaction.channel.purge(limit=limit, check=check_messages)
                if len(deleted) < limit:
                    break
            
            await interaction.followup.send(f"Deleted {limit} messages.")
    
    @group.command(name="purge", description="Purges a specific amount of messages sent earlier.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def purge_messages(self, interaction: Interaction, limit: Optional[int] = 100):
        await interaction.response.defer()

        def check_messages(m):
            return not interaction.message

        deleted_count = 0

        if isinstance(interaction.channel, discord.TextChannel):
            deleted = await interaction.channel.purge(limit=limit if limit is not None else 100, check=check_messages)
            await interaction.followup.send(f"Purged {len(deleted)} messages.")

    @group.command(name="purge_bot_messages",description="Deletes bot's messages")
    @app_commands.describe(limit="How much bot deletes it")
    @app_commands.checks.has_permissions(manage_channels=True, manage_messages=True)
    @app_commands.check(stuff.is_bot_owner)
    @app_commands.guild_only()
    async def delete_messages_sent_by_bot(self, ctx: Interaction, limit: int = 100):
        def check_messages(m: Message):
            is_bot = m.author == self.bot.user
            is_replied = False
            if m.reference and m.reference.resolved:
                if hasattr(m.reference.resolved, 'author'):
                    is_replied = m.reference.resolved.author == self.bot.user
            
            if ctx.message:
                if m.id == ctx.message.id:
                    return False

            return (is_bot or is_replied)

        deleted_count = 0
        
        if isinstance(ctx.channel, discord.abc.GuildChannel):
            while True:
                if isinstance(ctx.channel, TextChannel):
                    deleted = await ctx.channel.purge(limit=limit, check=check_messages)
                    deleted_count += len(deleted)
                    if len(deleted) < limit:
                        break
                
            await ctx.response.send_message(content=f"Deleted {deleted_count} messages including the messages that replied to me.")

    @group.command(name="uwuify", description="Sends a message to everyone that you did")
    @app_commands.describe(msg="Message to send")
    async def uwuified_say_something(self, ctx: Interaction, *, msg: str):
        await ctx.response.send_message(f"{stuff.to_uwu(msg)}")
    
    @group.command(name="direct_message",description="DMs to a member")
    @app_commands.checks.has_permissions(send_messages=True)
    @app_commands.guild_only()
    async def send_dm_to_member(self, ctx: Interaction, member: Member, enable_sent_by: Optional[bool]):
        return await ctx.response.send_modal(DMSendModal(enable_sent_by, member))
    
    @group.command(name="send2", description="...")
    @app_commands.guild_only()
    @app_commands.check(stuff.is_bot_owner)
    async def send2(self, interaction: Interaction, message: str):
        is_owner = await self.bot.is_owner(interaction.user)

        if not is_owner: return await interaction.response.send_message("You're not allowed to use this command.")
        await interaction.response.defer()
        guilds = self.bot.guilds

        total = 0
        send_count = 0
        sent_channels = []

        for guild in guilds:
            channels = guild.channels
            for channel in channels:
                await asyncio.sleep(0.25)
                if isinstance(channel, TextChannel) and re.search(r"[a-zA-Z0-9_\-\s]",channel.name):
                    total += 1
                    try:
                        await channel.send(message)
                        send_count += 1
                        sent_channels.append(channel.name)
                        logger.info(f"Sent to {channel.name}")
                    except Forbidden as e:
                        logger.error(f"{channel.name} Forbidden")
        return interaction.followup.send(f"Sent to {send_count} of channels: "+"\n".join(sent_channels))
    
    @cached(60)
    @group.command(name="search_for", description="Searches messages in current channel.")
    @app_commands.guild_only()
    async def search_messages_in_channel(self, interaction: Interaction, keyword: str, limit: Optional[int] = 100):
        await interaction.response.defer()
        found_messages = []

        if limit is None: limit = 1000
        else: limit = stuff.clamp(limit, 1,10000)

        if isinstance(interaction.channel, discord.TextChannel):
            async for message in interaction.channel.history(limit=limit):
                if keyword.lower() in message.content.lower():
                    logger.debug(f"Found message: {message.content} by {message.author.name}")
                    found_messages.append(f"- {message.author.name}: {stuff.crop_word(message.content, keyword) or textwrap.shorten(message.content, width=30)} (ID: {message.id})")
        
        embed = Embed(title="Search Results")

        if found_messages:
            embed.description = "\n".join(found_messages)
            embed.color = discord.Color.green()
            return await interaction.followup.send(embed=embed)
        else:
            embed.description = f"No messages found containing '{keyword}'."
            embed.color = discord.Color.red()
            return await interaction.followup.send(embed=embed)

    @cached(120)
    @group.command(name="last_sent", description="Fetches the last message from the current channel.")
    @app_commands.guild_only()
    async def fetch_last_message(self, interaction: Interaction):
        await interaction.response.defer()
        message = None
        if isinstance(interaction.channel, discord.TextChannel):
            message = interaction.channel.last_message
        
        embed = Embed(title="Last Message")

        if message:
            embed.title = f"Last Message sent in {interaction.channel.name if interaction.channel and isinstance(interaction.channel, discord.TextChannel) else 'Not an Text Channel'} by {message.author.name}"
            embed.description = message.content
            embed.set_footer(text=f"Message ID: {message.id}")
            embed.color = discord.Color.green()

            return await interaction.followup.send(embed=embed)
        else:
            embed.description = "No messages found in this channel."
            embed.color = discord.Color.red()

            return await interaction.followup.send(embed=embed)
    
    @cached(240)
    @group.command(name="first_sent", description="Fetches the first message from the current channel.")
    @app_commands.guild_only()
    async def fetch_first_message(self, interaction: Interaction):
        await interaction.response.defer()
        message = None
        if isinstance(interaction.channel, discord.TextChannel):
            async for msg in interaction.channel.history(limit=1, oldest_first=True):
                message = msg
        
        embed = Embed(title="First Message")

        if message:
            embed.title = f"First Message sent in {interaction.channel.name if interaction.channel and isinstance(interaction.channel, discord.TextChannel) else 'Not an Text Channel'} by {message.author.name}"
            embed.description = message.content
            embed.set_footer(text=f"Message ID: {message.id}")
            embed.color = discord.Color.purple()

            return await interaction.followup.send(embed=embed)
        else:
            embed.description = "No messages found in this channel."
            embed.color = discord.Color.red()

            return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @group.command(name="message_count", description="Counts messages in the current channel.")
    @app_commands.guild_only()
    async def count_messages_in_channel(self, interaction: Interaction):
        await interaction.response.defer()
        message_count = 0

        if isinstance(interaction.channel, discord.TextChannel):
            # Using history with limit=None to count all messages
            async for _ in interaction.channel.history(limit=None):
                message_count += 1
        
        return await interaction.followup.send(f"There are {message_count} messages in this channel.")

    @cached(60)
    @group.command(name="get_random_message", description="Fetches a random message from the current channel.")
    @app_commands.guild_only()
    async def fetch_random_message(self, interaction: Interaction):
        await interaction.response.defer()
        messages = []

        if isinstance(interaction.channel, discord.TextChannel):
            async for message in interaction.channel.history(limit=1000):
                messages.append(message)
        
        embed = Embed(title="Random Message")

        if messages:
            random_message = random.choice(messages)
            embed.title = f"Message by {random_message.author.name}"
            embed.description = random_message.content
            embed.set_footer(text=f"Message ID: {random_message.id}")
            embed.color = discord.Color.blue()

            return await interaction.followup.send(embed=embed)
        else:
            embed.description = "No messages found in this channel."
            embed.color = discord.Color.red()

            return await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MessageGroup(bot))