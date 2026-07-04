from datetime import datetime

from aiocache import cached
from discord import Interaction, Message
from discord.ext import commands
from pytz import UTC

from ....application import PoxBot


class VideoCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

    @cached(60)
    async def generate_funny_fade_video(
        self, interaction: Interaction, message: Message,
    ):
        _start_time = datetime.now(UTC)

        if not message.attachments or len(message.attachments) != 1:
            return await interaction.response.send_message(
                'This message has not exactly one attachment.', ephemeral=True,
            )

        attachment = message.attachments[0]
        _content_type = attachment.content_type or ''

        await interaction.response.send_message(
            f'Video generation requested by {interaction.user.mention}!\n'
            'Preparing data...',
        )
