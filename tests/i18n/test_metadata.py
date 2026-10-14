import json
from pathlib import Path

from poxbot.core.resources import FilesystemResolver, ResourceManager
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
                        'es_ES': 'Inglés',
                    },
                    'regions': [
                        {
                            'code': 'US',
                            'friendly_name': 'United States',
                            'localized_friendly_name': {
                                'en_US': 'United States',
                                'ja_JP': 'アメリカ合衆国',
                                'es_ES': 'Estados Unidos',
                            },
                            'emoji': '🇺🇸',
                            'default': True,
                        },
                        {
                            'code': 'GB',
                            'friendly_name': 'United Kingdom',
                            'localized_friendly_name': {
                                'en_US': 'United Kingdom',
                                'ja_JP': 'イギリス',
                                'es_ES': 'Reino Unido',
                            },
                            'emoji': '🇬🇧',
                            'default': False,
                        },
                    ],
                    'custom_variants': [
                        {
                            'code': 'uwu',
                            'locale_code': 'en-x-uwu',
                            'friendly_name': 'Uwuified English',
                            'localized_friendly_name': {
                                "en_US": "Uwuified English",
                                "en_GB": "Uwuified English",
                                "ja_JP": "カワイイ英語",
                                "es_ES": "Gatglés"
                            },
                            'emoji': '🐈',
                            'tone': 'uwu',
                        },
                        {
                            'code': 'lolcat',
                            'locale_code': 'en-x-lolcat',
                            'friendly_name': 'Lolcat English',
                            'localized_friendly_name': {
                                "en_US": "Lolcat English",
                                "en_GB": "Lolcat English",
                                "ja_JP": "猫英語",
                                "es_ES": "Inglés estilo lolcat"
                            },
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
                        'es_ES': 'Japonés',
                    },
                    'regions': [
                        {
                            'code': 'JP',
                            'friendly_name': 'Japan',
                            'localized_friendly_name': {
                                'en_US': 'Japan',
                                'ja_JP': '日本',
                                'es_ES': 'Japón',
                            },
                            'emoji': '🇯🇵',
                            'default': True,
                        },
                    ],
                    'custom_variants': [],
                },
                {
                    'code': 'es',
                    'localized_friendly_name': {
                        'en_US': 'Spanish',
                        'ja_JP': 'スペイン語',
                        'es_ES': 'Español',
                    },
                    'regions': [
                        {
                            'code': 'ES',
                            'friendly_name': 'Spain',
                            'localized_friendly_name': {
                                'en_US': 'Spain',
                                'ja_JP': 'スペイン',
                                'es_ES': 'España',
                            },
                            'emoji': '🇪🇸',
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
    assert processor.normalize_preference_locale('en-x-uwu') == 'en-x-uwu'
    assert processor.get_locale_tone('en-x-uwu') == 'uwu'
    assert processor.get_locale_tone('en-x-lolcat') == 'lolcat'


def test_i18n_manager_builds_options_from_shared_metadata(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    _write_metadata(locales_path)
    resources = ResourceManager()
    resources.register('assets', FilesystemResolver(locales_path.parent))
    manager = I18nManager(locales_path, resource_manager=resources)

    assert set(manager.get_available_language_codes()) == {
        'en_US',
        'en_GB',
        'en-x-uwu',
        'en-x-lolcat',
        'ja_JP',
        'es_ES',
    }

    options = manager.get_select_options('ja_JP')
    by_code = {option.value: option for option in options}

    assert by_code['en_US'].label == '英語 (アメリカ合衆国)'
    assert by_code['ja_JP'].label == '日本語 (日本)'
    assert by_code['ja_JP'].default is True

    english_options = manager.get_select_options('en_US')
    by_english_code = {option.value: option for option in english_options}
    assert by_english_code['en_US'].label == 'English (United States)'
    assert by_english_code['en_GB'].label == 'English (United Kingdom)'
    assert by_english_code['ja_JP'].label == 'Japanese (Japan)'
    assert by_english_code['en-x-uwu'].label == 'Uwuified English'

    spanish_options = manager.get_select_options('es_ES')
    by_spanish_code = {option.value: option for option in spanish_options}
    assert by_spanish_code['en_US'].label == 'Inglés (Estados Unidos)'
    assert by_spanish_code['ja_JP'].label == 'Japonés (Japón)'
    assert by_spanish_code['es_ES'].label == 'Español (España)'

    assert sum(option.default for option in options) == 1


def test_legacy_language_code_normalizes_to_default_region(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    _write_metadata(locales_path)
    manager = I18nManager(locales_path)

    assert manager.normalize_language_code('en') == 'en_US'
    assert manager.normalize_language_code('ja') == 'ja_JP'
    assert manager.normalize_language_code('en-x-uwu') == 'en-x-uwu'
    assert manager.normalize_language_code('en-x-lolcat') == 'en-x-lolcat'


def test_metadata_schema_version_must_be_supported(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    locales_path.mkdir(parents=True)
    (locales_path / 'metadata.json').write_text(
        json.dumps(
            {
                'metadata': {
                    'schema_version': 2,
                    'languages': [],
                },
            },
        ),
        encoding='utf-8',
    )

    processor = I18nProcessor(TranslatorOptions(base_path=locales_path))

    assert processor.load_metadata_catalog() == {}


def test_duplicate_metadata_locale_ids_keep_first_entry(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    locales_path.mkdir(parents=True)
    (locales_path / 'metadata.json').write_text(
        json.dumps(
            {
                'metadata': {
                    'schema_version': 1,
                    'languages': [
                        {
                            'code': 'en',
                            'regions': [
                                {
                                    'code': 'US',
                                    'default': True,
                                },
                            ],
                            'custom_variants': [
                                {
                                    'code': 'alternate',
                                    'locale_code': 'en_US',
                                    'tone': 'alternate',
                                },
                            ],
                        },
                    ],
                },
            },
        ),
        encoding='utf-8',
    )

    processor = I18nProcessor(TranslatorOptions(base_path=locales_path))
    entries = processor._metadata_locale_entries()

    assert entries['en-us']['region']['code'] == 'US'
    assert 'variant' not in entries['en-us']


def test_metadata_catalog_uses_resource_address(tmp_path: Path) -> None:
    assets_path = tmp_path / 'assets'
    locales_path = assets_path / 'locales'
    locales_path.mkdir(parents=True)
    (locales_path / 'metadata.json').write_text(
        json.dumps(
            {
                'metadata': {
                    'schema_version': 1,
                    'languages': [{'code': 'ja'}],
                },
            },
        ),
        encoding='utf-8',
    )

    resources = ResourceManager()
    resources.register('assets', FilesystemResolver(assets_path))
    unrelated_path = tmp_path / 'unrelated-locales'
    processor = I18nProcessor(
        TranslatorOptions(base_path=unrelated_path),
        resource_manager=resources,
    )

    catalog = processor.load_metadata_catalog()

    assert [language['code'] for language in catalog['languages']] == ['ja']


def test_metadata_catalog_rejects_non_object_json(tmp_path: Path) -> None:
    locales_path = tmp_path / 'locales'
    locales_path.mkdir(parents=True)
    (locales_path / 'metadata.json').write_text('[]', encoding='utf-8')

    processor = I18nProcessor(TranslatorOptions(base_path=locales_path))

    assert processor.load_metadata_catalog() == {}
