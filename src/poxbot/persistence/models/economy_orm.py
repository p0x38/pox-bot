from datetime import datetime

from pytz import UTC
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ...shared.bases import Base


class EconomyUser(Base):
    __tablename__ = 'economy_users'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    wallet: Mapped[int] = mapped_column(BigInteger, default=0)
    bank: Mapped[int] = mapped_column(BigInteger, default=0)
    last_daily: Mapped[float] = mapped_column(nullable=True)
    last_work: Mapped[float] = mapped_column(nullable=True)


class EconomyItem(Base):
    __tablename__ = 'economy_items'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column(nullable=True)


class EconomyInventory(Base):
    __tablename__ = 'economy_inventory'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[str] = mapped_column(primary_key=True)
    quantity: Mapped[int] = mapped_column(BigInteger, default=0)


class EconomyTransaction(Base):
    __tablename__ = 'economy_transactions'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    tx_type: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column()
    timestamp: Mapped[float] = mapped_column(
        default=lambda: datetime.now(UTC).timestamp(),
    )
