from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from ....shared.bases import Base
from ....shared.enums import ObjectType, PlatformType


class MetricsORM(Base):
    __tablename__ = 'metrics_data'

    platform: Mapped[PlatformType] = mapped_column(Enum(PlatformType), primary_key=True)
    object_type: Mapped[ObjectType] = mapped_column(Enum(ObjectType), primary_key=True)
    target_id: Mapped[str] = mapped_column(String, primary_key=True)

    interaction_count: Mapped[int] = mapped_column(BigInteger, default=0)
    message_count: Mapped[int] = mapped_column(BigInteger, default=0)
