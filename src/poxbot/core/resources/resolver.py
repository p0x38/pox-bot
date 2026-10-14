from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .address import ResourceAddress


class ResourceResolver(Protocol):
    """Resolve resource addresses to filesystem paths."""

    def resolve_path(
        self,
        address: ResourceAddress,
        *,
        write: bool = False,
    ) -> Path:
        """Resolve an address while enforcing access and containment rules."""
        ...
