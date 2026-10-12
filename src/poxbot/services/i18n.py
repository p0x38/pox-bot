from pathlib import Path
from typing import Any

import orjson
from discord import Locale, SelectOption

from ..features.i18n.processor import I18nProcessor, TranslatorOptions
from ..features.i18n.translator import DiscordI18nTranslator, I18nTranslator
from ..infrastructure.logger import get_logger


class I18nManager:
    def __init__(self, locales_path: str | Path):
        self.logger = get_logger(__name__, prefix='I18nManager')
        self.locales_path = Path(locales_path)

        self.processor = I18nProcessor(
            TranslatorOptions(base_path=str(self.locales_path)),
        )
        self.internal = I18nTranslator(self.processor)
        self.discord = DiscordI18nTranslator(self.internal)

        self.lang_info: dict[str, dict[str, Any]] = {}
        self._load_lang_info()

        self.logger.info('Initialized the manager.')

    def _load_lang_info(self) -> None:
        catalog = self.processor.load_metadata_catalog()
        languages = catalog.get('languages', []) if isinstance(catalog, dict) else []
        lang_info: dict[str, dict[str, Any]] = {}

        for language in languages:
            if not isinstance(language, dict):
                continue

            base_language = language.get('code')
            if not isinstance(base_language, str) or not base_language:
                continue

            localized_names = language.get('localized_friendly_name', {})
            if not isinstance(localized_names, dict):
                localized_names = {}

            default_name = (
                localized_names.get('en_US')
                or localized_names.get('en')
                or language.get('friendly_name')
                or base_language.upper()
            )

            regions = language.get('regions', [])
            if isinstance(regions, list):
                for region in regions:
                    if not isinstance(region, dict):
                        continue

                    region_code = region.get('code')
                    if not isinstance(region_code, str) or not region_code:
                        continue

                    locale_code = region.get('locale_code')
                    if not locale_code:
                        locale_code = f'{base_language}_{region_code}'
                    self._add_language_info(
                        lang_info,
                        locale_code,
                        {
                            'display': region.get('display') or default_name,
                            'emoji': region.get('emoji', '🌐'),
                            'base_language': base_language,
                            'region_code': region_code,
                            'default': region.get('default', False),
                            'localized_friendly_name': localized_names,
                            'kind': 'region',
                        },
                    )

            variants = language.get('custom_variants', [])
            if isinstance(variants, list):
                for variant in variants:
                    if not isinstance(variant, dict):
                        continue

                    variant_code = variant.get('code')
                    if not isinstance(variant_code, str) or not variant_code:
                        continue

                    locale_code = variant.get('locale_code') or (
                        f'{base_language}_{variant_code.upper()}'
                    )
                    self._add_language_info(
                        lang_info,
                        locale_code,
                        {
                            'display': (
                                variant.get('display')
                                or variant.get('friendly_name')
                                or variant_code
                            ),
                            'emoji': variant.get('emoji', '🌐'),
                            'base_language': base_language,
                            'variant_code': variant_code,
                            'tone': variant.get('tone'),
                            'localized_friendly_name': variant.get(
                                'localized_friendly_name',
                                {},
                            ),
                            'kind': 'variant',
                        },
                    )

        if lang_info:
            self.lang_info = lang_info
            return

        self._load_legacy_lang_info()

    def _add_language_info(
        self,
        destination: dict[str, dict[str, Any]],
        code: str,
        info: dict[str, Any],
    ) -> None:
        normalized = self._normalize_code(code)
        if normalized in {self._normalize_code(existing) for existing in destination}:
            self.logger.warning('Ignoring duplicate locale metadata code %r.', code)
            return

        destination[code] = {'code': code, **info}

    def _load_legacy_lang_info(self) -> None:
        candidates = (
            self.locales_path / 'available_languages.json',
            self.locales_path.parent / 'json' / 'available_languages.json',
        )

        for lang_file in candidates:
            try:
                if not lang_file.is_file():
                    continue

                with lang_file.open('rb') as file:
                    data = orjson.loads(file.read())

                if not isinstance(data, list):
                    raise ValueError('Available languages must be a JSON array.')

                self.lang_info = {
                    item['code']: item
                    for item in data
                    if isinstance(item, dict)
                    and isinstance(item.get('code'), str)
                    and item['code']
                }
                return
            except (OSError, ValueError, TypeError, KeyError):
                self.logger.exception(
                    'Failed to load legacy language catalog from %s',
                    lang_file,
                )

        self.lang_info = {}

    @staticmethod
    def _normalize_code(code: str | Locale | None) -> str:
        return str(code or '').strip().replace('-', '_').casefold()

    def normalize_language_code(self, locale: str | Locale | None) -> str:
        """Normalize a saved or Discord locale to a supported metadata locale code."""
        normalized = self._normalize_code(locale)

        for code in self.lang_info:
            if self._normalize_code(code) == normalized:
                return code

        preferred = self.processor.normalize_preference_locale(str(locale or ''))
        for code in self.lang_info:
            if self._normalize_code(code) == self._normalize_code(preferred):
                return code

        base_language = normalized.split('_', maxsplit=1)[0]
        candidates = [
            (code, info)
            for code, info in self.lang_info.items()
            if self._normalize_code(
                str(info.get('base_language', code)).split('_', maxsplit=1)[0],
            )
            == base_language
        ]

        for code, info in candidates:
            if info.get('kind') == 'region' and info.get('default') is True:
                return code

        for code, info in candidates:
            if info.get('kind') == 'region':
                return code

        if candidates:
            return candidates[0][0]

        fallback = self.processor.options.fallback_language
        fallback_base = self._normalize_code(fallback).split('_', maxsplit=1)[0]
        for code, info in self.lang_info.items():
            base = self._normalize_code(
                str(info.get('base_language', code)).split('_', maxsplit=1)[0],
            )
            if base == fallback_base:
                return code

        return next(iter(self.lang_info), fallback)

    def _localized_display(self, info: dict[str, Any], current_locale: str) -> str:
        localized_names = info.get('localized_friendly_name')
        if not isinstance(localized_names, dict) or not localized_names:
            return str(info.get('display') or info.get('code') or 'Unknown')

        normalized_current = self.normalize_language_code(current_locale)
        current_info = self.lang_info.get(normalized_current, {})
        current_base = str(
            current_info.get('base_language')
            or normalized_current.split('_', maxsplit=1)[0]
        ).casefold()

        normalized_names = {
            self._normalize_code(key): value
            for key, value in localized_names.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        exact = normalized_names.get(self._normalize_code(normalized_current))
        if exact:
            return exact

        for key, value in normalized_names.items():
            if key.split('_', maxsplit=1)[0] == current_base:
                return value

        return (
            normalized_names.get('en_us')
            or next(iter(localized_names.values()))
            or str(info.get('display') or info.get('code') or 'Unknown')
        )

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
        selected_code = self.normalize_language_code(current_locale)
        options = []

        for code, info in self.lang_info.items():
            label = self._localized_display(info, selected_code)
            emoji = info.get('emoji', '🌐')
            options.append(
                SelectOption(
                    label=str(label)[:100],
                    value=code,
                    emoji=emoji,
                    default=(code == selected_code),
                ),
            )

        return options
