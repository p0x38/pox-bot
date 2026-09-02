import random
import textwrap

import discord
from aiocache import cached
from discord import (
    Embed,
    Forbidden,
    Interaction,
    Member,
    TextChannel,
    TextStyle,
    app_commands,
)
from discord.ext import commands

from ....application import PoxBot
from ....infrastructure.logger import get_logger
from ....shared.utils.math_util import clamp
from ....shared.utils.text_util import crop_word


class DMSendModal(discord.ui.Modal):
    def __init__(self, enable_sent_by: bool | None, member) -> None:
        super().__init__(
            title='Send DM to member',
            timeout=None,
            custom_id='dm-sender-modal',
        )

        self.member = member
        # self.member = discord.ui.UserSelect(
        #       placeholder="Choose a member...", max_values=1,
        # custom_id="unique_member_selector", required=True)
        self.text_to_send = discord.ui.TextInput(
            label='Text to send',
            style=TextStyle.paragraph,
            required=True,
        )
        self.enable_sent_by = enable_sent_by

        # self.add_item(self.member)
        self.add_item(self.text_to_send)

    async def on_submit(self, interaction: Interaction):
        try:
            combine = [self.text_to_send.value]
            sent_by_text = self.enable_sent_by
            if self.member.id == 1321324137850994758:
                combine.append(
                    f'Sent by `{interaction.user.name}` with sent_by_text is {sent_by_text}.',
                )
            elif sent_by_text:
                combine.append(f'\nSent by `{interaction.user.name}`.')
            await self.member.send('\n'.join(combine))
            if self.member.id == 1321324137850994758 and not sent_by_text:
                await interaction.response.send_message(
                    'Your message sent as DM,'
                    'but you cannot disable the sent_by_text for DM'
                    'that directs to Creator of the bot, due to security issue.',
                )
            else:
                await interaction.response.send_message(
                    'Your message sent as DM.',
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.response.send_message(
                f'Failed to send DM. {e}',
                ephemeral=True,
            )
            get_logger(__name__).exception('Exception thrown while trying to send a DM')


class MessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    group = app_commands.Group(name='message', description='An group for messages.')

    @group.command(
        name='say',
        description='Makes the bot say something in current channel.',
    )
    @app_commands.guild_only()
    async def say_something(self, ctx: Interaction, *, msg: str):
        await ctx.response.send_message(f'{msg}')

    @group.command(name='send', description='Sends a message.')
    @app_commands.checks.cooldown(1, 3.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def send_message(
        self,
        interaction: Interaction,
        channel: TextChannel,
        message: str,
    ):
        try:
            await channel.send(f'{message}\nSent by {interaction.user.name}')
        except Forbidden:
            return await interaction.response.send_message(
                'Failed to send: I do not have permission to send it.',
            )
        except Exception:
            raise

    @group.command(
        name='mass_delete',
        description='Deletes messages before specified messages.',
    )
    @app_commands.describe(limit='How much range bot will delete.')
    @app_commands.checks.has_permissions(manage_channels=True, manage_messages=True)
    @app_commands.guild_only()
    async def mass_delete_messages(
        self,
        interaction: Interaction,
        limit: int | None = 100,
    ):
        await interaction.response.defer()

        if limit is None:
            limit = 100

        def check_messages(m):
            return m != interaction.message

        if isinstance(interaction.channel, discord.TextChannel):
            while True:
                deleted = await interaction.channel.purge(
                    limit=limit,
                    check=check_messages,
                )
                if len(deleted) < limit:
                    break

            await interaction.followup.send(f'Deleted {limit} messages.')

    @group.command(
        name='purge',
        description='Purges a specific amount of messages sent earlier.',
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def purge_messages(self, interaction: Interaction, limit: int | None = 100):
        await interaction.response.defer()

        def check_messages(m):
            return not interaction.message

        if isinstance(interaction.channel, discord.TextChannel):
            deleted = await interaction.channel.purge(
                limit=limit if limit is not None else 100,
                check=check_messages,
            )
            await interaction.followup.send(f'Purged {len(deleted)} messages.')

    @group.command(name='direct_message', description='DMs to a member')
    @app_commands.checks.has_permissions(send_messages=True)
    @app_commands.guild_only()
    async def send_dm_to_member(
        self,
        ctx: Interaction,
        member: Member,
        enable_sent_by: bool | None,
    ):
        return await ctx.response.send_modal(DMSendModal(enable_sent_by, member))

    @cached(60)
    @group.command(
        name='search_for',
        description='Searches messages in current channel.',
    )
    @app_commands.guild_only()
    async def search_messages_in_channel(
        self,
        interaction: Interaction,
        keyword: str,
        limit: int | None = 100,
    ):
        await interaction.response.defer()
        found_messages = []

        limit = 1000 if limit is None else clamp(limit, 1, 10000)

        if isinstance(interaction.channel, discord.TextChannel):
            async for message in interaction.channel.history(limit=limit):
                if keyword.lower() in message.content.lower():
                    self.bot.logger.debug(
                        'Found message: %s by %s',
                        message.content,
                        message.author.name,
                    )
                    found_messages.append(
                        f'- {message.author.name}: {
                            crop_word(message.content, keyword)
                            or textwrap.shorten(message.content, width=30)
                        } (ID: {message.id})',
                    )

        embed = Embed(title='Search Results')

        if found_messages:
            embed.description = '\n'.join(found_messages)
            embed.color = discord.Color.green()
            return await interaction.followup.send(embed=embed)
        embed.description = f"No messages found containing '{keyword}'."
        embed.color = discord.Color.red()
        return await interaction.followup.send(embed=embed)

    @cached(120)
    @group.command(
        name='last_sent',
        description='Fetches the last message from the current channel.',
    )
    @app_commands.guild_only()
    async def fetch_last_message(self, interaction: Interaction):
        await interaction.response.defer()
        message = None
        if isinstance(interaction.channel, discord.TextChannel):
            message = interaction.channel.last_message

        embed = Embed(title='Last Message')

        if message:
            embed.title = f'Last Message sent in {
                (
                    interaction.channel.name
                    if interaction.channel
                    and isinstance(interaction.channel, discord.TextChannel)
                    else "Not an Text Channel"
                )
            } by {message.author.name}'
            embed.description = message.content
            embed.set_footer(text=f'Message ID: {message.id}')
            embed.color = discord.Color.green()

            return await interaction.followup.send(embed=embed)
        embed.description = 'No messages found in this channel.'
        embed.color = discord.Color.red()

        return await interaction.followup.send(embed=embed)

    @cached(240)
    @group.command(
        name='first_sent',
        description='Fetches the first message from the current channel.',
    )
    @app_commands.guild_only()
    async def fetch_first_message(self, interaction: Interaction):
        await interaction.response.defer()
        message = None
        if isinstance(interaction.channel, discord.TextChannel):
            async for msg in interaction.channel.history(limit=1, oldest_first=True):
                message = msg

        embed = Embed(title='First Message')

        if message:
            embed.title = f'First Message sent in {
                (
                    interaction.channel.name
                    if interaction.channel
                    and isinstance(interaction.channel, discord.TextChannel)
                    else "Not an Text Channel"
                )
            } by {message.author.name}'
            embed.description = message.content
            embed.set_footer(text=f'Message ID: {message.id}')
            embed.color = discord.Color.purple()

            return await interaction.followup.send(embed=embed)
        embed.description = 'No messages found in this channel.'
        embed.color = discord.Color.red()

        return await interaction.followup.send(embed=embed)

    @cached(60)
    @group.command(
        name='message_count',
        description='Counts messages in the current channel.',
    )
    @app_commands.guild_only()
    async def count_messages_in_channel(self, interaction: Interaction):
        await interaction.response.defer()
        message_count = 0

        if isinstance(interaction.channel, discord.TextChannel):
            # Using history with limit=None to count all messages
            async for _ in interaction.channel.history(limit=None):
                message_count += 1

        return await interaction.followup.send(
            f'There are {message_count} messages in this channel.',
        )

    @cached(60)
    @group.command(
        name='get_random_message',
        description='Fetches a random message from the current channel.',
    )
    @app_commands.guild_only()
    async def fetch_random_message(self, interaction: Interaction):
        await interaction.response.defer()
        messages = []

        if isinstance(interaction.channel, discord.TextChannel):
            messages.extend([
                message async for message in interaction.channel.history(limit=1000)
            ])

        embed = Embed(title='Random Message')

        if messages:
            random_message = random.choice(messages)
            embed.title = f'Message by {random_message.author.name}'
            embed.description = random_message.content
            embed.set_footer(text=f'Message ID: {random_message.id}')
            embed.color = discord.Color.blue()

            return await interaction.followup.send(embed=embed)
        embed.description = 'No messages found in this channel.'
        embed.color = discord.Color.red()

        return await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MessageCog(bot))
