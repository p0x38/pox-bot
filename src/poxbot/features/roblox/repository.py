from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .akinator import Question, RobloxCandidate


class RobloxDataRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _load_json(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(f"{filename} must contain a JSON object.")

        return data

    def load_questions(self) -> list[Question]:
        data = self._load_json("questions.json")

        if data.get("version") != 1:
            raise ValueError("Unsupported questions.json version.")

        return [
            Question(
                id=item["id"],
                feature=item["feature"],
                prompt=item["prompt"],
                enabled=item.get("enabled", True),
                weight=item.get("weight", 1.0),
            )
            for item in data["questions"]
        ]

    def load_candidates(self) -> list[RobloxCandidate]:
        data = self._load_json("candidates.json")

        if data.get("version") != 1:
            raise ValueError("Unsupported candidates.json version.")

        return [
            RobloxCandidate(
                user_id=item["user_id"],
                username=item["username"],
                display_name=item["display_name"],
                features=item["features"],
                tags=tuple(item.get("tags", [])),
            )
            for item in data["candidates"]
        ]
