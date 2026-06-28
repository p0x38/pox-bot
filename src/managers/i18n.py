from pathlib import Path

import orjson
from discord import Locale, SelectOption

from ..i18n_processor.processor import I18nProcessor, TranslatorOptions
from ..i18n_processor.translator import DiscordI18nTranslator, I18nTranslator
from ..logger_factory.logger import setup_logger


class I18nManager:
    def __init__(self, locales_path: str | Path):
        self.logger = setup_logger(__name__)
        self.locales_path = Path(locales_path)

        self.processor = I18nProcessor(TranslatorOptions(base_path=str(self.locales_path)))
        self.internal = I18nTranslator(self.processor)
        self.discord = DiscordI18nTranslator(self.internal)

        self.lang_info = {}
        self._load_lang_info()

        self.logger.info("Initialized the manager.")

    async def initialize(self):
        await self.discord.load()

    def _load_lang_info(self):
        lang_file = self.locales_path / "available_languages.json"
        try:
            if lang_file.exists():
                with lang_file.open(encoding="utf-8") as f:
                    data = orjson.loads(f.read())
                    self.lang_info = {item["code"]: item for item in data}
        except Exception as e:
            self.logger.error(f"Failed to load available_languages.json: {e}")

    def T(self, key: str, locale: str | Locale, placeholders: dict | None = None, **kwargs) -> str:
        if locale is None:
            return key

        merged_kwargs = {}
        if placeholders:
            merged_kwargs.update(placeholders)

        if kwargs:
            merged_kwargs.update(kwargs)

        return self.internal.translate_string(key, str(locale), **merged_kwargs)

    def get_available_language_codes(self) -> list[str]:
        return list(self.lang_info.keys())

    def get_select_options(self, current_locale: str) -> list[SelectOption]:
        options = []
        for code, info in self.lang_info.items():
            options.append(SelectOption(
                label=info.get('display', code.upper()),
                value=code,
                emoji=info.get('emoji', '🌐'),
                default=(code == current_locale)
            ))
        return options
