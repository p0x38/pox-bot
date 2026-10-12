import asyncio
import os
import re
from pathlib import Path as StdPath
from typing import Any

import aiofiles
import icu
import orjson
from anyio import Path as AsyncPath

from ...core.resources import ResourceManager
from ...infrastructure.logger import get_logger

logger = get_logger(__name__, prefix='I18n', extension='i18n')


def natural_key(s: str):
    return [
        int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)
    ]


class TranslatorOptions:
    def __init__(
        self,
        base_path: str | os.PathLike = 'src/poxbot/assets/locales',
        fallback_language: str = 'en',
        fallback_tone: str = 'casual-silly',
        directory_format: str = '{base_path}/{language}/{namespace}.json',
    ):
        self.base_path = StdPath(base_path).resolve()
        self.fallback_language = fallback_language
        self.fallback_tone = fallback_tone
        self.directory_format = directory_format


class I18nProcessor:
    def __init__(
        self,
        options: TranslatorOptions | None = None,
        *,
        resource_manager: ResourceManager | None = None,
    ):
        self.options = options or TranslatorOptions()
        self.resource_manager = resource_manager
        self.locales_path = self.options.base_path
        self._preloaded = False

        self.translations: dict[str, dict[str, Any]] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self._metadata_catalog: dict[str, Any] | None = None
        self._metadata_catalog_loaded = False
        self._metadata_locale_entries_cache: dict[str, dict[str, Any]] | None = None
        self.available_files: set[str] = set()

        self._key_cache: dict[str, list[str]] = {}

        self._sync_cache_locales()

        self.missing_keys_buffer: dict[str, set[str]] = {}
        self.batch_delay = 5.0
        self.batch_task: asyncio.Task | None = None

    def _get_path(self, language: str, namespace: str) -> str:
        return self.options.directory_format.format(
            base_path=self.locales_path,
            language=language,
            namespace=namespace,
        )

    def load_metadata_catalog(self) -> dict[str, Any]:
        """Load the shared locale metadata catalog."""
        if self._metadata_catalog_loaded:
            return self._metadata_catalog or {}

        self._metadata_catalog_loaded = True
        meta_path = (
            self.resource_manager.resolve_path('assets:locales/metadata.json')
            if self.resource_manager is not None
            else self.locales_path / 'metadata.json'
        )

        if not meta_path.is_file():
            self._metadata_catalog = {}
            return self._metadata_catalog

        try:
            with meta_path.open('rb') as f:
                data = orjson.loads(f.read())

            catalog = data.get('metadata', data) if isinstance(data, dict) else {}
            if not isinstance(catalog, dict):
                raise ValueError('Metadata root must be a JSON object.')

            schema_version = catalog.get('schema_version', 1)
            if (
                isinstance(schema_version, bool)
                or not isinstance(schema_version, int)
                or schema_version != 1
            ):
                raise ValueError(
                    f'Unsupported locale metadata schema version: {schema_version!r}.'
                )

            languages = catalog.get('languages', [])
            if not isinstance(languages, list):
                raise ValueError("'metadata.languages' must be a JSON array.")

            valid_languages = []
            seen_codes: set[str] = set()
            for item in languages:
                if not isinstance(item, dict):
                    logger.warning('Ignoring non-object entry in locale metadata.')
                    continue

                code = item.get('code')
                if not isinstance(code, str) or not code.strip():
                    logger.warning('Ignoring locale metadata entry without a code.')
                    continue

                normalized_code = code.casefold()
                if normalized_code in seen_codes:
                    logger.warning('Ignoring duplicate locale metadata code %r.', code)
                    continue

                seen_codes.add(normalized_code)
                valid_languages.append(item)

            catalog['languages'] = valid_languages
            self._metadata_catalog = catalog
        except (OSError, ValueError, TypeError):
            logger.exception('Failed to load locale metadata catalog from %s', meta_path)
            self._metadata_catalog = {}

        return self._metadata_catalog

    def load_metadata(self, language: str) -> dict[str, Any]:
        """Return metadata for a base language."""
        if language in self.metadata:
            return self.metadata[language]

        normalized = str(language).replace('_', '-').casefold().split('-', maxsplit=1)[0]
        catalog = self.load_metadata_catalog()

        for item in catalog.get('languages', []):
            code = item.get('code')
            if isinstance(code, str) and code.casefold() == normalized:
                self.metadata[language] = item
                return item

        # Keep supporting older per-locale metadata files during migration.
        if re.fullmatch(r'[A-Za-z0-9_-]+', str(language)):
            meta_path = (
                self.resource_manager.resolve_path(
                    f'assets:locales/{language}/metadata.json',
                )
                if self.resource_manager is not None
                else self.locales_path / str(language) / 'metadata.json'
            )
            if meta_path.is_file():
                try:
                    with meta_path.open('rb') as f:
                        data = orjson.loads(f.read())
                    if isinstance(data, dict):
                        self.metadata[language] = data
                        return data
                except (OSError, ValueError, TypeError):
                    logger.exception('Failed to load metadata for %s', language)

        self.metadata[language] = {}
        return self.metadata[language]

    async def _flush_missing_keys(self):
        await asyncio.sleep(self.batch_delay)
        if self.missing_keys_buffer:
            report = ['Translation Missing Report:']
            for key in sorted(self.missing_keys_buffer, key=natural_key):
                langs = self.missing_keys_buffer[key]
                report.append(f"* Key: '{key}' in {', '.join(sorted(langs))}")

            logger.warning(
                '\n'.join(report),
                extra={
                    'missing_keys': list(self.missing_keys_buffer.keys()),
                    'languages': {
                        k: list(v) for k, v in self.missing_keys_buffer.items()
                    },
                },
            )
            self.missing_keys_buffer.clear()

    def _sync_cache_locales(self):
        if self.locales_path.exists():
            self.available_files = {
                name.name
                for name in self.locales_path.iterdir()
                if (self.locales_path / name).is_dir()
            }

    async def preload_all(self):
        if self._preloaded:
            return

        tasks = []

        for locale in self.available_files:
            self.load_metadata(locale)

            locale_dir = AsyncPath(self.locales_path / locale)
            if not await locale_dir.is_dir():
                continue

            async for filename in locale_dir.iterdir():
                if filename.name.endswith('.json') and filename != 'metadata.json':
                    namespace = filename.name[:-5]
                    tasks.append(self._load_file_async(locale, namespace))

        await asyncio.gather(*tasks)

        self._preloaded = True

        logger.info(
            'Processor: Preloaded %d languages with in-file tone block.',
            len(self.available_files),
        )

    async def _load_file_async(self, language: str, namespace: str) -> dict[str, Any]:
        if language in self.translations and namespace in self.translations[language]:
            return self.translations[language][namespace]

        file_path = self._get_path(language, namespace)
        data = {}

        if await AsyncPath(file_path).exists():
            try:
                async with aiofiles.open(file_path, mode='rb') as f:
                    content = await f.read()
                    data = orjson.loads(content)
            except Exception:
                logger.exception('Failed to load %s', file_path)

        self.translations.setdefault(language, {})[namespace] = data
        return data

    def _get_cached_translation(self, language: str, namespace: str) -> dict[str, Any]:
        return self.translations.get(language, {}).get(namespace, {})

    def _metadata_locale_entries(self) -> dict[str, dict[str, Any]]:
        if self._metadata_locale_entries_cache is not None:
            return self._metadata_locale_entries_cache

        entries: dict[str, dict[str, Any]] = {}

        for language in self.load_metadata_catalog().get('languages', []):
            if not isinstance(language, dict):
                continue

            base_language = language.get('code')
            if not isinstance(base_language, str) or not base_language:
                continue

            regions = language.get('regions', [])
            if isinstance(regions, list):
                for region in regions:
                    if not isinstance(region, dict):
                        continue
                    region_code = region.get('code')
                    if not isinstance(region_code, str) or not region_code:
                        continue
                    locale_code = region.get('locale_code') or f'{base_language}_{region_code}'
                    normalized_locale = locale_code.replace('_', '-').casefold()
                    if normalized_locale in entries:
                        logger.warning(
                            'Ignoring duplicate locale metadata code %r.',
                            locale_code,
                        )
                        continue
                    entries[normalized_locale] = {
                        'locale_code': locale_code,
                        'base_language': base_language,
                        'metadata': language,
                        'region': region,
                    }

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
                    normalized_locale = locale_code.replace('_', '-').casefold()
                    if normalized_locale in entries:
                        logger.warning(
                            'Ignoring duplicate locale metadata code %r.',
                            locale_code,
                        )
                        continue
                    entries[normalized_locale] = {
                        'locale_code': locale_code,
                        'base_language': base_language,
                        'metadata': language,
                        'variant': variant,
                    }

        self._metadata_locale_entries_cache = entries
        return entries

    def get_locale_tone(self, locale_str: str) -> str | None:
        normalized = str(locale_str).strip().replace('_', '-').casefold()
        entry = self._metadata_locale_entries().get(normalized)
        if not entry:
            return None

        variant = entry.get('variant')
        tone = variant.get('tone') if isinstance(variant, dict) else None
        return tone if isinstance(tone, str) and tone else None

    def normalize_preference_locale(self, locale_str: str | None) -> str:
        """Return the stable metadata locale code used to store a preference."""
        normalized = str(locale_str or '').strip().replace('_', '-').casefold()
        entries = self._metadata_locale_entries()

        if normalized in entries:
            return str(entries[normalized]['locale_code'])

        base_language = normalized.split('-', maxsplit=1)[0]
        candidates = [
            entry
            for entry in entries.values()
            if str(entry.get('base_language', '')).casefold() == base_language
        ]

        for entry in candidates:
            region = entry.get('region')
            if isinstance(region, dict) and region.get('default') is True:
                return str(entry['locale_code'])

        for entry in candidates:
            if 'region' in entry:
                return str(entry['locale_code'])

        available = {
            name.replace('_', '-').casefold(): name
            for name in self.available_files
        }
        if normalized in available:
            return available[normalized]

        fallback = self.options.fallback_language
        for entry in entries.values():
            if (
                str(entry.get('base_language', '')).casefold() == fallback.casefold()
                and isinstance(entry.get('region'), dict)
                and entry['region'].get('default') is True
            ):
                return str(entry['locale_code'])

        return fallback

    def _normalize_locale(self, locale_str: str) -> str:
        if not locale_str:
            locale_str = self.options.fallback_language

        norm = str(locale_str).strip().replace('_', '-').casefold()
        entries = self._metadata_locale_entries()
        entry = entries.get(norm)
        if entry:
            base_language = entry.get('base_language')
            if base_language in self.available_files:
                return base_language

        available = {
            name.replace('_', '-').casefold(): name
            for name in self.available_files
        }

        if norm in available:
            return available[norm]

        base = norm.split('-', maxsplit=1)[0]
        if base in available:
            return available[base]

        fallback = self.options.fallback_language
        normalized_fallback = fallback.replace('_', '-').casefold()
        return available.get(normalized_fallback, fallback)

    def _resolve_key_with_tone(
        self,
        data: dict[str, Any],
        key_path: str,
        tone: str,
    ) -> Any:
        keys = self._key_cache.get(key_path)

        if keys is None:
            keys = key_path.split('.')
            self._key_cache[key_path] = keys
        value = data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None

        if isinstance(value, dict):
            if tone in value:
                return value[tone]
            if self.options.fallback_tone in value:
                return value[self.options.fallback_tone]

            if 'default' in value:
                return value['default']
            return None

        if isinstance(value, str):
            return value

        return value

    def _format_icu(self, translated: str, lang: str, kwargs: dict[str, Any]) -> str:
        """Helper to formatting ICU pattern and restrict statements inside try-block."""
        arg_names = list(kwargs.keys())
        icu_pattern = translated

        for idx, name in enumerate(arg_names):
            icu_pattern = re.sub(
                rf'(?<=\{{){re.escape(name)}(?=\s*,)',
                str(idx),
                icu_pattern,
            )
            icu_pattern = re.sub(
                rf'(?<=\{{){re.escape(name)}(?=\}})',
                str(idx),
                icu_pattern,
            )

        msg_format = icu.MessageFormat(icu_pattern, icu.Locale(lang.replace('-', '_')))
        args = []

        for name in arg_names:
            value = kwargs[name]
            if isinstance(value, bool):
                args.append(icu.Formattable(int(value)))
            elif isinstance(value, (int, float)):
                args.append(icu.Formattable(value))
            else:
                args.append(icu.Formattable(str(value)))
        return str(msg_format.format(args))

    def translate_string(
        self,
        key: str | list[str],
        locale_str: str,
        **kwargs,
    ) -> str:
        """Translate a string key to a localized string with fallback support.

        Args:
            key: Translation key as string or list of strings for fallback chain.
            locale_str: Locale string to translate to.
            **kwargs: Format arguments for ICU or string formatting.

        Returns:
            Translated and formatted string.
        """
        lang = self._normalize_locale(locale_str)
        target_tone = (
            kwargs.get('tone')
            or self.get_locale_tone(locale_str)
            or self.options.fallback_tone
        )

        keys_to_try = key if isinstance(key, list) else [key]
        primary_key = keys_to_try[0]

        translated = None
        namespace = 'main'
        key_path = ''

        for current_key in keys_to_try:
            if '.' in current_key:
                namespace, key_path = current_key.split('.', 1)
            else:
                namespace, key_path = 'main', current_key

            data = self._get_cached_translation(lang, namespace)
            translated = self._resolve_key_with_tone(data, key_path, target_tone)

            if translated is not None and (
                not isinstance(translated, str) or translated.strip()
            ):
                break

            # Try fallback language if current language failed
            if (
                translated is None
                or (isinstance(translated, str) and not translated.strip())
            ) and lang != self.options.fallback_language:
                en_data = self._get_cached_translation(
                    self.options.fallback_language,
                    namespace,
                )
                translated = self._resolve_key_with_tone(
                    en_data,
                    key_path,
                    self.options.fallback_tone,
                )
                if translated is not None and (
                    not isinstance(translated, str) or translated.strip()
                ):
                    break

        is_missing = (translated is None) or (
            isinstance(translated, str) and not translated.strip()
        )

        is_same_as_en = False
        if not is_missing and lang != self.options.fallback_language:
            en_data = self._get_cached_translation(
                self.options.fallback_language,
                namespace,
            )
            en_val = self._resolve_key_with_tone(
                en_data,
                key_path,
                self.options.fallback_tone,
            )
            if translated == en_val:
                is_same_as_en = True

        if is_missing or is_same_as_en:
            if primary_key not in self.missing_keys_buffer:
                self.missing_keys_buffer[primary_key] = set()

            report_tag = f'{lang} (untranslated)' if is_same_as_en else lang
            self.missing_keys_buffer[primary_key].add(report_tag)

            if self.batch_task is None:
                try:
                    loop = asyncio.get_running_loop()
                    self.batch_task = loop.create_task(self._flush_missing_keys())
                    self.batch_task.add_done_callback(
                        lambda _: setattr(self, 'batch_task', None),
                    )
                except RuntimeError:
                    pass

            if is_missing and lang != self.options.fallback_language:
                en_data = self._get_cached_translation(
                    self.options.fallback_language,
                    namespace,
                )
                translated = self._resolve_key_with_tone(
                    en_data,
                    key_path,
                    self.options.fallback_tone,
                )

        if translated is None:
            return primary_key

        if isinstance(translated, str):
            if not kwargs:
                return translated

            is_icu = bool(
                re.search(
                    r'\{\s*\w+\s*,\s*(plural|select|selectordinal|choice)',
                    translated,
                ),
            )

            if is_icu:
                try:
                    return self._format_icu(translated, lang, kwargs)
                except Exception:
                    logger.exception(
                        "ICU format failed for '%s' (locale=%s, kwargs=%s)",
                        primary_key,
                        lang,
                        kwargs,
                    )
                    for k, v in kwargs.items():
                        translated = translated.replace(f'{{{k}}}', str(v))
                    return translated
            else:
                try:
                    return translated.format(**kwargs)
                except Exception:
                    for k, v in kwargs.items():
                        translated = translated.replace(f'{{{k}}}', str(v))
                    return translated

        return str(translated)
