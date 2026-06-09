import sys
import wave
from datetime import datetime, timedelta
from enum import StrEnum
from io import BytesIO
from time import time
from typing import Any

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
from edge_tts import Communicate, exceptions, list_voices
from gtts import gTTS, gTTSError
from piper import PiperVoice, SynthesisConfig
from pocket_tts import TTSModel
from pytz import UTC
from scipy.io.wavfile import write

from bot import PoxBot
from logger import logger
from src.translator import translator_instance
from stuff import clamp_f


class TTSEngineType(StrEnum):
    GOOGLE_TTS = "google-tts"
    PIPER_TTS = "piper-tts"
    ESPEAK_TTS = "espeak-tts"
    POCKET_TTS = "pocket-tts"
    EDGE_TTS = "edge-tts"

class SpeechGenerationError(Exception):
    pass

class TextToSpeechCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.pocket_tts_model = None
        self.pocket_tts_custom_models = [
            {
                "name": "sam",
                "friendly_name": "Microsoft Sam",
                "path": "/resources/voices/pocket-tts/sam.safetensors",
            },
            {
                "name": "zira",
                "friendly_name": "Microsoft Zira",
                "path": "/resources/voices/pocket-tts/zira.safetensors",
            },
            {
                "name": "sam-v2",
                "friendly_name": "Microsoft Sam V2",
                "path": "/resources/voices/pocket-tts/sam-v2.safetensors",
            },
            {
                "name": "zira-v2",
                "friendly_name": "Microsoft Zira V2",
                "path": "/resources/voices/pocket-tts/zira-v2.safetensors",
            },
            {
                "name": "carl",
                "friendly_name": "High pitched TruVoice Adult Male 1",
                "path": "/resources/voices/pocket-tts/carl.safetensors",
            },
            {
                "name": "mary",
                "friendly_name": "Microsoft Mary",
                "path": "/resources/voices/pocket-tts/mary.safetensors",
            },
            {
                "name": "mike",
                "friendly_name": "Microsoft Mike",
                "path": "/resources/voices/pocket-tts/mike.safetensors",
            },
            {
                "name": "truvoice-af1",
                "friendly_name": "TruVoice Adult Female 1",
                "path": "/resources/voices/pocket-tts/truvoice-af1.safetensors",
            },
            {
                "name": "truvoice-am1",
                "friendly_name": "TruVoice Adult Male 1",
                "path": "/resources/voices/pocket-tts/truvoice-am1.safetensors",
            },
            {
                "name": "missile",
                "friendly_name": "Missile knows where it is",
                "path": "/resources/voices/pocket-tts/missile.safetensors",
            },
            {
                "name": "sweep",
                "friendly_name": "Sine Sweep",
                "path": "/resources/voices/pocket-tts/sweep.safetensors",
            },
            {
                "name": "triangle-sweep",
                "friendly_name": "Triangle Sweep",
                "path": "/resources/voices/pocket-tts/triangle-sweep.safetensors",
            },
            {
                "name": "me",
                "friendly_name": "Me",
                "path": "/resources/voices/pocket-tts/me.safetensors",
            },
            {
                "name": "triangle",
                "friendly_name": "Triangle Wave",
                "path": "/resources/voices/pocket-tts/triangle.safetensors",
            },
            {
                "name": "sine",
                "friendly_name": "Sine Wave",
                "path": "/resources/voices/pocket-tts/sine.safetensors",
            },
            {
                "name": "dtmf",
                "friendly_name": "DTMF Tone",
                "path": "/resources/voices/pocket-tts/dtmf.safetensors",
            },
            {
                "name": "vc1",
                "friendly_name": "Voice 1",
                "path": "/resources/voices/pocket-tts/vc1.safetensors",
            },
            {
                "name": "vc2",
                "friendly_name": "Voice 2",
                "path": "/resources/voices/pocket-tts/vc2.safetensors",
            },
            {
                "name": "vc3",
                "friendly_name": "Voice 3",
                "path": "/resources/voices/pocket-tts/vc3.safetensors",
            },
            {
                "name": "vc4",
                "friendly_name": "Voice 4",
                "path": "/resources/voices/pocket-tts/vc4.safetensors",
            },
            {
                "name": "vc5",
                "friendly_name": "Voice 5",
                "path": "/resources/voices/pocket-tts/vc5.safetensors",
            },
            {
                "name": "vc5-lq",
                "friendly_name": "Voice 5 Low Quality",
                "path": "/resources/voices/pocket-tts/vc5-lq.safetensors",
            },
            {
                "name": "vc6",
                "friendly_name": "Voice 6",
                "path": "/resources/voices/pocket-tts/vc6.safetensors",
            },
            {
                "name": "gtts",
                "friendly_name": "gTTS",
                "path": "/resources/voices/pocket-tts/gtts.safetensors",
            },
        ]
        self.pocket_tts_predefined_models = [
            "alba",
            "giovanni",
            "lola",
            "juergen",
            "rafael",
            "estelle",
            "anna",
            "azelma",
            "bill_boerst",
            "caro_davy",
            "charles",
            "cosette",
            "eponine",
            "eve",
            "fantine",
            "george",
            "jane",
            "jean",
            "javert",
            "marius",
            "mary",
            "michael",
            "paul",
            "peter_yearsley",
            "stuart_bell",
            "vera",
        ]
        self.edge_tts_voices = {}
        self.piper_voice: PiperVoice | None = None

    async def cog_load(self):
        self.pocket_tts_model = TTSModel.load_model()
        self.edge_tts_voices = await list_voices()
        self.piper_voice = PiperVoice.load("./resources/voices/en_US-ryan-high.onnx")
    
    async def generate_speech(self, data: dict[str, Any]):
        if not data.get("input"):
            raise ValueError("Input text is None")
        
        if isinstance(data["input"], str):
            if not data["input"].strip():
                raise ValueError("Input text cannot be empty")
            if len(data["input"]) > 1500:
                raise RuntimeError("Input too long")
        
        input_text = data["input"]
        abuffer = BytesIO()
        start_time = datetime.now(UTC)
        
        match (data["engine"]):
            case TTSEngineType.GOOGLE_TTS:
                try:
                    voice_language = data.get("voice") or "en"
                    slow_mode = data.get("slow_mode") or False
                    
                    generated = gTTS(input_text, lang=voice_language, slow=slow_mode)
                    generated.write_to_fp(abuffer)
                    
                    duration = datetime.now(UTC) - start_time
                    
                    abuffer.seek(0)
                    
                    return {"output": abuffer, "duration": duration, "type": "mp3"}
                except gTTSError as e:
                    raise SpeechGenerationError() from e
            case TTSEngineType.PIPER_TTS:
                if not self.piper_voice:
                    raise RuntimeError("Voice model isn't loaded yet")
                
                speech_volume = data.get("volume") or 1.0
                length_factor = data.get("length_scale") or 1.0
                noise_factor = data.get("noise_scale") or 0.667
                noise_w_factor = data.get("noise_w_scale") or 0.8
                normalize_audio = data.get("normalize") or True
                
                synthesis_config = SynthesisConfig(
                    length_scale=length_factor,
                    noise_scale=noise_factor,
                    noise_w_scale=noise_w_factor,
                    normalize_audio=normalize_audio,
                    volume=speech_volume
                )
                
                with wave.open(abuffer, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.piper_voice.config.sample_rate)
                    
                    for raw in await self.bot.loop.run_in_executor(
                        None, lambda: list(self.piper_voice.synthesize(input_text, synthesis_config)) if self.piper_voice else []
                    ):
                        wf.writeframes(raw.audio_int16_bytes)
                
                duration = datetime.now(UTC) - start_time
                
                abuffer.seek(0)
                
                return {"output": abuffer, "duration": duration, "type": "wav"}
            case TTSEngineType.POCKET_TTS:
                speech_voice = data.get("voice")
                
                if not speech_voice:
                    speech_voice = self.bot.root_path + self.pocket_tts_custom_models[0]['path']
                
                for voice_data in self.pocket_tts_custom_models:
                    if speech_voice.lower() in voice_data['name'].lower() or speech_voice.lower() in voice_data['friendly_name'].lower():
                        speech_voice = self.bot.root_path + voice_data['path']
                        break
                
                if not self.pocket_tts_model:
                    raise RuntimeError("Voice model isn't loaded yet")
                
                voice_state = self.pocket_tts_model.get_state_for_audio_prompt(
                    audio_conditioning=speech_voice
                )
                
                generated = self.pocket_tts_model.generate_audio(voice_state, input_text)
                
                write(abuffer, self.pocket_tts_model.sample_rate, generated.numpy())
                
                duration = datetime.now(UTC) - start_time
                
                abuffer.seek(0)
                
                return {"output": abuffer, "duration": duration, "type": "wav"}
            case TTSEngineType.EDGE_TTS:
                speech_voice = data.get("voice")
                
                if not speech_voice:
                    speech_voice = "en-US-AndrewMultilingualNeural"
                    
                communicate = Communicate(input_text, speech_voice)
                chunks = 0
                
                async for chunk in communicate.stream():
                    chunks += 1
                    if chunk["type"] == "audio" and "data" in chunk:
                        abuffer.write(chunk["data"])
                
                duration = datetime.now(UTC) - start_time
                
                abuffer.seek(0)
                
                return {"output": abuffer, "duration": duration, "chunk_count": chunks, "type": "mp3"}
            case _:
                raise RuntimeError("Unknown engine type")

    ttsgroup = app_commands.Group(
        name="tts",
        description=app_commands.locale_str("command.tts.description"),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    async def googletts_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        suggestions = []

        for code, full in self.bot.gtts_cache_langs.items():
            if current.lower() in code.lower() or current.lower() in full.lower():
                suggestions.append(app_commands.Choice(name=full, value=code))

            if len(suggestions) >= 20:
                break

        return suggestions

    async def edgetts_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        suggestions = []

        for voice in self.edge_tts_voices:
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
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        suggestions = []

        for voice in self.pocket_tts_predefined_models:
            if current.lower() in voice.lower():
                suggestions.append(
                    app_commands.Choice(name=f"{voice} (Built-in)", value=voice)
                )

            if len(suggestions) >= 20:
                break

        for voice_data in self.pocket_tts_custom_models:
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
            result = await self.generate_speech(data)
            
            if not result:
                raise RuntimeError("Result returned None")
            
            if not result.get("output"):
                raise RuntimeError("Output returned None")
            
            filename = f"{str(engine).replace(" ", "")}_{int(time())!s}." + result["type"]
            
            file = File(result["output"], filename)
            
            embed.color = Color.green()
            embed.set_footer(text=f"Generated by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            
            duration = result.get("duration")
            
            embed.add_field(name="Input Text", value=input)
            embed.add_field(name="TTS Engine", value=str(engine))
            embed.add_field(name="Voice", value=voice)
            
            if isinstance(duration, timedelta):
                embed.add_field(name="Took generation", value=f"{duration.total_seconds():.3f}")
            
            if result.get("chunk_count"):
                embed.add_field(name="Chunk count", value=result["chunk_count"])
                
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
            embed.title = translator_instance.T("error.embeds.tts_no_text.title", loc)
            embed.description = translator_instance.T(
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
            embed.title = translator_instance.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = translator_instance.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(
                embed=embed
            )

        dfile = discord.File(abuffer, filename=f"GoogleTTS_{lang}_{int(time())!s}.mp3")
        embed.color = Color.green()
        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=translator_instance.T(
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
            embed.title = translator_instance.T("error.embeds.send_error.title", loc)
            embed.description = translator_instance.T(
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
            voice = self.pocket_tts_custom_models[0]['path']
        else:
            # Try to resolve voice name to path if not already a path
            for voice_data in self.pocket_tts_custom_models:
                if voice.lower() in voice_data['name'].lower() or voice.lower() in voice_data['friendly_name'].lower():
                    voice = self.bot.root_path + voice_data['path']
                    break

        embed = Embed(color=Color.red())

        if not text.strip():
            embed.title = translator_instance.T("error.embeds.tts_no_text.title", loc)
            embed.description = translator_instance.T(
                "error.embeds.tts_no_text.description", loc
            )
            return await interaction.followup.send(embed=embed)
        
        if not self.pocket_tts_model:
            embed.title = translator_instance.T("error.embeds.tts_no_model.title", loc)
            embed.description = translator_instance.T(
                "error.embeds.tts_no_model.description", loc
            )
            return await interaction.followup.send(embed=embed)

        abuffer = BytesIO()
        try:
            voice_state = self.pocket_tts_model.get_state_for_audio_prompt(
                audio_conditioning=voice
            )
 
            audio = self.pocket_tts_model.generate_audio(voice_state, text)

            write(abuffer, self.pocket_tts_model.sample_rate, audio.numpy())

            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = translator_instance.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = translator_instance.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(embed=embed)

        dfile = discord.File(abuffer, filename=f"PocketTTS_{int(time())!s}.wav")
        embed.color = Color.green()
        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=translator_instance.T(
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
            embed.title = translator_instance.T("error.embeds.send_error.title", loc)
            embed.description = translator_instance.T(
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
            embed.title = translator_instance.T("error.embeds.tts_no_text.title", loc)
            embed.description = translator_instance.T(
                "error.embeds.tts_no_text.description", loc
            )
            return await interaction.followup.send(embed=embed)
        
        if not self.piper_voice or not isinstance(self.piper_voice, PiperVoice):
            embed.title = translator_instance.T("error.embeds.tts_no_model.title", loc)
            embed.description = translator_instance.T(
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
                wf.setframerate(self.piper_voice.config.sample_rate)

                for raw in await self.bot.loop.run_in_executor(
                    None, lambda: list(self.piper_voice.synthesize(text, syn_config))
                ):
                    wf.writeframes(raw.audio_int16_bytes)
            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = translator_instance.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = translator_instance.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(embed=embed)

        dfile = discord.File(abuffer, filename=f"PiperTTS_{int(time())!s}.wav")

        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=translator_instance.T(
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
            embed.title = translator_instance.T("error.embeds.send_error.title", loc)
            embed.description = translator_instance.T(
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

        if not "edge_tts" in sys.modules:
            logger.error(
                "edge_tts package is not installed in this project. ignoring..."
            )
            embed.title = translator_instance.T(
                "error.embeds.edge_tts_not_installed.title", loc
            )
            embed.description = translator_instance.T(
                "error.embeds.tts_not_installed.description", loc
            )
            return await interaction.followup.send(embed=embed)

        if not text.strip():
            embed.title = translator_instance.T("error.embeds.tts_no_text.title", loc)
            embed.description = translator_instance.T(
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
        except (BlockingIOError, TypeError, ValueError, exceptions.NoAudioReceived, exceptions.UnexpectedResponse, exceptions.UnknownResponse, exceptions.WebSocketError) as e:
            logger.exception(f"{e}")
            embed.title = translator_instance.T(
                "error.embeds.tts_generation_error.title", loc
            )
            embed.description = translator_instance.T(
                "error.embeds.tts_generation_error.description", loc, {"e": e}
            )
            return await interaction.followup.send(embed=embed)

        dfile = discord.File(abuffer, filename=f"EdgeTTS_{lang}_{int(time())!s}.mp3")

        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T(
            "command.tts.embeds.default.description", loc
        )
        embed.set_footer(
            text=translator_instance.T(
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
            embed.title = translator_instance.T("error.embeds.send_error.title", loc)
            embed.description = translator_instance.T(
                "error.embeds.send_error.description", loc, {"e": e}
            )
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TextToSpeechCog(bot))
