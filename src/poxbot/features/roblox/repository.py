from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from .models import CandidateData, QuestionData


class RobloxDataRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _load_json(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename

        with path.open('r', encoding='utf-8') as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(f'{filename} must contain a JSON object.')

        return data

    def load_questions(self) -> QuestionData:
        try:
            document = TypeAdapter(QuestionData).validate_python(
                self._load_json('questions.json'),
            )
        except ValidationError as exc:
            raise ValueError('Invalid questions.json') from exc

        question_ids = [question.id for question in document.questions]

        if len(question_ids) != len(set(question_ids)):
            raise ValueError('Question IDs must be unique.')

        return document

    def load_candidates(self) -> CandidateData:
        try:
            document = TypeAdapter(CandidateData).validate_python(
                self._load_json('candidates.json'),
            )
        except ValidationError as exc:
            raise ValueError('Invalid candidates.json') from exc

        user_ids = [candidate.user_id for candidate in document.candidates]

        if len(user_ids) != len(set(user_ids)):
            raise ValueError('Candidate user IDs must be unique.')

        return document

    def load_game_data(self) -> tuple[QuestionData, CandidateData]:
        """Load and validate the complete Akinator dataset."""
        questions = self.load_questions()
        candidates = self.load_candidates()

        if not candidates.candidates:
            raise ValueError('At least one candidate is required.')

        for question in questions.questions:
            if not question.enabled:
                continue

            values = {
                candidate.features.get(question.feature)
                for candidate in candidates.candidates
            }

            if True not in values or False not in values:
                raise ValueError(
                    f'Question {question.id!r} cannot distinguish '
                    f'candidates using feature {question.feature!r}.'
                )

        return questions, candidates
