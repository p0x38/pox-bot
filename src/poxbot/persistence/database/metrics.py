from typing import Any

from discord import DMChannel, GroupChannel, Guild
from discord.abc import GuildChannel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...shared.abc.base_database import BaseDatabase
from ...shared.bases.base_orm_model import Base
from ...shared.enums.types import ObjectType, PlatformType
from ..models.orm.metrics import MetricsORM


class MetricsDatabase(BaseDatabase):
    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.debug("Initialized tables")

    def _resolve_target(self, target: Any) -> tuple[ObjectType, str]:
        if isinstance(target, Guild):
            return ObjectType.GUILD, str(target.id)
        if isinstance(target, GuildChannel) or (hasattr(target, 'guild') and target.guild):
            return ObjectType.GUILD, str(target.guild.id)
        if isinstance(target, DMChannel):
            return ObjectType.DM, str(target.id)
        if isinstance(target, GroupChannel):
            return ObjectType.GROUP, str(target.id)
        if isinstance(target, (int, str)):
            return ObjectType.UNKNOWN, str(target)
        
        target_id = getattr(target, 'id', 'unknown')
        return ObjectType.UNKNOWN, str(target_id)
    
    async def increment_interaction(self, target: Any, amount: int = 1) -> None:
        obj_type, target_id = self._resolve_target(target)
        
        async with self.get_session() as session, session.begin():
            if "postgresql" in self.engine.url.drivername:
                stmt = pg_insert(MetricsORM).values(
                    platform=PlatformType.DISCORD,
                    object_type=obj_type,
                    target_id=target_id,
                    interaction_count=amount,
                ).on_conflict_do_update(
                    constraint="metrics_data_pkey",
                    set_={"interaction_count": MetricsORM.interaction_count + amount},
                )
                await session.execute(stmt)
            else:
                stmt = select(MetricsORM).where(
                    MetricsORM.platform == PlatformType.DISCORD,
                    MetricsORM.object_type == obj_type,
                    MetricsORM.target_id == target_id,
                )
                result = await session.execute(stmt)
                record = result.scalar_one_or_none()
                
                if record:
                    record.interaction_count += amount
                else:
                    new_record = MetricsORM(
                        platform=PlatformType.DISCORD,
                        object_type=obj_type,
                        target_id=target_id,
                        interaction_count=amount,
                    )
                    session.add(new_record)
    
    async def increment_message(self, guild: Guild, amount: int = 1) -> None:
        async with self.get_session() as session, session.begin():
            stmt = select(MetricsORM).where(
                MetricsORM.platform == PlatformType.DISCORD,
                MetricsORM.object_type == ObjectType.GUILD,
                MetricsORM.target_id == str(guild.id),
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                record.message_count += 1
            else:
                new_record = MetricsORM(
                    platform=PlatformType.DISCORD,
                    object_type=ObjectType.GUILD,
                    target_id=str(guild.id),
                    message_count=amount,
                )
                session.add(new_record)
    
    async def increment_message_by_id(self, guild_id: str | int, amount: int = 1) -> None:
        async with self.get_session() as session, session.begin():
            stmt = select(MetricsORM).where(
                MetricsORM.platform == PlatformType.DISCORD,
                MetricsORM.object_type == ObjectType.GUILD,
                MetricsORM.target_id == guild_id,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                record.message_count += amount
            else:
                new_record = MetricsORM(
                    platform=PlatformType.DISCORD,
                    object_type=ObjectType.GUILD,
                    target_id=guild_id,
                    message_count=amount,
                )
                session.add(new_record)
