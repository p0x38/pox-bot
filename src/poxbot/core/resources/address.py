from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ResourcePathError

_SCHEME_PATTERN = re.compile(
    r'[a-z][a-z0-9+.-]*',
    re.IGNORECASE | re.ASCII,
)


@dataclass(frozen=True, slots=True)
class ResourceAddress:
    scheme: str
    parts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scheme, str) or not _SCHEME_PATTERN.fullmatch(
            self.scheme,
        ):
            raise ResourcePathError(
                f'Invalid resource scheme: {self.scheme!r}',
            )

        object.__setattr__(self, 'scheme', self.scheme.lower())

        if not isinstance(self.parts, tuple) or not self.parts:
            raise ResourcePathError(
                'Resource path must contain at least one component.',
            )

        for part in self.parts:
            if not isinstance(part, str):
                raise ResourcePathError(
                    'Resource path components must be strings.',
                )

            if part in {'', '.', '..'}:
                raise ResourcePathError(
                    f'Invalid resource path component: {part!r}',
                )

            if any(character in part for character in ('/', '\\', '\x00', ':')):
                raise ResourcePathError(
                    f'Invalid character in resource path component: {part!r}',
                )

    @classmethod
    def parse(cls, value: str) -> ResourceAddress:
        if not isinstance(value, str):
            raise ResourcePathError(
                'Resource address must be a string.',
            )

        scheme, separator, path = value.partition(':')

        if not separator:
            raise ResourcePathError(
                "Resource address must use 'scheme:path' syntax.",
            )

        if not path or path.startswith('/'):
            raise ResourcePathError(
                'Resource path must be non-empty and relative.',
            )

        return cls(
            scheme=scheme.lower(),
            parts=tuple(path.split('/')),
        )

    def __str__(self) -> str:
        return f'{self.scheme}:{"/".join(self.parts)}'
