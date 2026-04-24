import json
import os
import pathlib
from typing import Callable, Optional
import discord
from discord import app_commands

from logger import logger

class Translator:
    def __init__(self):
        self.translations = {}
        self.base_path = pathlib.Path(__file__).parent.parent / "locales"
        self.refresh()

    def refresh(self):
        temp_translations = {}
        
        try:
            for file in self.base_path.glob("*.json"):
                locale_name = file.stem
                with open(file, 'r', encoding='utf-8') as f:
                    temp_translations[locale_name] = json.load(f)
            
            self.translations = temp_translations
            logger.info(f"Locale data refreshed successfully: {list(self.translations.keys())}")
            return True
        except (json.JSONDecodeError, OSError) as e:
            logger.exception(f"Failed to refresh translations: {e}")
            logger.warning("Reverting locale data.")
            return False

    def translate(self, key: str, locale: discord.Locale, **kwargs) -> str:
        lang = str(locale)

        lang_data = self.translations.get(lang, self.translations.get("en-US", {}))
        text = lang_data.get(key, self.translations.get("en-US", {}).get(key, key))

        try:
            return text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing placeholder {e} for key '{key}' in '{lang}'")
            return text

translator_instance = Translator()

class CustomDiscordTranslator(app_commands.Translator):
    def __init__(self, internal_translator):
        self.internal = internal_translator
    
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> Optional[str]:
        translated = self.internal.translate(string.message, locale)
        
        if translated == string.message:
            return None
        
        return translated