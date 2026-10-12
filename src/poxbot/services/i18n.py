from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson
from discord import Locale, SelectOption

from ..features.i18n.processor import I18nProcessor, TranslatorOptions
from ..features.i18n.translator import DiscordI18nTranslator, I18nTranslator
from ..infrastructure.logger import get_logger

if TYPE_CHECKING:
    from ..core.resources import ResourceManager as ResourcePathManager


class I18nManager:
    def __init__(
        self,
        locales_path: str | Path,
        *,
        resource_manager: ResourcePathManager | None = None,
    ):
        self.logger = get_logger(__name__, prefix='I18nManager')
        self.locales_path = Path(locales_path)
        self.resource_manager = resource_manager

        self.processor = I18nProcessor(
            TranslatorOptions(
                base_path=self.locales_path,
                resource_manager=resource_manager,
            ),
        )
        self.internal = I18nTranslator(self.processor)
        self.discord = DiscordI18nTranslator(self.internal)

        self.lang_info: dict[str, dict[str, Any]] = {}
        self._load_lang_info()

        self.logger.info('Initialized the manager.')

    def _load_lang_info(self) -> None:
        try:
            if self.resource_manager is not None:
                address = "assets:locales/available_languages.json"
                if not self.resource_manager.exists(address):
                    return
                content = self.resource_manager.read_bytes(address)
                data = orjson.loads(content)
            else:
                lang_file = self.locales_path / 'available_languages.json'
                if not lang_file.is_file():
                    return
                data = orjson.loads(lang_file.read_bytes())

            if isinstance(data, list):
                self.lang_info = {
                    item['code']: item
                    for item in data
                    if isinstance(item, dict) and isinstance(item.get('code'), str)
                }
            else:
                self.logger.warning(
                    'available_languages.json must contain a JSON array.',
                )
        except Exception:
            self.logger.exception('Failed to load available_languages.json')

    def T(
        self,
        key: str,
        locale: str | Locale,
        placeholders: dict | None = None,
        **kwargs,
    ) -> str:
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
        return [
            SelectOption(
                label=info.get('display', code.upper()),
                value=code,
                emoji=info.get('emoji', '🌐'),
                default=(code == current_locale),
            )
            for code, info in self.lang_info.items()
        ]
