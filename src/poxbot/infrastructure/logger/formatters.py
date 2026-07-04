from __future__ import annotations

import json
from logging import Formatter, LogRecord
from typing import Any, NotRequired, TypedDict

from .context import extension_var, request_id_var


class JSONLog(TypedDict):
    level: str
    logger: str
    message: str
    time: str

    request_id: NotRequired[str | None]
    extension: NotRequired[str | None]
    trace_id: NotRequired[str | None]
    prefix: NotRequired[str | None]


class PlainFormatter(Formatter):
    def __init__(self):
        super().__init__("%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class JSONFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        payload: JSONLog = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record),
        }
        
        payload["request_id"] = getattr(record, "request_id", request_id_var.get())
        payload["extension"] = getattr(record, "extension", extension_var.get())
        
        trace_id = getattr(record, "trace_id", None)
        if trace_id is not None:
            payload["trace_id"] = trace_id

        prefix = getattr(record, "prefix", None)
        if prefix is not None:
            payload["prefix"] = prefix
        
        return json.dumps(payload, ensure_ascii=False)
