from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from ...shared.bases import Base


class Giveaway(Base):
    __tablename__ = 'active_giveaways'

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    end_time: Mapped[int] = mapped_column(BigInteger)
    winners: Mapped[int] = mapped_column(BigInteger)
    prize: Mapped[str] = mapped_column()
    host_id: Mapped[int] = mapped_column(BigInteger)
