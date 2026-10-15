from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, BigInteger, Float, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ....shared.bases import Base


class ModerationEntry(Base):
    __tablename__ = 'moderation_entries'
    __table_args__ = (
        Index('ix_moderation_entries_scope_type', 'item_scope', 'item_type'),
    )

    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    timestamp: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=lambda: datetime.now(UTC).timestamp(),
    )
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    item_scope: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    moderator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    extras: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
