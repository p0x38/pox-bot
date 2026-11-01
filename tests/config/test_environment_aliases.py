from argparse import Namespace
from pathlib import Path

import pytest

from poxbot.config.cli import check_environment
from poxbot.config.schema import BotSettings, DatabaseConfig


def _clear_database_host_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        'POXBOT_DATABASE_HOST',
        'DATABASE_CONFIG__HOST',
        'DATABASE_CONFIG',
    ):
        monkeypatch.delenv(name, raising=False)


def test_environment_alias_overrides_initialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_database_host_environment(monkeypatch)

    monkeypatch.setenv(
        'POXBOT_DATABASE_HOST',
        'environment.example.com',
    )

    settings = BotSettings(
        database_config=DatabaseConfig(
            host='config.example.com',
        ),
    )

    assert settings.database_config.host == 'environment.example.com'


def test_environment_alias_preserves_json_field_names() -> None:
    settings = DatabaseConfig.model_validate(
        {
            'host': 'config.example.com',
            'port': 5433,
        }
    )

    assert settings.host == 'config.example.com'
    assert settings.port == 5433


def test_dotenv_alias_overrides_initialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_database_host_environment(monkeypatch)

    env_file = tmp_path / '.env'
    env_file.write_text(
        'POXBOT_DATABASE_HOST=dotenv.example.com\n',
        encoding='utf-8',
    )

    settings = BotSettings(
        database_config=DatabaseConfig(
            host='config.example.com',
        ),
    )

    assert settings.database_config.host == 'dotenv.example.com'


def test_cli_recognizes_custom_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_database_host_environment(monkeypatch)

    env_file = tmp_path / '.env'
    env_file.write_text(
        '\n'.join(
            [
                'POXBOT_DATABASE_HOST=127.0.0.1',
                'POXBOT_DISCORD_TOKEN=test-token',
                'POXBOT_LOG_LEVEL=INFO',
                'POXBOT_LLM_MODEL=test-model',
            ]
        ),
        encoding='utf-8',
    )

    check_environment(Namespace(env_file=env_file))

    assert 'are valid' in capsys.readouterr().out


def test_nested_environment_name_is_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_database_host_environment(monkeypatch)

    monkeypatch.setenv(
        'DATABASE_CONFIG__HOST',
        'fallback.example.com',
    )

    settings = BotSettings()

    assert settings.database_config.host == 'fallback.example.com'


def test_custom_alias_has_priority_over_nested_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_database_host_environment(monkeypatch)

    monkeypatch.setenv(
        'DATABASE_CONFIG__HOST',
        'fallback.example.com',
    )
    monkeypatch.setenv(
        'POXBOT_DATABASE_HOST',
        'primary.example.com',
    )

    settings = BotSettings()

    assert settings.database_config.host == 'primary.example.com'
