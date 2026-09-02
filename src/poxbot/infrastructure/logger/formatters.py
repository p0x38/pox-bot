from __future__ import annotations

import json
from logging import Formatter, LogRecord
from typing import Any, TypedDict

from .context import extension_var, request_id_var

_IGNORE_ATTRIBUTES = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName",
}


class JSONLog(TypedDict):
    level: str
    logger: str
    message: str
    time: str

    request_id: str | None
    extension: str | None
    trace_id: str | None
    prefix: str | None
    error: str | None
    stack_trace: str | None


class PlainFormatter(Formatter):
    def __init__(self):
        super().__init__("%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class JSONFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record),
        }
        
        payload["request_id"] = getattr(record, "request_id", request_id_var.get())
        payload["extension"] = getattr(record, "extension", extension_var.get())
        
        for optional_key in ["trace_id", "prefix"]:
            val = getattr(record, optional_key, None)
            if val is not None:
                payload[optional_key] = val
        
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_value:
                payload["error"] = (
                    f"{exc_type.__name__}: {exc_value}"
                    if exc_type else str(exc_value)
                )
            
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                payload["stack_trace"] = record.exc_text
        
        for key, value in record.__dict__.items():
            if key not in _IGNORE_ATTRIBUTES and key not in payload:
                if isinstance(value, bytes):
                    payload[key] = value.decode('utf-8', errors='ignore')
                else:
                    payload[key] = str(value)
        
        return json.dumps(payload, ensure_ascii=False)
