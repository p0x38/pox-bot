from poxbot.persistence.models.guild_settings_v2 import (
    ChatbotConfig,
    GuildConfigV2,
)


def test_chatbot_config_round_trip() -> None:
    config = GuildConfigV2(
        features={
            'chatbot': ChatbotConfig(enabled=True),
        },
    )

    restored = GuildConfigV2.from_dict(config.to_dict())

    assert restored.chatbot.enabled is True


def test_legacy_markov_settings_are_ignored() -> None:
    legacy_data = {
        'version': 4,
        'features': {
            'chatbot': {
                'enabled': True,
                'type': 1,
                'markov_scope': 'global',
                'markov_order': 3,
                'markov_max_tokens': 80,
            },
        },
    }

    restored = GuildConfigV2.from_dict(legacy_data)

    assert restored.chatbot.enabled is True

    serialized = restored.to_dict()['features']['chatbot']

    assert 'type' not in serialized
    assert 'markov_scope' not in serialized
    assert 'markov_order' not in serialized
    assert 'markov_max_tokens' not in serialized
