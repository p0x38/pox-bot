from pathlib import Path

from .address import ResourceAddress
from .errors import ResourcePathError, ResourcePermissionError


class FilesystemResolver:
    """Resolve resources beneath a configured filesystem root."""

    def __init__(
            self,
            root: Path,
            *,
            writable: bool = False,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.writable = writable

    def resolve_path(
            self,
            address: ResourceAddress,
            *,
            write: bool = False,
    ) -> Path:
        if write and not self.writable:
            raise ResourcePermissionError(
                f"Resource scheme {address.scheme!r} is read-only.",
            )

        try:
            candidate = self.root.joinpath(*address.parts).resolve(
                strict=False,
            )
        except (OSError, RuntimeError) as exc:
            raise ResourcePathError(
                f"Unable to resolve resource address {address!s}.",
            ) from exc

        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ResourcePathError(
                f"Resource address escapes its registered root: {address!s}",
            ) from exc

        return candidate
