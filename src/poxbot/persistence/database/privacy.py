from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update

from ...shared.bases import BaseDatabase
from ..models.economy_orm import (
    EconomyInventory,
    EconomyTransaction,
    EconomyUser,
)
from ..models.giveaway_orm import Giveaway
from ..models.global_chat_moderation_orm import GlobalChatModerationCase
from ..models.guild_settings_v2 import GuildConfigV2
from ..models.guild_settings_v2_orm import ActiveTicket, GuildSettings
from ..models.orm.moderation import ModerationEntry
from ..models.stats_orm import DailyUserActivity, UserStatistics
from ..models.user_profile_orm import UserActivity, UserProfile
from ..models.user_settings_orm import UserPreference


class PrivacyDatabase(BaseDatabase):
    """Database operations for user data export and deletion."""

    @staticmethod
    def _serialize_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None

        return value.isoformat()

    @staticmethod
    def _get_row_count(result: Any) -> int:
        """Return a non-negative affected-row count."""
        row_count = result.rowcount

        if row_count is None or row_count < 0:
            return 0

        return int(row_count)

    @staticmethod
    def _matches_user_id(value: Any, user_id: int) -> bool:
        if isinstance(value, bool) or value is None:
            return False

        try:
            return int(value) == user_id
        except (TypeError, ValueError):
            return False

    @classmethod
    def _get_guild_config_user_references(
        cls,
        config: Any,
        user_id: int,
    ) -> dict[str, Any]:
        data = config.to_dict() if hasattr(config, 'to_dict') else config
        if not isinstance(data, dict):
            return {}

        features = data.get('features')
        if not isinstance(features, dict):
            return {}

        references: dict[str, Any] = {}
        executor_features = [
            name
            for name, feature in features.items()
            if isinstance(feature, dict)
            and cls._matches_user_id(feature.get('last_executor'), user_id)
        ]

        if executor_features:
            references['last_executor_features'] = sorted(executor_features)

        filtering = features.get('filtering')
        filters = filtering.get('filters') if isinstance(filtering, dict) else None
        anti_message = (
            filters.get('anti_message') if isinstance(filters, dict) else None
        )
        blocked_user_ids = (
            anti_message.get('blocked_user_ids')
            if isinstance(anti_message, dict)
            else None
        )
        if isinstance(blocked_user_ids, list) and any(
            cls._matches_user_id(value, user_id) for value in blocked_user_ids
        ):
            references['anti_message_blocklist'] = True

        global_chat = features.get('global_chat')
        whitelisted_user_ids = (
            global_chat.get('whitelisted_user_ids')
            if isinstance(global_chat, dict)
            else None
        )
        if isinstance(whitelisted_user_ids, list) and any(
            cls._matches_user_id(value, user_id) for value in whitelisted_user_ids
        ):
            references['global_chat_whitelist'] = True

        return references

    @classmethod
    def _remove_guild_config_user_references(
        cls,
        config: dict[str, Any],
        user_id: int,
    ) -> dict[str, int]:
        features = config.get('features')
        if not isinstance(features, dict):
            return {}

        removed: dict[str, int] = {}

        filtering = features.get('filtering')
        filters = filtering.get('filters') if isinstance(filtering, dict) else None
        anti_message = (
            filters.get('anti_message') if isinstance(filters, dict) else None
        )
        blocked_user_ids = (
            anti_message.get('blocked_user_ids')
            if isinstance(anti_message, dict)
            else None
        )
        if isinstance(blocked_user_ids, list):
            retained_ids = [
                value
                for value in blocked_user_ids
                if not cls._matches_user_id(value, user_id)
            ]
            removed_count = len(blocked_user_ids) - len(retained_ids)
            if removed_count and isinstance(anti_message, dict):
                anti_message['blocked_user_ids'] = retained_ids
                removed['guild_config_blocked_user_references'] = removed_count

        global_chat = features.get('global_chat')
        whitelisted_user_ids = (
            global_chat.get('whitelisted_user_ids')
            if isinstance(global_chat, dict)
            else None
        )
        if isinstance(whitelisted_user_ids, list):
            retained_ids = [
                value
                for value in whitelisted_user_ids
                if not cls._matches_user_id(value, user_id)
            ]
            removed_count = len(whitelisted_user_ids) - len(retained_ids)
            if removed_count and isinstance(global_chat, dict):
                global_chat['whitelisted_user_ids'] = retained_ids
                removed['guild_config_global_chat_whitelist_references'] = (
                    removed_count
                )

        executor_count = 0
        for feature in features.values():
            if (
                isinstance(feature, dict)
                and cls._matches_user_id(feature.get('last_executor'), user_id)
            ):
                feature['last_executor'] = None
                executor_count += 1

        if executor_count:
            removed['guild_config_last_executor_references'] = executor_count

        return removed

    async def export_user_data(self, user_id: int) -> dict[str, Any]:
        """
        Collect data associated with one Discord user.
        
        Only explicitly selected fields are exported. Do not replace these
        dictionaries with generic ORM serialization.
        """
        async with self.async_session() as session:
            statistics = await session.get(UserStatistics, user_id)
            profile = await session.get(UserProfile, user_id)
            activity = await session.get(UserActivity, user_id)
            preference = await session.get(UserPreference, user_id)
            economy_user = await session.get(EconomyUser, user_id)

            daily_activity_result = await session.scalars(
                select(DailyUserActivity)
                .where(DailyUserActivity.user_id == user_id)
                .order_by(DailyUserActivity.activity_date)
            )
            daily_activity = list(daily_activity_result.all())

            inventory_result = await session.scalars(
                select(EconomyInventory)
                .where(EconomyInventory.user_id == user_id)
                .order_by(EconomyInventory.item_id),
            )
            inventory = list(inventory_result.all())

            transaction_result = await session.scalars(
                select(EconomyTransaction)
                .where(EconomyTransaction.user_id == user_id)
                .order_by(EconomyTransaction.timestamp),
            )
            transactions = list(transaction_result.all())

            ticket_result = await session.scalars(
                select(ActiveTicket)
                .where(ActiveTicket.user_id == user_id)
                .order_by(ActiveTicket.guild_id),
            )
            tickets = list(ticket_result.all())

            giveaway_result = await session.scalars(
                select(Giveaway)
                .where(Giveaway.host_id == user_id)
                .order_by(Giveaway.end_time),
            )
            giveaways = list(giveaway_result.all())

            guild_settings_result = await session.scalars(
                select(GuildSettings).order_by(GuildSettings.guild_id),
            )
            server_configuration_references = []
            for guild_settings in guild_settings_result:
                references = self._get_guild_config_user_references(
                    guild_settings.config,
                    user_id,
                )
                if references:
                    server_configuration_references.append(
                        {
                            'guild_id': str(guild_settings.guild_id),
                            **references,
                        },
                    )

            # These are moderation restrictions where this user is the target.
            # They are exported but retained during deletion for moderation
            # and abuse-prevention purposes.
            restriction_result = await session.scalars(
                select(ModerationEntry)
                .where(
                    ModerationEntry.item_type == 'user',
                    ModerationEntry.value == str(user_id),
                )
                .order_by(ModerationEntry.timestamp),
            )
            restrictions = list(restriction_result.all())

            authored_case_result = await session.scalars(
                select(GlobalChatModerationCase)
                .where(GlobalChatModerationCase.author_id == user_id)
                .order_by(GlobalChatModerationCase.created_at),
            )
            authored_cases = list(authored_case_result.all())

            reviewed_case_count = await session.scalar(
                select(func.count())
                .select_from(GlobalChatModerationCase)
                .where(GlobalChatModerationCase.reviewer_id == user_id),
            )

            moderator_action_count = await session.scalar(
                select(func.count())
                .select_from(ModerationEntry)
                .where(ModerationEntry.moderator == user_id),
            )

            preference_data: dict[str, Any] | None = None

            if preference is not None:
                data = preference.data

                if hasattr(data, 'to_dict'):
                    preference_data = data.to_dict()
                elif isinstance(data, dict):
                    preference_data = data
                else:
                    preference_data = None

            return {
                'schema_version': 1,
                'exported_at': datetime.now(UTC).isoformat(),
                'user': {
                    'discord_id': str(user_id),
                },
                'statistics': (
                    {
                        'xp': statistics.xp,
                        'total_messages': statistics.total_messages,
                        'level': statistics.level,
                    }
                    if statistics is not None
                    else None
                ),
                'daily_activity': [
                    {
                        'guild_id': str(row.guild_id),
                        'date': row.activity_date.isoformat(),
                        'message_count': row.message_count,
                        'character_count': row.character_count,
                        'xp_gained': row.xp_gained,
                    }
                    for row in daily_activity
                ],
                'profile': (
                    {
                        'description': profile.description,
                        'nickname': profile.nickname,
                        'updated_at': self._serialize_datetime(
                            profile.updated_at,
                        ),
                    }
                    if profile is not None
                    else None
                ),
                'activity': (
                    {
                        'commands_run': activity.commands_run,
                        'messages_sent': activity.messages_sent,
                        'last_active_at': self._serialize_datetime(
                            activity.last_active_at,
                        ),
                    }
                    if activity is not None
                    else None
                ),
                'preferences': preference_data,
                'economy': {
                    'account': (
                        {
                            'wallet': economy_user.wallet,
                            'bank': economy_user.bank,
                            'last_daily': economy_user.last_daily,
                            'last_work': economy_user.last_work,
                        }
                        if economy_user is not None
                        else None
                    ),
                    'inventory': [
                        {
                            'item_id': row.item_id,
                            'quantity': row.quantity,
                        }
                        for row in inventory
                    ],
                    'transactions': [
                        {
                            'type': row.tx_type,
                            'amount': row.amount,
                            'description': row.description,
                            'timestamp': row.timestamp,
                        }
                        for row in transactions
                    ],
                },
                'server_configuration_references': server_configuration_references,
                'tickets': [
                    {
                        'channel_id': str(row.channel_id),
                        'guild_id': str(row.guild_id),
                    }
                    for row in tickets
                ],
                'hosted_giveaways': [
                    {
                        'message_id': str(row.message_id),
                        'channel_id': str(row.channel_id),
                        'guild_id': str(row.guild_id),
                        'end_time': row.end_time,
                        'winners': row.winners,
                        'prize': row.prize,
                    }
                    for row in giveaways
                ],
                'moderation': {
                    'restrictions': [
                        {
                            'scope': str(row.item_scope),
                            'created_at': row.timestamp,
                            'expires_at': row.expires_at,
                            'reasons': list(row.reasons or []),
                        }
                        for row in restrictions
                    ],
                    'authored_global_chat_cases': [
                        {
                            'message_id': str(row.message_id),
                            'guild_id': str(row.guild_id),
                            'channel_id': str(row.channel_id),
                            'reason_codes': list(row.reason_codes or []),
                            'status': row.status,
                            'created_at': self._serialize_datetime(
                                row.created_at,
                            ),
                            'reviewed_at': self._serialize_datetime(
                                row.reviewed_at,
                            ),
                        }
                        for row in authored_cases
                    ],
                    'reviewed_case_count': int(reviewed_case_count or 0),
                    'moderator_action_count': int(moderator_action_count or 0),
                },
            }

    async def delete_user_data(self, user_id: int) -> dict[str, dict[str, int]]:
        """
        Delete user-owned records in one database transaction.

        Some moderation records are intentionally retained or anonymized.
        The report distinguishes those operations from actual deletions.
        """
        report: dict[str, dict[str, int]] = {
            'deleted': {},
            'anonymized': {},
            'retained': {},
        }

        async with self.async_session() as session, session.begin():
            retained_restrictions = await session.scalar(
                select(func.count())
                .select_from(ModerationEntry)
                .where(
                    ModerationEntry.item_type == 'user',
                    ModerationEntry.value == str(user_id),
                ),
            )

            report['retained']['moderation_restrictions'] = int(
                retained_restrictions or 0,
            )

            moderator_result = await session.execute(
                update(ModerationEntry)
                .where(ModerationEntry.moderator == user_id)
                .values(moderator=None),
            )
            report['anonymized']['moderator_references'] = (
                self._get_row_count(moderator_result)
            )

            # Remove reviewer attribution from cases involving other users.
            reviewer_result = await session.execute(
                update(GlobalChatModerationCase)
                .where(
                    GlobalChatModerationCase.reviewer_id == user_id,
                )
                .values(reviewer_id=None),
            )
            report['anonymized']['reviewer_references'] = (
                self._get_row_count(reviewer_result)
            )

            authored_case_result = await session.execute(
                delete(GlobalChatModerationCase).where(
                    GlobalChatModerationCase.author_id == user_id,
                ),
            )
            report['deleted']['authored_moderation_cases'] = (
                self._get_row_count(authored_case_result)
            )

            # Delete personal profile, activity, preference, statistics,
            # and economy data.
            deletion_statements = (
                (
                    'statistics',
                    delete(UserStatistics).where(
                        UserStatistics.user_id == user_id,
                    ),
                ),
                (
                    'daily_activity',
                    delete(DailyUserActivity).where(
                        DailyUserActivity.user_id == user_id,
                    ),
                ),
                (
                    'profile',
                    delete(UserProfile).where(
                        UserProfile.user_id == user_id,
                    ),
                ),
                (
                    'activity',
                    delete(UserActivity).where(
                        UserActivity.user_id == user_id,
                    ),
                ),
                (
                    'preferences',
                    delete(UserPreference).where(
                        UserPreference.user_id == user_id,
                    ),
                ),
                (
                    'economy_account',
                    delete(EconomyUser).where(
                        EconomyUser.user_id == user_id,
                    ),
                ),
                (
                    'economy_inventory',
                    delete(EconomyInventory).where(
                        EconomyInventory.user_id == user_id,
                    ),
                ),
                (
                    'economy_transactions',
                    delete(EconomyTransaction).where(
                        EconomyTransaction.user_id == user_id,
                    ),
                ),
                (
                    'tickets',
                    delete(ActiveTicket).where(
                        ActiveTicket.user_id == user_id,
                    ),
                ),
            )

            for name, statement in deletion_statements:
                result = await session.execute(statement)
                report['deleted'][name] = self._get_row_count(result)

            guild_settings_result = await session.scalars(
                select(GuildSettings).order_by(GuildSettings.guild_id),
            )
            for guild_settings in guild_settings_result:
                config = guild_settings.config
                config_data = (
                    config.to_dict() if hasattr(config, 'to_dict') else config
                )
                if not isinstance(config_data, dict):
                    continue

                removed_references = self._remove_guild_config_user_references(
                    config_data,
                    user_id,
                )
                if not removed_references:
                    continue

                guild_settings.config = GuildConfigV2.from_dict(config_data)
                for name, count in removed_references.items():
                    target = (
                        report['anonymized']
                        if name == 'guild_config_last_executor_references'
                        else report['deleted']
                    )
                    target[name] = target.get(name, 0) + count

            giveaway_result = await session.execute(
                update(Giveaway)
                .where(Giveaway.host_id == user_id)
                .values(host_id=None),
            )
            report['anonymized']['giveaway_host_references'] = (
                self._get_row_count(giveaway_result)
            )

        return report
