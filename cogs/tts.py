from io import BytesIO
import sys
from time import time
from typing import Optional
from aiocache import cached
import discord
import wave
from discord.ext import commands
from discord import Color, Embed, Interaction, app_commands
from edge_tts import Communicate
from gtts import gTTS
from piper import PiperVoice, SynthesisConfig
from bot import PoxBot
from logger import logger
from stuff import clamp_f
from src.translator import translator_instance

voice = PiperVoice.load("./resources/voices/en_US-ryan-high.onnx")

class TextToSpeechCog(commands.Cog):
    def __init__(self,bot):
        self.bot: PoxBot = bot
    
    ttsgroup = app_commands.Group(name=app_commands.locale_str("tts", extras={"key": "command.tts.name"}),description=app_commands.locale_str("Center of TTS.", extras={"key": "command.tts.description"}))
    
    async def googletts_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        suggestions = []
        
        for code, full in self.bot.gtts_cache_langs.items():
            if current.lower() in code.lower() or current.lower() in full.lower():
                suggestions.append(app_commands.Choice(name=full,value=code))
            
            if len(suggestions) >= 20:
                break
        
        return suggestions
    
    @cached(60*2)
    @ttsgroup.command(name=app_commands.locale_str("googletts", extras={"key": "command.tts.google_translate.name"}))
    @app_commands.autocomplete(lang=googletts_autocomplete)
    async def google_text_to_speech(self, interaction: discord.Interaction, text: str, slow: Optional[bool] = False, lang: Optional[str] = "en"):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer(thinking=True)
        
        embed = Embed(color=Color.red())
        
        if not text.strip():
            embed.title = translator_instance.T("error.embed.tts_no_text.title", loc)
            embed.description = translator_instance.T("error.embed.tts_no_text.description", loc)
            return interaction.followup.send(embed=embed)
        
        if lang is None: lang = "en"
        if slow is None: slow = False
        
        abuffer = BytesIO()
        try:
            tts = gTTS(text, lang=lang, slow=slow)
            tts.write_to_fp(abuffer)
            
            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = translator_instance.T("error.embed.tts_generation_error.title", loc)
            embed.description = translator_instance.T("error.embed.tts_generation_error.description", loc, {"e": e})
            return await interaction.followup.send(translator_instance.T("error.custom.tts_generation_error", loc, {"e": e}))
        
        dfile = discord.File(abuffer, filename=f"GoogleTTS_{lang}_{str(int(time()))}.mp3")
        embed.color=Color.green()
        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T("command.tts.embeds.default.description", loc)
        embed.set_footer(text=translator_instance.T("command.tts.embeds.default.footer", loc, {"tts_type": "Google Translate TTS", "input": text}))
        
        try:
            await interaction.followup.send(embed=embed,file=dfile)
        except Exception as e:
            logger.exception(f"{e}")
            embed.color=Color.red()
            embed.title = translator_instance.T("error.embed.send_error.title", loc)
            embed.description = translator_instance.T("error.embed.send_error.description", loc, {"e": e})
            await interaction.followup.send(embed=embed)
    
    @cached(60)
    @ttsgroup.command(name="piper_tts")
    async def piper_text_to_speech(
        self,
        interaction: discord.Interaction,
        text: str,
        volume: Optional[float] = 1.0,
        length_scale: Optional[float] = 1.0,
        noise_scale: Optional[float] = 0.667,
        noise_w_scale: Optional[float] = 0.8,
        normalize: Optional[bool] = False,
    ):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer(thinking=True)
        
        embed = Embed(color=Color.red())
        
        if not text.strip():
            embed.title = translator_instance.T("error.embed.tts_no_text.title", loc)
            embed.description = translator_instance.T("error.embed.tts_no_text.description", loc)
            return interaction.followup.send(embed=embed)
        
        abuffer = BytesIO()
        try:
            syn_config = SynthesisConfig(
                volume=clamp_f(volume or 1.0, 0.1, 5.0),
                length_scale=clamp_f(length_scale or 1.0, 0.25, 4.0),
                noise_scale=clamp_f(noise_scale or 0.667, 0.0, 1.0),
                noise_w_scale=clamp_f(noise_w_scale or 0.8, 0.0, 1.0),
                normalize_audio=normalize or True,
            )

            with wave.open(abuffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(voice.config.sample_rate)
                
                for raw in voice.synthesize(text, syn_config):
                    wf.writeframes(raw.audio_int16_bytes)
            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = translator_instance.T("error.embed.tts_generation_error.title", loc)
            embed.description = translator_instance.T("error.embed.tts_generation_error.description", loc, {"e": e})
            return await interaction.followup.send(translator_instance.T("error.custom.tts_generation_error", loc, {"e": e}))
        
        dfile = discord.File(abuffer, filename=f"PiperTTS_{str(int(time()))}.wav")
        
        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T("command.tts.embeds.default.description", loc)
        embed.set_footer(text=translator_instance.T("command.tts.embeds.default.footer", loc, {"tts_type": "Piper TTS", "input": text}))
        
        try:
            await interaction.followup.send(embed=embed, file=dfile)
        except Exception as e:
            logger.exception(f"{e}")
            embed.color=Color.red()
            embed.title = translator_instance.T("error.embed.send_error.title", loc)
            embed.description = translator_instance.T("error.embed.send_error.description", loc, {"e": e})
            await interaction.followup.send(embed=embed)
    
    @cached(60)
    @ttsgroup.command(name="edge")
    async def edge_text_to_speech(self, interaction: discord.Interaction, text: str, lang: Optional[str], slow: Optional[bool]):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        
        embed = Embed(color=Color.red())
        
        if not "edge_tts" in sys.modules:
            logger.error("edge_tts package is not installed in this project. ignoring...")
            embed.title = translator_instance.T("error.embed.edge_tts_not_installed.title", loc)
            embed.description = translator_instance.T("error.embed.tts_not_installed.description", loc)
            return interaction.followup.send(embed=embed)
        
        if not text.strip():
            embed.title = translator_instance.T("error.embed.tts_no_text.title", loc)
            embed.description = translator_instance.T("error.embed.tts_no_text.description", loc)
            return interaction.followup.send(embed=embed)
        
        if not lang:
            lang = "en-US-AndrewMultilingualNeural"
        
        if not slow:
            slow = False
        
        
        await interaction.response.defer(thinking=True)
        
        abuffer = BytesIO()
        try:
            communicate = Communicate(text, lang)
            
            async for chunk in communicate.stream():
                self.bot.received_chunks += 1
                if chunk["type"] == "audio" and "data" in chunk:
                    abuffer.write(chunk["data"])
            
            abuffer.seek(0)
        except Exception as e:
            logger.exception(f"{e}")
            embed.title = translator_instance.T("error.embed.tts_generation_error.title", loc)
            embed.description = translator_instance.T("error.embed.tts_generation_error.description", loc, {"e": e})
            return await interaction.followup.send(translator_instance.T("error.custom.tts_generation_error", loc, {"e": e}))
        
        dfile = discord.File(abuffer, filename=f"EdgeTTS_{lang}_{str(int(time()))}.mp3")
        
        embed.title = translator_instance.T("command.tts.embeds.default.title", loc)
        embed.description = translator_instance.T("command.tts.embeds.default.description", loc)
        embed.set_footer(text=translator_instance.T("command.tts.embeds.default.footer", loc, {"tts_type": "Edge TTS", "input": text}))
        
        try:
            await interaction.followup.send(embed=embed, file=dfile)
        except Exception as e:
            logger.exception(f"{e}")
            embed.color=Color.red()
            embed.title = translator_instance.T("error.embed.send_error.title", loc)
            embed.description = translator_instance.T("error.embed.send_error.description", loc, {"e": e})
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TextToSpeechCog(bot))