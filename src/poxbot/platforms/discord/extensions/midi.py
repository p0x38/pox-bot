from __future__ import annotations

import asyncio
import io
import logging
import os
import re
from pathlib import Path

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from ....application.bot import PoxBot

# Adjust this import to the actual location of MIDIProcessor.
from ....features.midi.midi_processor import MIDIProcessor

logger = logging.getLogger(__name__)

MAX_MIDI_SIZE = 10 * 1024 * 1024  # 10 MiB


class MidiCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot

        soundfont = os.getenv(
            "MIDI_SOUNDFONT_PATH",
            "src/poxbot/assets/sf2/gmgsx.sf2",
        )

        self.processor = MIDIProcessor(soundfont=soundfont)

    group = app_commands.Group(
        name="midi",
        description=app_commands.locale_str(
            "command.midi.description"
        ),
    )

    @group.command(
        name="convert",
        description=app_commands.locale_str(
            "command.midi.convert.description"
        ),
    )
    @app_commands.describe(
        attachment="The MIDI file to convert into an MP3."
    )
    async def convert_midi(
        self,
        interaction: Interaction,
        attachment: discord.Attachment,
    ) -> None:
        # Validate the attachment before downloading it.
        if Path(attachment.filename).suffix.lower() not in {
            ".mid",
            ".midi",
        }:
            await interaction.response.send_message(
                "Please upload a `.mid` or `.midi` file.",
                ephemeral=True,
            )
            return

        if attachment.size > MAX_MIDI_SIZE:
            await interaction.response.send_message(
                "That MIDI file is too large. "
                "The maximum allowed size is 10 MiB.",
                ephemeral=True,
            )
            return

        # Acknowledge the interaction before downloading and converting.
        await interaction.response.defer(thinking=True)

        try:
            midi_data = await attachment.read()

            # Check the actual payload size as well.
            if len(midi_data) > MAX_MIDI_SIZE:
                await interaction.followup.send(
                    "The uploaded MIDI file exceeds the 10 MiB limit.",
                    ephemeral=True,
                )
                return

            mp3_buffer = io.BytesIO()

            try:
                # MIDIProcessor is synchronous. Keep it off the event loop.
                await asyncio.to_thread(
                    self.processor.convert,
                    midi_data,
                    mp3_buffer,
                )

                mp3_buffer.seek(0)

                # Keep the generated filename safe and predictable.
                stem = Path(attachment.filename).stem
                stem = re.sub(r"[^\w.-]+", "_", stem).strip("._")
                stem = stem[:100] or "converted"

                output_filename = f"{stem}.mp3"

                mp3_file = discord.File(
                    mp3_buffer,
                    filename=output_filename,
                )

                try:
                    await interaction.followup.send(
                        content="MIDI conversion complete.",
                        file=mp3_file,
                    )
                finally:
                    mp3_file.close()
            finally:
                mp3_buffer.close()

        except Exception:
            logger.exception(
                "Failed to convert MIDI attachment %r (user_id=%s)",
                attachment.filename,
                interaction.user.id,
            )

            await interaction.followup.send(
                "I couldn't convert that MIDI file. "
                "It may be invalid, or the audio converter may not "
                "be configured correctly.",
                ephemeral=True,
            )


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(MidiCog(bot))
