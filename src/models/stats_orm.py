from datetime import datetime

from sqlalchemy import BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from src.bases import Base


class UserStatistics(Base):
    __tablename__ = "user_statistics"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    xp: Mapped[int] = mapped_column(BigInteger, default=0)
    total_messages: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=1)


class MessageCache(Base):
    __tablename__ = "m_cache"
    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    author_id: Mapped[int] = mapped_column(BigInteger)
    content: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
