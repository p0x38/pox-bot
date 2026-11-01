import json

import pytest

from poxbot.features.roblox.repository import RobloxDataRepository


def _write_json(path, filename: str, data: dict) -> None:
    (path / filename).write_text(
        json.dumps(data),
        encoding='utf-8',
    )


def test_load_game_data_rejects_unusable_questions(tmp_path) -> None:
    _write_json(
        tmp_path,
        'questions.json',
        {
            'version': 1,
            'questions': [
                {
                    'id': 'hat',
                    'feature': 'has_hat',
                    'prompt': 'akinator.questions.hat',
                },
            ],
        },
    )

    _write_json(
        tmp_path,
        'candidates.json',
        {
            'version': 1,
            'candidates': [
                {
                    'user_id': 1,
                    'username': 'user1',
                    'display_name': 'User 1',
                    'features': {'has_hat': True},
                },
                {
                    'user_id': 2,
                    'username': 'user2',
                    'display_name': 'User 2',
                    'features': {'has_hat': True},
                },
            ],
        },
    )

    repository = RobloxDataRepository(tmp_path)

    with pytest.raises(ValueError, match='cannot distinguish'):
        repository.load_game_data()


def test_load_game_data_accepts_valid_dataset(tmp_path) -> None:
    _write_json(
        tmp_path,
        'questions.json',
        {
            'version': 1,
            'questions': [
                {
                    'id': 'hat',
                    'feature': 'has_hat',
                    'prompt': 'akinator.questions.hat',
                },
            ],
        },
    )

    _write_json(
        tmp_path,
        'candidates.json',
        {
            'version': 1,
            'candidates': [
                {
                    'user_id': 1,
                    'username': 'user1',
                    'display_name': 'User 1',
                    'features': {'has_hat': True},
                },
                {
                    'user_id': 2,
                    'username': 'user2',
                    'display_name': 'User 2',
                    'features': {'has_hat': False},
                },
            ],
        },
    )

    repository = RobloxDataRepository(tmp_path)
    questions, candidates = repository.load_game_data()

    assert len(questions.questions) == 1
    assert len(candidates.candidates) == 2
