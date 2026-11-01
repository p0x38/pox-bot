from datetime import date

from sqlalchemy import BigInteger, Date
from sqlalchemy.orm import Mapped, mapped_column

from ...shared.bases import Base


class UserStatistics(Base):
    __tablename__ = 'user_statistics'
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_messages: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    level: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


class DailyUserActivity(Base):
    __tablename__ = 'daily_user_activity'

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    activity_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
    )

    message_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    character_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    xp_gained: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
