from poxbot.persistence.models.guild_settings_v2 import GuildConfigV2, LogsConfig


def test_guild_logs_config_round_trip() -> None:
    config = GuildConfigV2.from_dict(
        {
            'version': 4,
            'features': {
                'logs': {
                    'enabled': True,
                    'channel_id': 123,
                },
            },
        },
    )

    assert isinstance(config.logs, LogsConfig)
    assert config.logs.enabled is True
    assert config.logs.channel_id == 123

    restored = GuildConfigV2.from_dict(config.to_dict())
    assert restored.logs.enabled is True
    assert restored.logs.channel_id == 123


def test_guild_logs_migrate_legacy_global_chat_log_channel() -> None:
    config = GuildConfigV2.from_dict(
        {
            'version': 4,
            'features': {
                'global_chat': {
                    'channel_id': 100,
                    'log_channel_id': 456,
                },
            },
        },
    )

    assert config.logs.enabled is True
    assert config.logs.channel_id == 456
    assert 'log_channel_id' not in config.to_dict()['features']['global_chat']
