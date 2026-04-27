import i18n
import os
import orjson
import aiofiles
import asyncio
from typing import Any, Dict, List, Optional, Union, overload, Set
from discord import Interaction, Locale, SelectOption, app_commands

from logger import logger

class TranslationManager:
    def __init__(self, locales_path: str = "locales"):
        self.locales_path = locales_path
        try:
            with open("resources/available_languages.json", "r", encoding="utf-8") as f:
                data = orjson.loads(f.read())
                # Convert the list to a dict for easy lookup: {"en": {"display": "English", ...}}
                self.lang_info = {item["code"]: item for item in data}
        except Exception as e:
            logger.error(f"Failed to load available_languages.json: {e}")
            self.lang_info = {}
    
    def get_available_language_codes(self) -> List[str]:
        return list(self.lang_info.keys())
    
    def get_select_options(self, current_locale: str) -> List[SelectOption]:
        options = []
        for code, info in self.lang_info.items():
            info = self.lang_info.get(code, {"name": code.upper(), "emoji": "🌐"})
            options.append(SelectOption(
                label=info.get('display', code.upper()),
                value=code,
                emoji=info('emoji', '🌐'),
                default=(code == current_locale)
            ))
        return options

translation_manager = TranslationManager()

class I18nTranslator:
    def __init__(self, locales_path: str = "resources/locales"):
        self.locales_path = os.path.abspath(locales_path)
        self.available_files: Set[str] = set()
        self._sync_cache_locales()
        
        self.missing_keys_buffer: Dict[str, Set[str]] = {}
        self.batch_delay = 5.0
        self.batch_task: Optional[asyncio.Task] = None
        
        i18n.load_path.append(self.locales_path)
        i18n.set('file_format', 'json')
        i18n.set('filename_format', '{namespace}.{format}')
        i18n.set('fallback', 'en')
        i18n.set('skip_locale_root_data', True)
        i18n.set('use_locale_dirs', True)
        
        self.MISSING = object()
        
        def missing_handler(key, locale, **kwargs):
            return self.MISSING
        
        i18n.set('on_missing_translation', missing_handler)
    
    async def _flush_missing_keys(self):
        await asyncio.sleep(self.batch_delay)
        
        if self.missing_keys_buffer:
            report = ["\n----  Translation Missing Report ----"]
            for key, langs in self.missing_keys_buffer.items():
                report.append(f"\t* Key: '{key}' | Missing in: {', '.join(langs)}")
            report.append("-------------------------------------")
            
            logger.warning("\n".join(report))
            self.missing_keys_buffer.clear()
        
        self.batch_task = None
    
    def _sync_cache_locales(self):
        if os.path.exists(self.locales_path):
            self.available_files = {
                name for name in os.listdir(self.locales_path)
                if os.path.isdir(os.path.join(self.locales_path, name))
            }
    
    def _orjson_loader(self, file_path: str) -> dict:
        with open(file_path, "rb") as f:
            return orjson.loads(f.read())
    
    async def preload_all(self):
        tasks = []
        
        for locale in self.available_files:
            tasks.append(self._load_locale_async(locale))
        await asyncio.gather(*tasks)
        logger.info(f"Preloaded {len(self.available_files)} languages.")
    
    async def _load_locale_async(self, locale: str):
        file_path = os.path.join(self.locales_path, f"{locale}.json")
        try:
            async with aiofiles.open(file_path, mode='rb') as f:
                content = await f.read()
                data = orjson.loads(content)
                
                i18n.translations.add(locale, data)
        except Exception as e:
            logger.error(f"Failed to async load {locale}: {e}")

    def _normalize_locale(self, locale: Union[str, Locale]) -> str:
        if not locale:
            return "en"
        
        if isinstance(locale, list):
            locale = locale[0]
        
        locale = str(locale).replace("_", "-").lower()

        base = locale.split("-")[0]

        if base not in self.available_files:
            return "en"
        
        return base
    
    def get_best_locale(self, user_locale: Optional[str], interaction_locale: Locale) -> str:
        if user_locale:
            if user_locale in self.available_files:
                return user_locale
        
        return self._normalize_locale(interaction_locale)
    
    def get_user_locale(self, interaction: Interaction, user_settings: Optional[Any] = None) -> str:
        if user_settings and hasattr(user_settings, 'locale') and user_settings.locale:
            return self._normalize_locale(user_settings.locale)
        return self._normalize_locale(interaction.locale)
    
    def translate_string(self, text: str, locale: Union[str, Locale], **kwargs) -> str:
        lang = self._normalize_locale(locale)
        
        translated = i18n.t(text, locale=lang, **kwargs)
        
        if translated is self.MISSING:
            if text not in self.missing_keys_buffer:
                self.missing_keys_buffer[text] = set()
            self.missing_keys_buffer[text].add(lang)
            
            if self.batch_task is None:
                try:
                    loop = asyncio.get_running_loop()
                    self.batch_task = loop.create_task(self._flush_missing_keys())
                    self.batch_task.add_done_callback(lambda t: setattr(self, "batch_task", None))
                except RuntimeError:
                    pass
            return text
        
        return translated
    
    def translate_plural(self, key: str, count: int, locale: str, **kwargs) -> str:
        return self.T(key, locale, count=count, **kwargs)
    
    @overload
    def T(self, text: str, locale: None = None, placeholders: Optional[dict[str, Any]] = None, **kwargs) -> app_commands.locale_str: ...
    
    @overload
    def T(self, text: str, locale: Union[str, Locale], placeholders: Optional[dict[str, Any]] = None, **kwargs) -> str: ...
    
    def T(self, text: str, locale: Optional[Union[str, Locale]] = None, placeholders: Optional[dict[str, Any]] = None, **kwargs) -> Union[str, app_commands.locale_str]:
        if locale is None:
            return text
        
        merged_kwargs = {}
        
        if placeholders:
            merged_kwargs.update(placeholders)
        
        if kwargs:
            merged_kwargs.update(kwargs)
        
        return self.translate_string(text, locale, **merged_kwargs)
    
    def translate_map(self, data_dict: dict[str, Any], locale: str, prefix: str = "label") -> dict:
        """
        Translates all keys in a dictionary based on a specific i18n prefix.
        """
        return {
            self.T(f"{prefix}.{k}", locale): (v if v is not None else self.T("text.unknown", locale))
            for k, v in data_dict.items()
        }

class DiscordI18nTranslator(app_commands.Translator):
    def __init__(self, internal_translator: I18nTranslator):
        self.internal = internal_translator
    
    async def load(self):
        await self.internal.preload_all()
    
    async def translate(self, string: app_commands.locale_str, locale: Locale, context: app_commands.TranslationContext) -> Optional[str]:
        key = string.message if string.message is not None else str(string)
        
        is_name = context.location in [
            app_commands.TranslationContextLocation.command_name,
            app_commands.TranslationContextLocation.group_name,
            app_commands.TranslationContextLocation.parameter_name
        ]
        
        if is_name and "." not in key:
            return None
        
        translated = self.internal.translate_string(key, str(locale))
        
        if translated == key:
            return None
        
        return translated

translator_instance = I18nTranslator(locales_path="locales")
discord_translator = DiscordI18nTranslator(translator_instance)