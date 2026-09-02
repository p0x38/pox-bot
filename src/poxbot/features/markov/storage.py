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
from .model import MarkovModel, MarkovModelKey


class MarkovStorage(Protocol):
    """Persistence interface for Markov models."""

    async def load(
        self,
        key: MarkovModelKey,
        model: MarkovModel,
    ) -> None: ...

    async def save(
        self,
        key: MarkovModelKey,
        model: MarkovModel,
    ) -> None: ...

    async def clear(
        self,
        key: MarkovModelKey,
    ) -> None: ...


class InMemoryMarkovStorage:
    """In-memory Markov storage."""

    def __init__(self) -> None:
        self.data: dict[
            MarkovModelKey,
            dict[tuple[str, ...], Counter[str]],
        ] = {}

        self.metadata: dict[
            MarkovModelKey,
            tuple[int, int, int],
        ] = {}

    async def load(
        self,
        key: MarkovModelKey,
        model: MarkovModel,
    ) -> None:
        """Load a Markov model from memory."""
        model.clear()

        metadata = self.metadata.get(key)

        if metadata is not None:
            order, message_count, token_count = metadata

            if order != model.order:
                return

            model.message_count = message_count
            model.token_count = token_count

        model_data = self.data.get(key)

        if not model_data:
            return

        for state, transitions in model_data.items():
            model.transitions[state].update(transitions)

    async def save(
        self,
        key: MarkovModelKey,
        model: MarkovModel,
    ) -> None:
        """Save a Markov model to memory."""
        self.metadata[key] = (
            model.order,
            model.message_count,
            model.token_count,
        )

        self.data[key] = {
            state: Counter(transitions)
            for state, transitions in model.transitions.items()
        }

    async def clear(
        self,
        key: MarkovModelKey,
    ) -> None:
        """Delete a Markov model from memory."""
        self.data.pop(key, None)
        self.metadata.pop(key, None)


class MarkovDatabase(BaseDatabase, MarkovStorage):
    """SQLAlchemy-backed persistent Markov storage."""

    metadata = MetaData()

    model_table = Table(
        'markov_models',
        metadata,
        Column(
            'scope',
            String(16),
            primary_key=True,
            nullable=False,
        ),
        Column(
            'scope_id',
            BigInteger,
            primary_key=True,
            nullable=False,
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
            'scope',
            String(16),
            primary_key=True,
            nullable=False,
        ),
        Column(
            'scope_id',
            BigInteger,
            primary_key=True,
            nullable=False,
        ),
        Column(
            'state',
            String,
            primary_key=True,
            nullable=False,
        ),
        Column(
            'next_token',
            String,
            primary_key=True,
            nullable=False,
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

    @staticmethod
    def _scope_values(
        key: MarkovModelKey,
    ) -> dict[str, str | int]:
        """Convert a model key into database values."""
        return {
            'scope': key.scope.value,
            'scope_id': key.scope_id,
        }

    async def on_load(self) -> None:
        """Create Markov tables if they do not exist."""
        async with self.engine.begin() as connection:
            await connection.run_sync(
                self.metadata.create_all,
            )

        self.logger.debug('Initialized Markov tables')

    async def load(
        self,
        key: MarkovModelKey,
        model: MarkovModel,
    ) -> None:
        """Load a Markov model from the database."""
        model.clear()

        values = self._scope_values(key)

        async with self.get_session() as session:
            model_result = await session.execute(
                select(
                    self.model_table.c.order,
                    self.model_table.c.message_count,
                    self.model_table.c.token_count,
                ).where(
                    self.model_table.c.scope == values['scope'],
                    self.model_table.c.scope_id == values['scope_id'],
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
                        'Ignoring Markov model for %s/%s: '
                        'stored order=%s, requested order=%s'
                    ),
                    key.scope.value,
                    key.scope_id,
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
                    self.transition_table.c.scope == values['scope'],
                    self.transition_table.c.scope_id == values['scope_id'],
                ),
            )

            for row in result:
                mapping = row._mapping

                state = self._deserialize_state(
                    mapping['state'],
                )
                next_token = mapping['next_token']
                count = mapping['count']

                model.transitions[state][next_token] = count

    async def save(
        self,
        key: MarkovModelKey,
        model: MarkovModel,
    ) -> None:
        """Save a Markov model to the database."""
        values = self._scope_values(key)

        async with self.get_session() as session, session.begin():
            await session.execute(
                delete(self.transition_table).where(
                    self.transition_table.c.scope == values['scope'],
                    self.transition_table.c.scope_id == values['scope_id'],
                ),
            )

            await session.execute(
                delete(self.model_table).where(
                    self.model_table.c.scope == values['scope'],
                    self.model_table.c.scope_id == values['scope_id'],
                ),
            )

            await session.execute(
                insert(self.model_table).values(
                    **values,
                    order=model.order,
                    message_count=model.message_count,
                    token_count=model.token_count,
                ),
            )

            rows = [
                {
                    **values,
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
        key: MarkovModelKey,
    ) -> None:
        """Delete a Markov model from the database."""
        values = self._scope_values(key)

        async with self.get_session() as session, session.begin():
            await session.execute(
                delete(self.transition_table).where(
                    self.transition_table.c.scope == values['scope'],
                    self.transition_table.c.scope_id == values['scope_id'],
                ),
            )

            await session.execute(
                delete(self.model_table).where(
                    self.model_table.c.scope == values['scope'],
                    self.model_table.c.scope_id == values['scope_id'],
                ),
            )
