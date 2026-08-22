from poxbot.persistence.models.guild_settings_v2 import (
    GlobalChatConfig,
    GlobalChatDeliveryType,
    GuildConfigV2,
)


def test_global_chat_config_round_trip_preserves_settings():
    config = GuildConfigV2.from_dict(
        {
            'version': 2,
            'features': {
                'global_chat': {
                    'enabled': True,
                    'channel_id': 123,
                    'webhook_url': 'https://example.com/webhook',
                    'message_delivery_type': GlobalChatDeliveryType.webhook,
                    'silent': True,
                },
            },
        },
    )

    global_chat = config.global_chat

    assert isinstance(global_chat, GlobalChatConfig)
    assert global_chat.enabled is True
    assert global_chat.channel_id == 123
    assert global_chat.webhook_url == 'https://example.com/webhook'
    assert global_chat.message_delivery_type == GlobalChatDeliveryType.webhook
    assert global_chat.silent is True
