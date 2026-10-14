from __future__ import annotations

from pathlib import Path

from .address import ResourceAddress
from .errors import ResourceSchemeAlreadyRegisteredError, UnknownResourceSchemeError
from .resolver import ResourceResolver


class ResourceManager:
    """Manage resources using registered virtual path schemes."""

    def __init__(self) -> None:
        self._resolvers: dict[str, ResourceResolver] = {}

    def register(
        self,
        scheme: str,
        resolver: ResourceResolver,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(scheme, str):
            raise ValueError('Resource scheme must be a string.')

        probe = ResourceAddress.parse(f'{scheme}:__probe__')
        normalized_scheme = probe.scheme

        if normalized_scheme in self._resolvers and not replace:
            raise ResourceSchemeAlreadyRegisteredError(
                f'Resource scheme {normalized_scheme!r} is already registered.',
            )

        self._resolvers[normalized_scheme] = resolver

    def _get_resolver(
        self,
        address: str,
    ) -> tuple[ResourceAddress, ResourceResolver]:
        parsed = ResourceAddress.parse(address)

        try:
            resolver = self._resolvers[parsed.scheme]
        except KeyError:
            raise UnknownResourceSchemeError(
                f'Unknown resource scheme: {parsed.scheme!r}',
            ) from None

        return parsed, resolver

    def resolve_path(
        self,
        address: str,
        *,
        write: bool = False,
    ) -> Path:
        parsed, resolver = self._get_resolver(address)

        return resolver.resolve_path(
            parsed,
            write=write,
        )

    def read_bytes(self, address: str) -> bytes:
        return self.resolve_path(address).read_bytes()

    def read_text(
        self,
        address: str,
        *,
        encoding: str = 'utf-8',
    ) -> str:
        return self.resolve_path(address).read_text(
            encoding=encoding,
        )

    def write_bytes(
        self,
        address: str,
        data: bytes,
    ) -> int:
        path = self.resolve_path(address, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = self.resolve_path(address, write=True)
        return path.write_bytes(data)

    def write_text(
        self,
        address: str,
        data: str,
        *,
        encoding: str = 'utf-8',
    ) -> int:
        path = self.resolve_path(address, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = self.resolve_path(address, write=True)
        return path.write_text(
            data,
            encoding=encoding,
        )

    def exists(self, address: str) -> bool:
        return self.resolve_path(address).exists()
