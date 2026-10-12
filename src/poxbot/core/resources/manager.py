from __future__ import annotations

from pathlib import Path

from .address import ResourceAddress
from .errors import (
    ResourcePathError,
    ResourceSchemeAlreadyRegisteredError,
    UnknownResourceSchemeError,
)
from .filesystem import FilesystemResolver
from .resolver import ResourceResolver


class ResourceManager:
    """Resolve and access resources through registered virtual path schemes."""

    def __init__(self) -> None:
        self._resolvers: dict[str, ResourceResolver] = {}

    def register(
        self,
        scheme: str,
        resolver: ResourceResolver,
        *,
        replace: bool = False,
    ) -> None:
        probe = ResourceAddress.parse(f"{scheme}:probe")
        normalized_scheme = probe.scheme

        if normalized_scheme in self._resolvers and not replace:
            raise ResourceSchemeAlreadyRegisteredError(
                f"Resource scheme {normalized_scheme!r} is already registered.",
            )

        self._resolvers[normalized_scheme] = resolver

    def _get_resolver(
        self,
        address: str | ResourceAddress,
    ) -> tuple[ResourceAddress, ResourceResolver]:
        parsed = (
            ResourceAddress.parse(address)
            if isinstance(address, str)
            else address
        )

        try:
            resolver = self._resolvers[parsed.scheme]
        except KeyError:
            raise UnknownResourceSchemeError(
                f"Unknown resource scheme: {parsed.scheme!r}",
            ) from None

        return parsed, resolver

    def resolve_path(
        self,
        address: str | ResourceAddress,
        *,
        write: bool = False,
    ) -> Path:
        parsed, resolver = self._get_resolver(address)
        return resolver.resolve_path(parsed, write=write)

    def get_root(self, scheme: str) -> Path:
        """Return a registered filesystem resolver's canonical root."""

        try:
            resolver = self._resolvers[scheme.lower()]
        except KeyError:
            raise UnknownResourceSchemeError(
                f"Unknown resource scheme: {scheme!r}",
            ) from None

        if not isinstance(resolver, FilesystemResolver):
            raise ResourcePathError(
                f"Resource scheme {scheme!r} does not expose a filesystem root.",
            )

        return resolver.root

    def read_bytes(self, address: str | ResourceAddress) -> bytes:
        return self.resolve_path(address).read_bytes()

    def read_text(
        self,
        address: str | ResourceAddress,
        *,
        encoding: str = "utf-8",
    ) -> str:
        return self.resolve_path(address).read_text(encoding=encoding)

    def write_bytes(
        self,
        address: str | ResourceAddress,
        data: bytes,
    ) -> int:
        path = self.resolve_path(address, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Revalidate after creating parent directories to catch symlink escapes.
        path = self.resolve_path(address, write=True)
        return path.write_bytes(data)

    def write_text(
        self,
        address: str | ResourceAddress,
        data: str,
        *,
        encoding: str = "utf-8",
    ) -> int:
        path = self.resolve_path(address, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = self.resolve_path(address, write=True)
        return path.write_text(data, encoding=encoding)

    def exists(self, address: str | ResourceAddress) -> bool:
        return self.resolve_path(address).exists()


def create_default_resource_manager(
    *,
    user_data_path: Path | None = None,
    assets_path: Path | None = None,
) -> ResourceManager:
    """Create the standard assets and user-data resource schemes."""

    if assets_path is None:
        package_root = Path(__file__).resolve().parents[2]
        assets_path = package_root / "assets"

    if user_data_path is None:
        from platformdirs import PlatformDirs

        user_data_path = PlatformDirs(
            appname="pox-bot",
            appauthor="p0x38",
        ).user_data_path

    manager = ResourceManager()
    manager.register("assets", FilesystemResolver(assets_path, writable=False))
    manager.register("userdata", FilesystemResolver(user_data_path, writable=True))
    return manager
