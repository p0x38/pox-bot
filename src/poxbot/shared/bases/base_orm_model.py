from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Serve as the declarative base class for all SQLAlchemy ORM models.

    This class tracks and maps all database tables defined as subclasses
    throughput the application using SQLAlchemy's modern Declarative system.
    """

    pass
