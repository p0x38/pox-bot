
from __future__ import annotations

import math
import random
from collections.abc import Sequence

from .models import Question, RobloxCandidate


class AkinatorSession:
    def __init__(
        self,
        candidates: Sequence[RobloxCandidate],
        questions: Sequence[Question],
        *,
        rng: random.Random | None = None,
    ) -> None:
        if not candidates:
            raise ValueError("At least one candidate is required.")

        if len({candidate.user_id for candidate in candidates}) != len(
            candidates
        ):
            raise ValueError("Candidate user IDs must be unique.")

        if len({question.id for question in questions}) != len(questions):
            raise ValueError("Question IDs must be unique.")

        self.candidates = list(candidates)
        self.questions = tuple(questions)
        self.asked_questions: set[str] = set()
        self._questions_by_id = {
            question.id: question for question in self.questions
        }
        self._rng = rng or random.Random()

    @property
    def remaining_count(self) -> int:
        return len(self.candidates)

    def next_question(self) -> Question | None:
        """Choose the unanswered question with the best candidate split."""
        if len(self.candidates) < 2:
            return None

        best_score = 0.0
        best_questions: list[Question] = []

        for question in self.questions:
            if not question.enabled or question.id in self.asked_questions:
                continue

            values = [
                candidate.features.get(question.feature)
                for candidate in self.candidates
            ]

            yes_count = sum(value is True for value in values)
            no_count = sum(value is False for value in values)
            known_count = yes_count + no_count

            if yes_count == 0 or no_count == 0:
                continue

            yes_probability = yes_count / known_count
            no_probability = no_count / known_count

            entropy = -(
                yes_probability * math.log2(yes_probability)
                + no_probability * math.log2(no_probability)
            )

            coverage = known_count / len(self.candidates)
            score = entropy * coverage * question.weight

            if score > best_score + 1e-9:
                best_score = score
                best_questions = [question]
            elif abs(score - best_score) <= 1e-9:
                best_questions.append(question)

        if not best_questions:
            return None

        return self._rng.choice(best_questions)

    def answer(self, question_id: str, answer: bool | None) -> int:
        """
        Record an answer and narrow the candidate pool.

        True  = Yes
        False = No
        None  = Don't know
        """
        question = self._questions_by_id.get(question_id)

        if question is None:
            raise KeyError(f"Unknown question: {question_id}")

        if not question.enabled:
            raise ValueError(f"Question is disabled: {question_id}")

        if question_id in self.asked_questions:
            raise ValueError(f"Question already answered: {question_id}")

        if answer is not None and type(answer) is not bool:
            raise TypeError("answer must be True, False, or None")

        self.asked_questions.add(question_id)

        if answer is None:
            return self.remaining_count

        self.candidates = [
            candidate
            for candidate in self.candidates
            if (
                candidate.features.get(question.feature) is None
                or candidate.features.get(question.feature) is answer
            )
        ]

        return self.remaining_count

    def make_guess(self) -> RobloxCandidate | None:
        """
        Suggest a candidate when no useful question remains.

        Returns None while more informative questions are available.
        """
        if not self.candidates or self.next_question() is not None:
            return None

        return self._rng.choice(self.candidates)

    def reject_guess(self, user_id: int) -> int:
        """Remove a rejected guess so another candidate can be tried."""
        previous_count = self.remaining_count

        self.candidates = [
            candidate
            for candidate in self.candidates
            if candidate.user_id != user_id
        ]

        if self.remaining_count == previous_count:
            raise KeyError(f"Candidate not found: {user_id}")

        return self.remaining_count
