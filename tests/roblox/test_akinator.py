import random

import pytest

from poxbot.features.roblox.akinator import AkinatorSession
from poxbot.features.roblox.models import Question, RobloxCandidate


def _candidate(user_id: int, has_hat: bool | None) -> RobloxCandidate:
    return RobloxCandidate(
        user_id=user_id,
        username=f'user{user_id}',
        display_name=f'User {user_id}',
        features={'has_hat': has_hat},
    )


def test_next_question_selects_a_useful_question() -> None:
    question = Question(
        id='hat',
        feature='has_hat',
        prompt='akinator.questions.hat',
    )

    session = AkinatorSession(
        candidates=[
            _candidate(1, True),
            _candidate(2, False),
            _candidate(3, None),
        ],
        questions=[question],
        rng=random.Random(0),
    )

    assert session.next_question() == question


def test_answer_keeps_candidates_with_unknown_features() -> None:
    session = AkinatorSession(
        candidates=[
            _candidate(1, True),
            _candidate(2, False),
            _candidate(3, None),
        ],
        questions=[
            Question(
                id='hat',
                feature='has_hat',
                prompt='akinator.questions.hat',
            ),
        ],
    )

    assert session.answer('hat', True) == 2
    assert [candidate.user_id for candidate in session.candidates] == [1, 3]


def test_dont_know_does_not_filter_candidates() -> None:
    session = AkinatorSession(
        candidates=[
            _candidate(1, True),
            _candidate(2, False),
        ],
        questions=[
            Question(
                id='hat',
                feature='has_hat',
                prompt='akinator.questions.hat',
            ),
        ],
    )

    assert session.answer('hat', None) == 2
    assert session.next_question() is None


def test_reject_guess_removes_candidate() -> None:
    session = AkinatorSession(
        candidates=[
            _candidate(1, True),
            _candidate(2, False),
        ],
        questions=[
            Question(
                id='hat',
                feature='has_hat',
                prompt='akinator.questions.hat',
            ),
        ],
    )

    session.answer('hat', None)
    guess = session.make_guess()

    assert guess is not None
    assert session.reject_guess(guess.user_id) == 1

    with pytest.raises(KeyError):
        session.reject_guess(999)
