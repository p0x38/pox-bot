import sys
import wave
from datetime import timedelta
from io import BytesIO
from time import time

import discord
from aiocache import cached
from discord import (
    Color,
    Embed,
    File,
    Forbidden,
    HTTPException,
    Interaction,
    NotFound,
    app_commands,
)
from discord.ext import commands
from edge_tts import Communicate, exceptions
from gtts import gTTS
from piper import PiperVoice, SynthesisConfig
from scipy.io.wavfile import write

from logger import logger
from src.bot import PoxBot
from src.tts.manager import TTSEngineType, TTSManager
from stuff import clamp_f


class TextToSpeechCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.tts_manager = TTSManager(bot)

    async def cog_load(self):
        await self.tts_manager.cog_load()

    ttsgroup = app_commands.Group(
        name="tts",
        description=app_commands.locale_str("command.tts.description"),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    async def googletts_autocomplete(
        self, interaction: Interaction, current: str  # noqa: ARG002
    ) -> list[app_commands.Choice[str]]:
        suggestions = []

        for code, full in self.bot.gtts_cache_langs.items():
            if current.lower() in code.lower() or current.lower() in full.lower():
                suggestions.append(app_commands.Choice(name=full, value=code))

            if len(suggestions) >= 20:
                break

        return suggestions

    async def edgetts_autocomplete(
        self, interaction: Interaction, current: str  # noqa: ARG002
    ) -> list[app_commands.Choice[str]]:
        suggestions = []

        for voice in self.tts_manager.edge_tts_voices:
            if current.lower() in voice.get("Name").lower():
                suggestions.append(
                    app_commands.Choice(
                        name=voice.get("FriendlyName"), value=voice.get("Name")
                    )
                )

            if len(suggestions) >= 20:
                break

        return suggestions

    async def pockettts_autocomplete(
        self, interaction: Interaction, current: str  # noqa: ARG002
    ) -> list[app_commands.Choice[str]]:
        suggestions = []

        for voice in self.tts_manager.pocket_tts_predefined_models:
            if current.lower() in voice.lower():
                suggestions.append(
                    app_commands.Choice(name=f"{voice} (Built-in)", value=voice)
                )

            if len(suggestions) >= 20:
                break

        for voice_data in self.tts_manager.pocket_tts_custom_models:
            voice_name = voice_data.get("name")
            voice_friendly_name = voice_data.get("friendly_name")
            voice_path = voice_data.get("path")

            if not voice_name or not voice_friendly_name or not voice_path:
                continue

            if current.lower() in voice_name.lower() or current.lower() in voice_friendly_name.lower():
                suggestions.append(
                    app_commands.Choice(name=f"{voice_friendly_name} (Custom)", value=self.bot.root_path + voice_path)
                )

            if len(suggestions) >= 20:
                break

        return suggestions

    async def tts_voice_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        engine = interaction.namespace.engine

        match (engine):
            case TTSEngineType.GOOGLE_TTS:
                return await self.googletts_autocomplete(interaction, current)
            case TTSEngineType.POCKET_TTS:
                return await self.pockettts_autocomplete(interaction, current)
            case TTSEngineType.EDGE_TTS:
                return await self.edgetts_autocomplete(interaction, current)
            case _:
                return []

    @app_commands.command(name="tts_v2", description=app_commands.locale_str("commands.tts_v2.description"))
    @app_commands.autocomplete(voice=tts_voice_autocomplete)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def generate_tts(
        self,
        interaction: Interaction,
        input: str,
        engine: TTSEngineType,
        voice: str | None = None,
    ):
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db
            else interaction.locale
        )
        await interaction.response.defer(thinking=True)

        embed = Embed()

        try:
            data = {"input": input, "engine": engine, "voice": voice}
            result = await self.tts_manager.generate_speech(data)

            if not result:
                raise RuntimeError("Result returned None")

            if not result.get("output"):
                raise RuntimeError("Output returned None")

            filename = f"{str(engine).replace(' ', '')}_{int(time())!s}." + result["type"]

            file = File(result["output"], filename)

            embed.color = Color.green()
            embed.set_footer(text=f"Generated by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            duration = result.get("duration")

            temp_tts = {
                'tts_input': input,
                'tts_engine': str(engine),
                'tts_voice': voice if voice else "None",
            }

            if isinstance(duration, timedelta):
                temp_tts['tts_generation_took'] = f"{duration.total_seconds():.3f}"

            if result.get("chunk_count"):
                temp_tts['tts_chunk'] = str(result["chunk_count"])

            temp_tts = self.bot.internal_translator.translate_map(temp_tts, str(loc))

            for name, value in temp_tts.items():
                embed.add_field(name=name, value=value, inline=True)

            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            embed.color = Color.red()
            embed.title = f"Exception thrown: {e.__class__.__name__}"
            embed.description = str(e)

            await interaction.followup.send(embed=embed)

    @cached(60 * 2)
    @ttsgroup.command(name="google_tts")
    @app_commands.autocomplete(lang=googletts_autocomplete)
    async def google_text_to_speech(
        self,
        interaction: discord.Interaction,
        text: str,
        slow: bool | None = False,
        lang: str | None = "en",

    ):
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db
            else interaction.locale
        )
        await interaction.response.defer(thinking=True)

        embed = Embed(color=Color.red())

        if not text.strip():
            embed.title = self.bot.internal_translator.T("error.embeds.tts_no_text.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_no_text.description", loc
            )
            return await interaction.followup.send(embed=embed)

        if lang is None:
            lang = "en"
        if slow is None:
            slow = False

        abuffer = BytesIO()
        try:
            tts = gTTS(text, lang=lang, slow=slow)
            tts.write_to_fp(abuffer)

            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(
                embed=embed
            )

        dfile = discord.File(abuffer, filename=f"GoogleTTS_{lang}_{int(time())!s}.mp3")
        embed.color = Color.green()
        embed.title = self.bot.internal_translator.T("command.tts.embeds.default.title", loc)
        embed.description = self.bot.internal_translator.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=self.bot.internal_translator.T(
                "command.tts.embeds.default.footer",
                loc,
                {"tts_type": "Google Translate TTS", "input": text},
            )
        )

        try:
            await interaction.followup.send(embed=embed, file=dfile)
        except Exception as e:
            logger.exception(f"{e}")
            embed.color = Color.red()
            embed.title = self.bot.internal_translator.T("error.embeds.send_error.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.send_error.description", loc, {"e": e}
            )
            await interaction.followup.send(embed=embed)

    @cached(60)
    @ttsgroup.command(name="pocket_tts")
    @app_commands.autocomplete(voice=pockettts_autocomplete)
    async def pocket_text_to_speech(
        self, interaction: Interaction, text: str, voice: str | None = None
    ):
        await interaction.response.defer(thinking=True)
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db
            else interaction.locale
        )

        if voice is None:
            voice = self.tts_manager.pocket_tts_custom_models[0]['path']
        else:
            # Try to resolve voice name to path if not already a path
            for voice_data in self.tts_manager.pocket_tts_custom_models:
                if voice.lower() in voice_data['name'].lower() or voice.lower() in voice_data['friendly_name'].lower():
                    voice = self.bot.root_path + voice_data['path']
                    break

        embed = Embed(color=Color.red())

        if not text.strip():
            embed.title = self.bot.internal_translator.T("error.embeds.tts_no_text.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_no_text.description", loc
            )
            return await interaction.followup.send(embed=embed)

        if not self.tts_manager.pocket_tts_model:
            embed.title = self.bot.internal_translator.T("error.embeds.tts_no_model.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_no_model.description", loc
            )
            return await interaction.followup.send(embed=embed)

        abuffer = BytesIO()
        try:
            voice_state = self.tts_manager.pocket_tts_model.get_state_for_audio_prompt(
                audio_conditioning=voice
            )

            audio = self.tts_manager.pocket_tts_model.generate_audio(voice_state, text)

            write(abuffer, self.tts_manager.pocket_tts_model.sample_rate, audio.numpy())

            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(embed=embed)

        dfile = discord.File(abuffer, filename=f"PocketTTS_{int(time())!s}.wav")
        embed.color = Color.green()
        embed.title = self.bot.internal_translator.T("command.tts.embeds.default.title", loc)
        embed.description = self.bot.internal_translator.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=self.bot.internal_translator.T(
                "command.tts.embeds.default.footer",
                loc,
                {"tts_type": "Pocket TTS", "input": text, "voice": voice},
            )
        )

        try:
            await interaction.followup.send(embed=embed, file=dfile)
        except (HTTPException, NotFound, Forbidden, TypeError, ValueError) as e:
            logger.exception(f"{e}")
            embed.color = Color.red()
            embed.title = self.bot.internal_translator.T("error.embeds.send_error.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.send_error.description", loc, {"e": e}
            )
            await interaction.followup.send(embed=embed)

    @cached(60)
    @ttsgroup.command(name="piper_tts")
    async def piper_text_to_speech(
        self,
        interaction: discord.Interaction,
        text: str,
        volume: float | None = 1.0,
        length_scale: float | None = 1.0,
        noise_scale: float | None = 0.667,
        noise_w_scale: float | None = 0.8,
        normalize: bool | None = False,
    ):
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db
            else interaction.locale
        )
        await interaction.response.defer(thinking=True)

        embed = Embed(color=Color.red())

        if not text.strip():
            embed.title = self.bot.internal_translator.T("error.embeds.tts_no_text.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_no_text.description", loc
            )
            return await interaction.followup.send(embed=embed)

        if not self.tts_manager.piper_voice or not isinstance(self.tts_manager.piper_voice, PiperVoice):
            embed.title = self.bot.internal_translator.T("error.embeds.tts_no_model.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_no_model.description", loc
            )
            return await interaction.followup.send(embed=embed)

        abuffer = BytesIO()
        try:
            syn_config = SynthesisConfig(
                volume=clamp_f(volume or 1.0, 0.1, 5.0),
                length_scale=clamp_f(length_scale or 1.0, 0.25, 4.0),
                noise_scale=clamp_f(noise_scale or 0.667, 0.0, 1.0),
                noise_w_scale=clamp_f(noise_w_scale or 0.8, 0.0, 1.0),
                normalize_audio=normalize or True,
            )

            with wave.open(abuffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.tts_manager.piper_voice.config.sample_rate)

                for raw in await self.bot.loop.run_in_executor(
                    None, lambda: list(self.tts_manager.piper_voice.synthesize(text, syn_config))
                ):
                    wf.writeframes(raw.audio_int16_bytes)
            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(embed=embed)

        dfile = discord.File(abuffer, filename=f"PiperTTS_{int(time())!s}.wav")

        embed.title = self.bot.internal_translator.T("command.tts.embeds.default.title", loc)
        embed.description = self.bot.internal_translator.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=self.bot.internal_translator.T(
                "command.tts.embeds.default.footer",
                loc,
                {"tts_type": "Piper TTS", "input": text},
            )
        )

        try:
            await interaction.followup.send(embed=embed, file=dfile)
        except (HTTPException, NotFound, Forbidden, TypeError, ValueError) as e:
            logger.exception(f"{e}")
            embed.color = Color.red()
            embed.title = self.bot.internal_translator.T("error.embeds.send_error.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.send_error.description", loc, {"e": e}
            )
            await interaction.followup.send(embed=embed)

    @cached(60)
    @ttsgroup.command(name="edge")
    @app_commands.autocomplete(lang=edgetts_autocomplete)
    async def edge_text_to_speech(
        self,
        interaction: discord.Interaction,
        text: str,
        lang: str | None,
        slow: bool | None,
    ):
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db
            else interaction.locale
        )
        await interaction.response.defer(thinking=True)

        embed = Embed(color=Color.red())

        if "edge_tts" not in sys.modules:
            logger.error(
                "edge_tts package is not installed in this project. ignoring..."
            )
            embed.title = self.bot.internal_translator.T(
                "error.embeds.edge_tts_not_installed.title", loc
            )
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_not_installed.description", loc
            )
            return await interaction.followup.send(embed=embed)

        if not text.strip():
            embed.title = self.bot.internal_translator.T("error.embeds.tts_no_text.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_no_text.description", loc
            )
            return await interaction.followup.send(embed=embed)

        if not lang:
            lang = "en-US-AndrewMultilingualNeural"

        if not slow:
            slow = False

        abuffer = BytesIO()
        try:
            communicate = Communicate(text, lang)

            async for chunk in communicate.stream():
                self.bot.received_chunks += 1
                if chunk["type"] == "audio" and "data" in chunk:
                    abuffer.write(chunk["data"])

            abuffer.seek(0)
        except (BlockingIOError, TypeError, ValueError, exceptions.NoAudioReceived, exceptions.UnexpectedResponse,
                exceptions.UnknownResponse, exceptions.WebSocketError) as e:
            logger.exception(f"{e}")
            embed.title = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = self.bot.internal_translator.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(embed=embed)

        dfile = discord.File(abuffer, filename=f"EdgeTTS_{lang}_{int(time())!s}.mp3")

        embed.title = self.bot.internal_translator.T("command.tts.embeds.default.title", loc)
        embed.description = self.bot.internal_translator.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=self.bot.internal_translator.T(
                "command.tts.embeds.default.footer",
                loc,
                {"tts_type": "Edge TTS", "input": text},
            )
        )

        try:
            await interaction.followup.send(embed=embed, file=dfile)
        except (HTTPException, NotFound, Forbidden, TypeError, ValueError) as e:
            logger.exception(f"{e}")
            embed.color = Color.red()
            embed.title = self.bot.internal_translator.T("error.embeds.send_error.title", loc)
            embed.description = self.bot.internal_translator.T(
                "error.embeds.send_error.description", loc, {"e": e}
            )
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TextToSpeechCog(bot))
