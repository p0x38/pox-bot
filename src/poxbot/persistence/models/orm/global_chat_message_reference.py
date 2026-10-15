from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ....shared.bases import Base


class GlobalChatMessageReference(Base):
    __tablename__ = 'global_chat_message_references'
    __table_args__ = (
        UniqueConstraint(
            'origin_message_id',
            'replica_guild_id',
            name='uq_global_chat_reference_origin_guild',
        ),
    )

    replica_message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    origin_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    replica_guild_id: Mapped[int] = mapped_column(BigInteger)
    replica_channel_id: Mapped[int] = mapped_column(BigInteger)
