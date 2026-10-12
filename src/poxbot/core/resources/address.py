from __future__ import annotations

import re
from dataclasses import dataclass

_SCHEME_PATTERN = re.compile(
    r"[a-z][a-z0-9+.-]*",
    re.ASCII,
)


class ResourcePathError(ValueError):
    """Raised when a resource address is invalid."""


@dataclass(frozen=True, slots=True)
class ResourceAddress:
    scheme: str
    parts: tuple[str, ...]

    @classmethod
    def parse(cls, value: str) -> ResourceAddress:
        if not isinstance(value, str):
            raise ResourcePathError(
                "Resource address must be a string.",
            )
        
        scheme, separator, path = value.partition(":")

        if not separator:
            raise ResourcePathError(
                "Resource address must use 'scheme:path' syntax.",
            )

        if not _SCHEME_PATTERN.fullmatch(scheme):
            raise ResourcePathError(
                f"Invalid resource scheme: {scheme!r}",
            )

        if not path or path.startswith("/"):
            raise ResourcePathError(
                "Resource path must be non-empty and relative.",
            )

        if "\\" in path or "\x00" in path:
            raise ResourcePathError(
                "Resource path contains an invalid character.",
            )

        parts = tuple(path.split("/"))

        if any(part in {"", ".", ".."} for part in parts):
            raise ResourcePathError(
                "Resource path contains an invalid component.",
            )

        if any(":" in part for part in parts):
            raise ResourcePathError(
                "Colons are not allowed in path components.",
            )

        return cls(
            scheme=scheme.lower(),
            parts=parts,
        )
