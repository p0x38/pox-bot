from .context import get_request_id, get_extension


def enrich_extra(extra: dict | None) -> dict:
    base = dict(extra or {})
    
    base["request_id"] = get_request_id()
    base["extension"] = get_extension()
    
    return base
