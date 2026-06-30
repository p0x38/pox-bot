from typing import Any

import orjson
from sqlalchemy import BigInteger, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.orm import Mapped, mapped_column

from src.bases import Base
from src.models.guild_settings_v2 import GuildConfigV2


class GuildConfigType(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ARG002
        if isinstance(value, GuildConfigV2):
            return orjson.loads(orjson.dumps(value.to_dict()))
        if isinstance(value, dict):
            return value
        if isinstance(value, (str, bytes, bytearray, memoryview)):
            try:
                return orjson.loads(value)
            except Exception:
                return {}
        return value

    def process_result_value(self, value, dialect):  # noqa: ARG002
        if value is None or value == "":
            return MutableGuildConfig.coerce(self, GuildConfigV2())

        if isinstance(value, dict):
            try:
                return MutableGuildConfig.coerce(self, GuildConfigV2.from_dict(value))
            except Exception:
                return MutableGuildConfig.coerce(self, GuildConfigV2())

        if isinstance(value, (str, bytes, bytearray, memoryview)):
            try:
                if isinstance(value, str) and not value.strip():
                    return MutableGuildConfig.coerce(self, GuildConfigV2())
                return MutableGuildConfig.coerce(self, GuildConfigV2.from_dict(orjson.loads(value)))
            except Exception:
                return MutableGuildConfig.coerce(self, GuildConfigV2())

        return MutableGuildConfig.coerce(self, GuildConfigV2())


class MutableGuildConfig(Mutable, GuildConfigV2):
    @classmethod
    def coerce(cls, key: Any, value: Any) -> Any:
        if not isinstance(value, MutableGuildConfig):
            if isinstance(value, GuildConfigV2):
                try:
                    data = value.to_dict()
                    nu = cls.from_dict(data)
                    return nu
                except Exception:
                    nu = cls()
                    nu.__dict__.update(value.__dict__)
            return super().coerce(key, value)
        return value

    def __setattr__(self, name: str, value):
        super().__setattr__(name, value)
        self.changed()


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    config: Mapped[GuildConfigV2] = mapped_column(MutableGuildConfig.as_mutable(GuildConfigType))


class ActiveTicket(Base):
    __tablename__ = "active_tickets"
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
