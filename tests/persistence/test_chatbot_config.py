from poxbot.persistence.models.guild_settings_v2 import (
    ChatbotConfig,
    ChatbotMethodType,
    GuildConfigV2,
    MarkovModelScope,
)


def test_chatbot_config_round_trip_preserves_markov_settings() -> None:
    config = GuildConfigV2(
        features={
            'chatbot': ChatbotConfig(
                enabled=True,
                type=ChatbotMethodType.markov_chain,
                markov_scope=MarkovModelScope.GLOBAL,
                markov_order=3,
                markov_max_tokens=80,
            ),
        },
    )

    restored = GuildConfigV2.from_dict(config.to_dict())

    assert restored.chatbot.enabled is True
    assert restored.chatbot.type is ChatbotMethodType.markov_chain
    assert restored.chatbot.markov_scope is MarkovModelScope.GLOBAL
    assert restored.chatbot.markov_order == 3
    assert restored.chatbot.markov_max_tokens == 80
