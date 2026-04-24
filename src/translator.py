import i18n
import os
from typing import Optional
import discord
from discord import Locale, app_commands
from logger import logger

class I18nTranslator:
    def __init__(self, locales_path: str = "locales"):
        self.locales_path = os.path.abspath(locales_path)
        
        i18n.load_path.append(self.locales_path)
        i18n.set('file_format', 'json')
        i18n.set('filename_format', '{locale}.{format}')
        i18n.set('fallback', 'en')
        
        i18n.set('on_missing_translation', 'return_key_on_missing_translation')
    
    def _normalize_locale(self, locale: str) -> str:
        return str(locale)
    
    def translate_string(self, text: str, locale: str, **kwargs) -> str:
        lang = self._normalize_locale(locale)
        try:
            return i18n.t(text, locale=lang, **kwargs)
        except Exception as e:
            logger.error(f"Translation error for '{text}' in {lang}: {e}")
            return text
    
    def translate_plural(self, key: str, count: int, locale: str, **kwargs) -> str:
        return i18n.t(key, count=count, locale=locale, **kwargs)
    
    def T(self, text: str, locale: str, **kwargs) -> str:
        return self.translate_string(text, locale, **kwargs)

class DiscordI18nTranslator(app_commands.Translator):
    def __init__(self, internal_translator: I18nTranslator):
        self.internal = internal_translator
    
    async def load(self):
        pass
    
    async def translate(self, string: app_commands.locale_str, locale: Locale, context: app_commands.TranslationContext) -> Optional[str]:
        key = string.message if string.message is not None else str(string)
        
        translated = self.internal.translate_string(key, str(locale))
        
        if translated == key:
            return None
        
        return translated

translator_instance = I18nTranslator(locales_path="locales")
discord_translator = DiscordI18nTranslator(translator_instance)