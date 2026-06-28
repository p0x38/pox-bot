import orjson
from sqlalchemy import BigInteger, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from src.bases import Base

from .user_settings import SettingsData


class SettingsDataType(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):  # noqa: ARG002
        if isinstance(value, SettingsData):
            return orjson.dumps(value.to_dict()).decode('utf-8')
        return value

    def process_result_value(self, value, dialect):  # noqa: ARG002
        return SettingsData.from_dict(orjson.loads(value)) if value else SettingsData


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data: Mapped[SettingsData] = mapped_column(SettingsDataType)
