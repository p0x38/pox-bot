import orjson
from sqlalchemy import BigInteger, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from src.bases import Base
from src.models.guild_settings_v2 import GuildConfigV2


class GuildConfigType(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):  # noqa: ARG002
        if isinstance(value, GuildConfigV2):
            return orjson.dumps(value.to_dict()).decode('utf-8')
        return value

    def process_result_value(self, value, dialect):  # noqa: ARG002
        return GuildConfigV2.from_dict(orjson.loads(value)) if value else GuildConfigV2()


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    config: Mapped[GuildConfigV2] = mapped_column(GuildConfigType)


class ActiveTicket(Base):
    __tablename__ = "active_tickets"
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
