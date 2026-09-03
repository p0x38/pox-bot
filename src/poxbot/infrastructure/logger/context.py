from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str | None] = ContextVar('request_id', default=None)
extension_var: ContextVar[str | None] = ContextVar('extension', default=None)


def get_request_id() -> str:
    rid = request_id_var.get()
    if rid is None:
        rid = uuid4().hex
        request_id_var.set(rid)
    return rid


def set_request_id(value: str | None = None) -> str:
    value = value or uuid4().hex
    request_id_var.set(value)
    return value


def set_extension(name: str | None):
    extension_var.set(name)


def get_extension() -> str | None:
    return extension_var.get()


def start_request() -> str:
    """Call this at the beginning of ANY bot interaction."""
    rid = uuid4().hex
    request_id_var.set(rid)
    return rid
