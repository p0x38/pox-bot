import os
from typing import Any, overload

from discord import Interaction, Locale, app_commands

from .processor import I18nProcessor


class I18nTranslator:
    def __init__(self, processor: I18nProcessor):
        self.processor = processor
        self.locales_path = os.path.abspath(processor.locales_path)

    @property
    def available_files(self) -> set[str]:
        return self.processor.available_files

    def load_metadata(self, language: str) -> dict[str, Any]:
        return self.processor.load_metadata(language)

    async def preload_all(self):
        await self.processor.preload_all()

    def _normalize_locale(self, locale: str | Locale) -> str:
        return self.processor._normalize_locale(str(locale))

    def get_best_locale(self, user_locale: str | None, interaction_locale: Locale) -> str:
        if user_locale and user_locale in self.processor.available_files:
            return user_locale

        return self._normalize_locale(interaction_locale)

    def get_user_locale(self, interaction: Interaction, user_settings: Any = None) -> str:
        if user_settings and hasattr(user_settings, 'locale') and user_settings.locale:
            return self._normalize_locale(user_settings.locale)

        return self._normalize_locale(interaction.locale)

    def translate_string(self, text: str, locale: str | Locale, **kwargs) -> str:
        return self.processor.translate_string(text, str(locale), **kwargs)

    def translate_plural(self, key: str, count: int, locale: str, **kwargs) -> str:
        return self.T(key, locale, count=count, **kwargs)

    @overload
    def T(self, text: str,
          locale: None = None, placeholders: dict[str, Any] | None = None, **kwargs) -> app_commands.locale_str: ...

    @overload
    def T(self, text: str, locale: str | Locale, placeholders: dict[str, Any] | None = None, **kwargs) -> str: ...

    def T(self, text: str, locale: str | Locale | None = None,
          placeholders: dict[str, Any] | None = None, **kwargs) -> str | app_commands.locale_str:
        if locale is None:
            return text

        merged_kwargs = {}
        if placeholders:
            merged_kwargs.update(placeholders)
        if kwargs:
            merged_kwargs.update(kwargs)

        return self.translate_string(text, locale, **merged_kwargs)

    def translate_map(self, data_dict: dict[str, Any], locale: str | Locale, prefix: str = "label") -> dict:
        return {
            self.T(f"{prefix}.{k}", locale): (v if v is not None else self.T("text.unknown", locale))
            for k, v in data_dict.items()
        }


class DiscordI18nTranslator(app_commands.Translator):
    def __init__(self, internal: I18nTranslator):
        self.internal = internal

    async def load(self):
        await self.internal.preload_all()

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: Locale,
        context: app_commands.TranslationContext
    ) -> str | None:
        key = str(string)

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
