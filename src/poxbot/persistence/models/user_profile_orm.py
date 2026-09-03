from datetime import datetime

from sqlalchemy import BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from ...shared.bases import Base


class UserProfile(Base):
    __tablename__ = 'user_profiles'
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    description: Mapped[str | None] = mapped_column(nullable=True)
    nickname: Mapped[str | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserActivity(Base):
    __tablename__ = 'user_activity'
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commands_run: Mapped[int] = mapped_column(BigInteger, default=0)
    messages_sent: Mapped[int] = mapped_column(BigInteger, default=0)
    last_active_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
