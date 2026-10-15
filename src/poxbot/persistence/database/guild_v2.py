from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import orjson
from discord import Member, User
from sqlalchemy import bindparam, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...core.cache import Cache
from ...shared.bases import BaseDatabase
from ...shared.bases.base_orm_model import Base
from ..models.global_chat_moderation_orm import GlobalChatModerationCase
from ..models.guild_settings_v2 import GuildConfigV2
from ..models.guild_settings_v2_orm import ActiveTicket, GuildSettings
from ..models.orm.moderation import ModerationEntry

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class GuildSettingsDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str):
        super().__init__(bot, dsn)
        self._cache = Cache(ttl=500)
        self._moderation_entries_cache = Cache(ttl=5)

    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self._migrate_legacy_moderation_entries()
        self.logger.debug('Initialized tables')

    @staticmethod
    def _legacy_timestamp(entry: dict) -> float:
        timestamp = entry.get('timestamp')
        if timestamp is None:
            return datetime.now(UTC).timestamp()

        try:
            return float(timestamp)
        except (TypeError, ValueError):
            return datetime.now(UTC).timestamp()

    @staticmethod
    def _legacy_expiry(entry: dict) -> float | None:
        try:
            expires_at = float(entry.get('expires_at', -1))
        except (TypeError, ValueError):
            return None

        return None if expires_at < 0 else expires_at

    @staticmethod
    def _legacy_moderator(entry: dict) -> int | None:
        moderator = entry.get('executed_by', entry.get('moderator'))

        if moderator is None:
            return None

        try:
            return int(moderator)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _legacy_reasons(entry: dict) -> list[str]:
        reasons = entry.get('reasons')
        if isinstance(reasons, list):
            return [str(reason) for reason in reasons if reason is not None]

        reason = entry.get('reason')
        return [str(reason)] if reason else []

    async def _migrate_legacy_moderation_entries(self) -> None:
        """Move blacklist arrays out of guild_settings.config atomically."""
        migrated_count = 0

        async with self.async_session() as session, session.begin():
            result = await session.execute(
                text('SELECT guild_id, config FROM guild_settings'),
            )

            for row in result.mappings():
                guild_id = int(row['guild_id'])
                config = row['config']

                if isinstance(config, str):
                    try:
                        config = orjson.loads(config)
                    except orjson.JSONDecodeError:
                        continue
                elif isinstance(config, (bytes, bytearray, memoryview)):
                    try:
                        config = orjson.loads(bytes(config))
                    except orjson.JSONDecodeError:
                        continue

                if not isinstance(config, dict):
                    continue

                features = config.get('features', {})
                if not isinstance(features, dict):
                    continue
                filtering = features.get('filtering', {})
                if not isinstance(filtering, dict):
                    continue
                filters = filtering.get('filters', {})
                if not isinstance(filters, dict):
                    continue

                changed = False
                word_config = filters.get('word')
                if isinstance(word_config, dict) and 'blacklists' in word_config:
                    legacy_entries = word_config['blacklists'] or []
                    if not isinstance(legacy_entries, list):
                        raise ValueError(
                            f'Invalid legacy word blacklist for guild {guild_id}',
                        )

                    for legacy in legacy_entries:
                        if not isinstance(legacy, dict):
                            raise ValueError(
                                f'Invalid legacy word entry for guild {guild_id}',
                            )

                        trigger = str(legacy.get('trigger') or '')
                        try:
                            match_type = int(legacy.get('type', 0))
                        except (TypeError, ValueError):
                            match_type = 0

                        self._add_legacy_moderation_entry(
                            session,
                            ModerationEntry(
                                item_type='word',
                                value=trigger,
                                item_scope=guild_id,
                                timestamp=self._legacy_timestamp(legacy),
                                expires_at=self._legacy_expiry(legacy),
                                reasons=self._legacy_reasons(legacy),
                                moderator=self._legacy_moderator(legacy),
                                extras={
                                    'match_type': match_type,
                                    'case_insensitive': bool(
                                        legacy.get('case_insensitive', True),
                                    ),
                                    **(
                                        {'legacy_id': str(legacy['id'])}
                                        if legacy.get('id') is not None
                                        else {}
                                    ),
                                },
                            ),
                        )
                        migrated_count += 1

                    word_config.pop('blacklists', None)
                    changed = True

                anti_join_config = filters.get('anti_join')
                if (
                    isinstance(anti_join_config, dict)
                    and 'blacklists' in anti_join_config
                ):
                    legacy_entries = anti_join_config['blacklists'] or []
                    if not isinstance(legacy_entries, list):
                        raise ValueError(
                            f'Invalid legacy anti-join blacklist for guild {guild_id}',
                        )

                    for legacy in legacy_entries:
                        if not isinstance(legacy, dict) or 'target_id' not in legacy:
                            raise ValueError(
                                f'Invalid legacy user blacklist for guild {guild_id}',
                            )

                        raw_scope = legacy.get('scope', 0)
                        if isinstance(raw_scope, str):
                            scope_names = {'SERVER': 0, 'GLOBAL': 1, 'BOT': 2}
                            try:
                                scope_value = int(raw_scope)
                            except ValueError:
                                scope_value = scope_names.get(raw_scope.upper(), 0)
                        else:
                            try:
                                scope_value = int(raw_scope)
                            except (TypeError, ValueError):
                                scope_value = 0

                        item_scope = {-2: -2, -1: -1, 1: -1, 2: -2}.get(
                            scope_value,
                            guild_id,
                        )
                        target_id = str(legacy['target_id'])

                        self._add_legacy_moderation_entry(
                            session,
                            ModerationEntry(
                                item_type='user',
                                value=target_id,
                                item_scope=item_scope,
                                timestamp=self._legacy_timestamp(legacy),
                                expires_at=self._legacy_expiry(legacy),
                                reasons=self._legacy_reasons(legacy),
                                moderator=self._legacy_moderator(legacy),
                                extras={},
                            ),
                        )
                        migrated_count += 1

                    anti_join_config.pop('blacklists', None)
                    changed = True

                if changed:
                    statement = text(
                        'UPDATE guild_settings SET config = :config '
                        'WHERE guild_id = :guild_id',
                    ).bindparams(
                        bindparam(
                            'config', type_=GuildSettings.__table__.c.config.type
                        ),
                    )
                    await session.execute(
                        statement,
                        {'config': config, 'guild_id': guild_id},
                    )

        if migrated_count:
            self.logger.info(
                'Migrated %d legacy moderation entries into moderation_entries',
                migrated_count,
            )

    @staticmethod
    def _add_legacy_moderation_entry(
        session: AsyncSession, entry: ModerationEntry
    ) -> None:
        session.add(entry)

    async def get_config(self, guild_id: int) -> GuildConfigV2:
        async with self.async_session() as session, session.begin():
            result = await session.get(GuildSettings, guild_id)
            return result.config if result else GuildConfigV2()

    async def update_config(self, guild_id: int, config: GuildConfigV2):
        async with self.async_session() as session, session.begin():
            db_record = await session.get(GuildSettings, guild_id)

            if db_record:
                db_record.config = config

                flag_modified(db_record, 'config')
            else:
                db_record = GuildSettings(guild_id=guild_id, config=config)
                session.add(db_record)

        self._cache.set(guild_id, config)

    @staticmethod
    def _moderation_cache_key(item_type: str, scopes: tuple[int, ...]) -> str:
        scope_key = ','.join(str(scope) for scope in scopes)
        return f'moderation_entries:{item_type}:{scope_key}'

    async def get_moderation_entries(
        self,
        item_type: str,
        item_scope: int | tuple[int, ...],
    ) -> list[ModerationEntry]:
        if item_type not in {'user', 'word'}:
            raise ValueError(f'Unsupported moderation item type: {item_type}')

        scopes = (
            (item_scope,)
            if isinstance(item_scope, int)
            else tuple(sorted(set(item_scope)))
        )
        if not scopes:
            return []

        cache_key = self._moderation_cache_key(item_type, scopes)
        cached = self._moderation_entries_cache.get(cache_key)
        if cached is not None:
            return cached

        async with self.async_session() as session:
            statement = (
                select(ModerationEntry)
                .where(
                    ModerationEntry.item_type == item_type,
                    ModerationEntry.item_scope.in_(scopes),
                )
                .order_by(ModerationEntry.timestamp)
            )
            result = await session.execute(statement)
            entries = list(result.scalars())

        self._moderation_entries_cache.set(cache_key, entries)
        return entries

    async def add_moderation_entry(
        self,
        *,
        item_type: str,
        value: str,
        item_scope: int,
        reasons: list[str] | None = None,
        expires_at: float | None = None,
        moderator: int | None = None,
        extras: dict[str, object] | None = None,
        timestamp: float | None = None,
    ) -> ModerationEntry:
        if item_type not in {'user', 'word'}:
            raise ValueError(f'Unsupported moderation item type: {item_type}')

        entry = ModerationEntry(
            item_type=item_type,
            value=value,
            item_scope=item_scope,
            timestamp=(
                timestamp if timestamp is not None else datetime.now(UTC).timestamp()
            ),
            expires_at=expires_at,
            reasons=list(reasons or []),
            moderator=moderator,
            extras=dict(extras or {}),
        )
        async with self.async_session() as session, session.begin():
            session.add(entry)
            await session.flush()

        self._moderation_entries_cache.clear()
        return entry

    async def remove_moderation_entries(
        self,
        *,
        item_type: str,
        item_scope: int,
        query: str,
    ) -> bool:
        entries = await self.get_moderation_entries(item_type, item_scope)
        matches = [
            entry
            for entry in entries
            if (
                entry.value == query
                or str(entry.item_id).startswith(query)
                or (entry.extras or {}).get('legacy_id') == query
            )
        ]
        if not matches:
            return False

        async with self.async_session() as session, session.begin():
            await session.execute(
                delete(ModerationEntry).where(
                    ModerationEntry.item_id.in_([entry.item_id for entry in matches]),
                ),
            )

        self._moderation_entries_cache.clear()
        return True

    async def create_ticket_record(self, channel_id: int, user_id: int, guild_id: int):
        async with self.async_session() as session, session.begin():
            session.add(
                ActiveTicket(channel_id=channel_id, user_id=user_id, guild_id=guild_id),
            )

    async def create_global_chat_moderation_case(
        self,
        *,
        message_id: int,
        guild_id: int,
        channel_id: int,
        author_id: int,
        reason_codes: list[str],
        message_fingerprint: str,
    ) -> None:
        async with self.async_session() as session, session.begin():
            if await session.get(GlobalChatModerationCase, message_id):
                return
            session.add(
                GlobalChatModerationCase(
                    message_id=message_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    author_id=author_id,
                    reason_codes=reason_codes,
                    message_fingerprint=message_fingerprint,
                ),
            )

    async def get_pending_global_chat_moderation_cases(
        self,
        guild_id: int,
        limit: int = 10,
    ) -> list[GlobalChatModerationCase]:
        async with self.async_session() as session:
            statement = (
                select(GlobalChatModerationCase)
                .where(
                    GlobalChatModerationCase.guild_id == guild_id,
                    GlobalChatModerationCase.status == 'pending',
                )
                .order_by(GlobalChatModerationCase.created_at)
                .limit(limit)
            )
            result = await session.execute(statement)
            return list(result.scalars())

    async def get_global_chat_moderation_case(
        self,
        guild_id: int,
        message_id: int,
    ) -> GlobalChatModerationCase | None:
        async with self.async_session() as session:
            case = await session.get(GlobalChatModerationCase, message_id)
            if case is None or case.guild_id != guild_id:
                return None
            return case

    async def resolve_global_chat_moderation_case(
        self,
        *,
        guild_id: int,
        message_id: int,
        status: str,
        reviewer_id: int,
    ) -> bool:
        if status not in {'approved', 'denied', 'stale'}:
            raise ValueError(f'Invalid moderation case status: {status}')

        async with self.async_session() as session, session.begin():
            statement = (
                update(GlobalChatModerationCase)
                .where(
                    GlobalChatModerationCase.guild_id == guild_id,
                    GlobalChatModerationCase.message_id == message_id,
                    GlobalChatModerationCase.status == 'pending',
                )
                .values(
                    status=status,
                    reviewer_id=reviewer_id,
                    reviewed_at=datetime.now(UTC),
                )
                .returning(GlobalChatModerationCase.message_id)
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none() is not None

    async def find_random_partner(self, requester_guild_id: int) -> int | None:
        async with self.async_session() as session, session.begin():
            stmt = select(GuildSettings.guild_id).where(
                GuildSettings.guild_id != requester_guild_id,
            )

            if 'sqlite' in self.engine.url.drivername:
                stmt = stmt.where(
                    func.json_extract(
                        GuildSettings.config, '$.features.userphone.status'
                    )
                    == 1,
                )
            else:
                stmt = stmt.where(
                    GuildSettings.config['features']['userphone']['status'].as_integer()
                    == 1,
                )

            stmt = stmt.limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def ban_user(
        self,
        user: Member | User,
        duration: timedelta,
        reasons: list[str] | None = None,
    ):
        pass
