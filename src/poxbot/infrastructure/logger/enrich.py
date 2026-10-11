from .context import extension_var, request_id_var


def enrich_extra(extra: dict | None) -> dict:
    base = dict(extra or {})

    request_id = request_id_var.get()
    if request_id is not None:
        base['request_id'] = request_id

    base['extension'] = extension_var.get()

    return base
