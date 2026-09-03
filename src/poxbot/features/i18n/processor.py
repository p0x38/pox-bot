import asyncio
import os
import re
from pathlib import Path as StdPath
from typing import Any

import aiofiles
import icu
import orjson
from anyio import Path as AsyncPath

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
    def __init__(self, options: TranslatorOptions | None = None):
        self.options = options or TranslatorOptions()
        self.locales_path = self.options.base_path

        self.translations: dict[str, dict[str, Any]] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
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

    def load_metadata(self, language: str) -> dict[str, Any]:
        if language in self.metadata:
            return self.metadata[language]

        meta_path = self.locales_path / language / 'metadata.json'
        if meta_path.exists():
            try:
                with meta_path.open('rb') as f:
                    self.metadata[language] = orjson.loads(f.read())
            except Exception:
                logger.exception('Failed to load metadata for %s', language)
                self.metadata[language] = {}
        else:
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

    def _normalize_locale(self, locale_str: str) -> str:
        if not locale_str:
            return self.options.fallback_language

        norm = locale_str.replace('_', '-').lower()
        if norm in self.available_files:
            return norm

        base = norm.split('-')[0]
        if base in self.available_files:
            return base

        return self.options.fallback_language

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
        target_tone = kwargs.get('tone') or self.options.fallback_tone

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
