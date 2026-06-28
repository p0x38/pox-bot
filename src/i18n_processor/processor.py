import asyncio
import os
import re
from typing import Any

import aiofiles
import icu
import orjson

from logger import logger


def natural_key(s: str):
    return [
        int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)
    ]


class TranslatorOptions:
    def __init__(
        self,
        base_path: str | os.PathLike = "src/assets/locales",
        fallback_language: str = "en",
        fallback_tone: str = "formal",
        directory_format: str = "{base_path}/{language}/{namespace}.json",
    ):
        self.base_path = os.path.abspath(base_path)
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
            base_path=self.locales_path, language=language, namespace=namespace
        )

    def load_metadata(self, language: str) -> dict[str, Any]:
        if language in self.metadata:
            return self.metadata[language]

        meta_path = os.path.join(self.locales_path, language, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "rb") as f:
                    self.metadata[language] = orjson.loads(f.read())
            except Exception as e:
                logger.error(f"Failed to load metadata for {language}: {e} XD")
                self.metadata[language] = {}
        else:
            self.metadata[language] = {}

        return self.metadata[language]

    async def _flush_missing_keys(self):
        await asyncio.sleep(self.batch_delay)
        if self.missing_keys_buffer:
            report = ["Translation Missing Report:"]
            for key in sorted(self.missing_keys_buffer, key=natural_key):
                langs = self.missing_keys_buffer[key]
                report.append(f"* Key: '{key}' in {', '.join(sorted(langs))}")

            logger.warning("\n".join(report) + "\n")
            self.missing_keys_buffer.clear()

    def _sync_cache_locales(self):
        if os.path.exists(self.locales_path):
            self.available_files = {
                name
                for name in os.listdir(self.locales_path)
                if os.path.isdir(os.path.join(self.locales_path, name))
            }

    async def preload_all(self):
        tasks = []
        for locale in self.available_files:
            self.load_metadata(locale)

            locale_dir = os.path.join(self.locales_path, locale)
            if not os.path.isdir(locale_dir):
                continue

            for filename in os.listdir(locale_dir):
                if filename.endswith(".json") and filename != "metadata.json":
                    namespace = filename[:-5]
                    tasks.append(self._load_file_async(locale, namespace))

        await asyncio.gather(*tasks)
        logger.info(
            f"Processor: Preloaded {len(self.available_files)} languages with in-file tone block."
        )

    async def _load_file_async(self, language: str, namespace: str) -> dict[str, Any]:
        if language in self.translations and namespace in self.translations[language]:
            return self.translations[language][namespace]

        file_path = self._get_path(language, namespace)
        data = {}

        if os.path.exists(file_path):
            try:
                async with aiofiles.open(file_path, mode="rb") as f:
                    content = await f.read()
                    data = orjson.loads(content)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e} D:<")

        self.translations.setdefault(language, {})[namespace] = data
        return data

    def _get_cached_translation(self, language: str, namespace: str) -> dict[str, Any]:
        return self.translations.get(language, {}).get(namespace, {})

    def _normalize_locale(self, locale_str: str) -> str:
        if not locale_str:
            return self.options.fallback_language

        norm = locale_str.replace("_", "-").lower()
        if norm in self.available_files:
            return norm

        base = norm.split("-")[0]
        if base in self.available_files:
            return base

        return self.options.fallback_language

    def _resolve_key_with_tone(
        self, data: dict[str, Any], key_path: str, tone: str
    ) -> Any:
        keys = self._key_cache.get(key_path)

        if keys is None:
            keys = key_path.split(".")
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
            elif self.options.fallback_tone in value:
                return value[self.options.fallback_tone]

            if "default" in value:
                return value["default"]
            return None

        if isinstance(value, str):
            return value

        return value

    def translate_string(
        self, text: str, locale_str: str, tone: str | None = None, **kwargs
    ) -> str:
        lang = self._normalize_locale(locale_str)
        target_tone = tone or self.options.fallback_tone

        if "." in text:
            namespace, key_path = text.split(".", 1)
        else:
            namespace, key_path = "main", text

        data = self._get_cached_translation(lang, namespace)
        translated = self._resolve_key_with_tone(data, key_path, target_tone)

        if (
            translated is None
            or (isinstance(translated, str) and not translated.strip())
        ) and lang != self.options.fallback_language:
            en_data = self._get_cached_translation(
                self.options.fallback_language, namespace
            )
            translated = self._resolve_key_with_tone(
                en_data, key_path, self.options.fallback_tone
            )

        is_missing = (translated is None) or (
            isinstance(translated, str) and not translated.strip()
        )

        is_same_as_en = False
        if not is_missing and lang != self.options.fallback_language:
            en_data = self._get_cached_translation(
                self.options.fallback_language, namespace
            )
            en_val = self._resolve_key_with_tone(
                en_data, key_path, self.options.fallback_tone
            )
            if translated == en_val:
                is_same_as_en = True

        if is_missing or is_same_as_en:
            if text not in self.missing_keys_buffer:
                self.missing_keys_buffer[text] = set()

            report_tag = f"{lang} (untranslated)" if is_same_as_en else lang
            self.missing_keys_buffer[text].add(report_tag)

            if self.batch_task is None:
                try:
                    loop = asyncio.get_running_loop()
                    self.batch_task = loop.create_task(self._flush_missing_keys())
                    self.batch_task.add_done_callback(
                        lambda _t: setattr(self, "batch_task", None)
                    )
                except RuntimeError:
                    pass

            if is_missing and lang != self.options.fallback_language:
                en_data = self._get_cached_translation(
                    self.options.fallback_language, namespace
                )
                translated = self._resolve_key_with_tone(
                    en_data, key_path, self.options.fallback_tone
                )

        if translated is None:
            return text

        if isinstance(translated, str):
            if not kwargs:
                return translated

            is_icu = bool(
                re.search(
                    r"\{\s*\w+\s*,\s*(plural|select|selectordinal|choice)", translated
                )
            )

            if is_icu:
                try:
                    arg_names = list(kwargs.keys())
                    icu_pattern = translated

                    for idx, name in enumerate(arg_names):
                        icu_pattern = re.sub(
                            rf"(?<=\{{){re.escape(name)}(?=\s*,)", str(idx), icu_pattern
                        )
                        icu_pattern = re.sub(
                            rf"(?<=\{{){re.escape(name)}(?=\}})", str(idx), icu_pattern
                        )

                    msg_format = icu.MessageFormat(  # type: ignore
                        icu_pattern,
                        icu.Locale(lang.replace("-", "_"))  # type: ignore
                    )

                    args = []

                    for name in arg_names:
                        value = kwargs[name]

                        if isinstance(value, bool):
                            args.append(icu.Formattable(int(value)))  # type: ignore
                        elif isinstance(value, (int, float)):
                            args.append(icu.Formattable(value))  # type: ignore
                        else:
                            args.append(icu.Formattable(str(value)))  # type: ignore

                    return str(msg_format.format(args))
                except Exception:  # noqa: BLE001
                    logger.exception(
                        f"ICU format failed for '{text}' "
                        f"(locale={lang}, kwargs={kwargs})"
                    )
                    for k, v in kwargs.items():
                        translated = translated.replace(f"{{{k}}}", str(v))
                    return translated
            else:
                try:
                    return translated.format(**kwargs)
                except Exception:
                    for k, v in kwargs.items():
                        translated = translated.replace(f"{{{k}}}", str(v))
                    return translated

        return str(translated)
