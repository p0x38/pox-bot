import json
from pathlib import Path

from poxbot.features.i18n.processor import I18nProcessor, TranslatorOptions
from poxbot.services.i18n import I18nManager


def _write_metadata(locales_path: Path) -> None:
    (locales_path / 'en').mkdir(parents=True)
    (locales_path / 'ja').mkdir()
    metadata = {
        'metadata': {
            'schema_version': 1,
            'languages': [
                {
                    'code': 'en',
                    'localized_friendly_name': {
                        'en_US': 'English',
                        'ja_JP': '英語',
                    },
                    'regions': [
                        {
                            'code': 'US',
                            'friendly_name': 'United States',
                            'emoji': '🇺🇸',
                            'default': True,
                        },
                    ],
                    'custom_variants': [
                        {
                            'code': 'uwu',
                            'locale_code': 'en_UWU',
                            'friendly_name': 'Uwuified English',
                            'emoji': '🐈',
                            'tone': 'uwu',
                        },
                        {
                            'code': 'lolcat',
                            'locale_code': 'me_OW',
                            'friendly_name': 'Lolcat',
                            'emoji': '🐈',
                            'tone': 'lolcat',
                        },
                    ],
                },
                {
                    'code': 'ja',
                    'localized_friendly_name': {
                        'en_US': 'Japanese',
                        'ja_JP': '日本語',
                    },
                    'regions': [
                        {
                            'code': 'JP',
                            'friendly_name': 'Japan',
                            'emoji': '🇯🇵',
                            'default': True,
                        },
                    ],
                    'custom_variants': [],
                },
            ],
        },
    }
    (locales_path / 'metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding='utf-8',
    )


def test_metadata_catalog_resolves_region_and_variant_codes(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    _write_metadata(locales_path)
    processor = I18nProcessor(TranslatorOptions(base_path=locales_path))

    assert processor._normalize_locale('en_US') == 'en'
    assert processor._normalize_locale('ja-JP') == 'ja'
    assert processor._normalize_locale('me_OW') == 'en'
    assert processor.normalize_preference_locale('en') == 'en_US'
    assert processor.normalize_preference_locale('ja') == 'ja_JP'
    assert processor.normalize_preference_locale('en-uwu') == 'en_UWU'
    assert processor.get_locale_tone('en_UWU') == 'uwu'
    assert processor.get_locale_tone('me_OW') == 'lolcat'


def test_i18n_manager_builds_options_from_shared_metadata(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    _write_metadata(locales_path)
    manager = I18nManager(locales_path)

    assert set(manager.get_available_language_codes()) == {
        'en_US',
        'en_UWU',
        'me_OW',
        'ja_JP',
    }

    options = manager.get_select_options('ja_JP')
    by_code = {option.value: option for option in options}

    assert by_code['en_US'].label == '英語'
    assert by_code['ja_JP'].label == '日本語'
    assert by_code['ja_JP'].default is True
    assert sum(option.default for option in options) == 1


def test_legacy_language_code_normalizes_to_default_region(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    _write_metadata(locales_path)
    manager = I18nManager(locales_path)

    assert manager.normalize_language_code('en') == 'en_US'
    assert manager.normalize_language_code('ja') == 'ja_JP'
    assert manager.normalize_language_code('en_UWU') == 'en_UWU'
    assert manager.normalize_language_code('me_OW') == 'me_OW'
