from pathlib import Path as StdPath

import orjson
from discord import SelectOption

from ...infrastructure.logger import get_logger
from .processor import I18nProcessor
from .translator import DiscordI18nTranslator, I18nTranslator

translation_manager_logger = get_logger(__name__, prefix='TranslationManager')


class TranslationManager:
    def __init__(self, locales_path: str = 'locales'):
        self.locales_path = locales_path
        try:
            with StdPath('src/poxbot/assets/json/available_languages.json').open(
                encoding='utf-8',
            ) as f:
                data = orjson.loads(f.read())
                self.lang_info = {item['code']: item for item in data}
        except Exception as e:
            translation_manager_logger.exception(
                'Failed to load available_languages.json: %s',
                e.__str__(),
            )
            self.lang_info = {}

        self.internal_translator: I18nTranslator | None = None
        self.discord_translator: DiscordI18nTranslator | None = None
        self.processor: I18nProcessor | None = None

    def initialize(self, processor: I18nProcessor):
        self.internal_translator = I18nTranslator(processor=processor)

        self.discord_translator = DiscordI18nTranslator(
            internal=self.internal_translator,
        )

        translation_manager_logger.info('TranslationManager initialized.')

    def get_translator(self):
        return self.internal_translator

    def get_discord_translator(self):
        return self.discord_translator

    def get_available_language_codes(self) -> list[str]:
        return list(self.lang_info.keys())

    def get_select_options(self, current_locale: str) -> list[SelectOption]:
        options = []
        for code, info in self.lang_info.items():
            display_name = info.get('display', code.upper())
            emoji = info.get('emoji', '🌐')

            options.append(
                SelectOption(
                    label=display_name,
                    value=code,
                    emoji=emoji,
                    default=(code == current_locale),
                ),
            )
        return options


manager = TranslationManager(locales_path='src/poxbot/assets/locales')
