from poxbot.persistence.models.guild_settings_v2 import (
    AntiMessageFilter,
    GuildConfigV2,
    ProfanityFilter,
    ReactionRoleEntry,
)


def test_missing_feature_configs_are_stored_and_round_trip() -> None:
    config = GuildConfigV2()

    config.filtering.enabled = True
    config.leveling.enabled = True
    config.welcome.enabled = True
    config.tickets.enabled = True
    config.global_chat.enabled = True
    config.userphone.enabled = True
    config.chatbot.enabled = True

    expected_keys = {
        'filtering',
        'leveling',
        'welcome_channel',
        'ticket_system',
        'global_chat',
        'userphone',
        'chatbot',
    }
    assert expected_keys.issubset(config.features)

    restored = GuildConfigV2.from_dict(config.to_dict())

    assert restored.filtering.enabled is True
    assert restored.leveling.enabled is True
    assert restored.welcome.enabled is True
    assert restored.tickets.enabled is True
    assert restored.global_chat.enabled is True
    assert restored.userphone.enabled is True
    assert restored.chatbot.enabled is True


def test_legacy_welcome_key_is_migrated_on_load() -> None:
    config = GuildConfigV2.from_dict(
        {
            'features': {
                'welcome': {
                    'enabled': True,
                    'channels': {'join': 123},
                },
            },
        },
    )

    assert config.welcome.enabled is True
    assert config.welcome.channels.join == 123
    assert 'welcome_channel' in config.features
    assert 'welcome' not in config.features


def test_profanity_global_chat_setting_round_trip() -> None:
    config = GuildConfigV2.from_dict(
        {
            'features': {
                'filtering': {
                    'enabled': True,
                    'filters': {
                        'profanity': {
                            'enabled': True,
                            'use_in_globalchat': False,
                        },
                    },
                },
            },
        },
    )

    profanity = config.filtering.filters['profanity']
    assert isinstance(profanity, ProfanityFilter)
    assert profanity.use_in_globalchat is False

    restored = GuildConfigV2.from_dict(config.to_dict())
    restored_profanity = restored.filtering.filters['profanity']

    assert isinstance(restored_profanity, ProfanityFilter)
    assert restored_profanity.use_in_globalchat is False


def test_reaction_roles_round_trip() -> None:
    entry = ReactionRoleEntry(
        message_id=123,
        emoji='🔥',
        role_id=456,
    )
    config = GuildConfigV2(reaction_roles=[entry])

    restored = GuildConfigV2.from_dict(config.to_dict())

    assert restored.reaction_roles == [entry]


def test_anti_message_filter_round_trip_and_normalizes_user_ids() -> None:
    config = GuildConfigV2.from_dict(
        {
            'features': {
                'filtering': {
                    'enabled': True,
                    'filters': {
                        'anti_message': {
                            'enabled': True,
                            'blocked_user_ids': [123, '456', 'invalid', -1, True],
                        },
                    },
                },
            },
        },
    )

    anti_message = config.filtering.filters['anti_message']
    assert isinstance(anti_message, AntiMessageFilter)
    assert anti_message.enabled is True
    assert anti_message.blocked_user_ids == [123, 456]

    restored = GuildConfigV2.from_dict(config.to_dict())
    restored_filter = restored.filtering.filters['anti_message']
    assert isinstance(restored_filter, AntiMessageFilter)
    assert restored_filter.blocked_user_ids == [123, 456]


def test_anti_message_filter_defaults_to_empty_blocklist() -> None:
    config = GuildConfigV2.from_dict(
        {
            'features': {
                'filtering': {
                    'filters': {
                        'anti_message': {'enabled': False},
                    },
                },
            },
        },
    )

    anti_message = config.filtering.filters['anti_message']
    assert isinstance(anti_message, AntiMessageFilter)
    assert anti_message.enabled is False
    assert anti_message.blocked_user_ids == []
