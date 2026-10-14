import pickle  # ruff: ignore[suspicious-pickle-import]

import orjson


class OrjsonSerializer:
    def dumps(self, value: object) -> bytes:
        return orjson.dumps(value)

    def loads(self, payload: bytes) -> object:
        return orjson.loads(payload)


class PickleSerializer:
    """Serialize trusted, application-owned cache values."""

    def dumps(self, value: object) -> bytes:
        return pickle.dumps(
            value,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    def loads(self, payload: bytes) -> object:
        return pickle.loads(  # ruff: ignore[suspicious-pickle-usage]
            payload,
        )
