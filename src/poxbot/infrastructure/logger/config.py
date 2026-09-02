from __future__ import annotations

import logging


def get_log_level(config, default="INFO") -> int:
    level_name = getattr(config, "level", default)
    return getattr(logging, level_name.upper(), logging.INFO)
