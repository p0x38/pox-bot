from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    delete,
    insert,
    select,
)

from ...shared.abc.base_database import BaseDatabase
from .model import MarkovModel


class MarkovStorage(Protocol):
    """Persistence interface for Markov models."""

    async def load(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None: ...

    async def save(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None: ...

    async def clear(
        self,
        guild_id: int,
    ) -> None: ...


class InMemoryMarkovStorage:
    """In-memory Markov storage."""

    def __init__(self) -> None:
        self.data: dict[
            int,
            dict[tuple[str, ...], Counter[str]],
        ] = {}

        self.metadata: dict[
            int,
            tuple[int, int, int],
        ] = {}

    async def load(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None:
        model.clear()

        metadata = self.metadata.get(guild_id)

        if metadata is not None:
            order, message_count, token_count = metadata

            if order != model.order:
                return

            model.message_count = message_count
            model.token_count = token_count

        guild_data = self.data.get(guild_id)

        if not guild_data:
            return

        for state, transitions in guild_data.items():
            model.transitions[state].update(transitions)

    async def save(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None:
        self.metadata[guild_id] = (
            model.order,
            model.message_count,
            model.token_count,
        )

        self.data[guild_id] = {
            state: Counter(transitions)
            for state, transitions in model.transitions.items()
        }

    async def clear(
        self,
        guild_id: int,
    ) -> None:
        self.data.pop(guild_id, None)
        self.metadata.pop(guild_id, None)


class MarkovDatabase(BaseDatabase, MarkovStorage):
    """SQLAlchemy-backed persistent Markov storage."""

    metadata = MetaData()

    model_table = Table(
        'markov_models',
        metadata,
        Column(
            'guild_id',
            BigInteger,
            primary_key=True,
        ),
        Column(
            'order',
            Integer,
            nullable=False,
        ),
        Column(
            'message_count',
            Integer,
            nullable=False,
        ),
        Column(
            'token_count',
            Integer,
            nullable=False,
        ),
    )

    transition_table = Table(
        'markov_transitions',
        metadata,
        Column(
            'guild_id',
            BigInteger,
            primary_key=True,
        ),
        Column(
            'state',
            String,
            primary_key=True,
        ),
        Column(
            'next_token',
            String,
            primary_key=True,
        ),
        Column(
            'count',
            Integer,
            nullable=False,
        ),
    )

    @staticmethod
    def _serialize_state(
        state: Sequence[str],
    ) -> str:
        """Serialize a Markov state into compact JSON."""
        return json.dumps(
            list(state),
            ensure_ascii=False,
            separators=(',', ':'),
        )

    @staticmethod
    def _deserialize_state(
        value: str,
    ) -> tuple[str, ...]:
        """Deserialize a Markov state from JSON."""
        result = json.loads(value)

        if not isinstance(result, list):
            raise ValueError(
                'Invalid Markov state stored in database',
            )

        return tuple(str(token) for token in result)

    async def on_load(self) -> None:
        """Create Markov tables if they do not exist."""
        async with self.engine.begin() as connection:
            await connection.run_sync(
                self.metadata.create_all,
            )

        self.logger.debug('Initialized Markov tables')

    async def load(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None:
        """Load a guild's Markov model."""
        model.clear()

        async with self.get_session() as session:
            model_result = await session.execute(
                select(
                    self.model_table.c.order,
                    self.model_table.c.message_count,
                    self.model_table.c.token_count,
                ).where(
                    self.model_table.c.guild_id == guild_id,
                ),
            )

            model_row = model_result.first()

            if model_row is None:
                return

            mapping = model_row._mapping

            stored_order: int = mapping['order']

            if stored_order != model.order:
                self.logger.warning(
                    (
                        'Ignoring Markov model for guild %s: '
                        'stored order=%s, requested order=%s'
                    ),
                    guild_id,
                    stored_order,
                    model.order,
                )
                return

            model.message_count = mapping['message_count']
            model.token_count = mapping['token_count']

            result = await session.execute(
                select(
                    self.transition_table.c.state,
                    self.transition_table.c.next_token,
                    self.transition_table.c.count,
                ).where(
                    self.transition_table.c.guild_id == guild_id,
                ),
            )

            for row in result:
                mapping = row._mapping

                state = mapping['state']
                next_token = mapping['next_token']
                count = mapping['count']

                model.transitions[
                    self._deserialize_state(state)
                ][next_token] = count

    async def save(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None:
        """Save a guild's complete Markov model."""
        async with self.get_session() as session, session.begin():
            await session.execute(
                delete(self.transition_table).where(
                    self.transition_table.c.guild_id == guild_id,
                ),
            )

            await session.execute(
                delete(self.model_table).where(
                    self.model_table.c.guild_id == guild_id,
                ),
            )

            await session.execute(
                insert(self.model_table).values(
                    guild_id=guild_id,
                    order=model.order,
                    message_count=model.message_count,
                    token_count=model.token_count,
                ),
            )

            rows = [
                {
                    'guild_id': guild_id,
                    'state': self._serialize_state(state),
                    'next_token': next_token,
                    'count': count,
                }
                for state, transitions in model.transitions.items()
                for next_token, count in transitions.items()
            ]

            if rows:
                await session.execute(
                    insert(self.transition_table),
                    rows,
                )

    async def clear(
        self,
        guild_id: int,
    ) -> None:
        """Delete a guild's Markov model."""
        async with self.get_session() as session, session.begin():
            await session.execute(
                delete(self.transition_table).where(
                    self.transition_table.c.guild_id == guild_id,
                ),
            )

            await session.execute(
                delete(self.model_table).where(
                    self.model_table.c.guild_id == guild_id,
                ),
            )
