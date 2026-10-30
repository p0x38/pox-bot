from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass

from roblox import AvatarThumbnailType, Client


class RobloxAPIError(RuntimeError):
    """Raised when a Roblox API operation fails."""


@dataclass(frozen=True, slots=True)
class RobloxUser:
    user_id: int
    username: str
    display_name: str
    avatar_url: str

    @property
    def profile_url(self) -> str:
        return f"https://www.roblox.com/users/{self.user_id}/profile"


class RobloxClient:
    def __init__(self, *, cache_ttl: float = 300.0) -> None:
        if cache_ttl < 0:
            raise ValueError("cache_ttl must not be negative.")

        self._client = Client()
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, RobloxUser]] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._closed:
            return

        self._closed = True
        await self._client.requests.session.aclose()

    async def resolve_users(
        self,
        usernames: Sequence[str],
    ) -> list[RobloxUser]:
        """Resolve usernames and retrieve their current avatar thumbnails."""
        unique_names: dict[str, str] = {}

        for username in usernames:
            username = username.strip()  # ruff: ignore[redefined-loop-name]
            if username:
                unique_names.setdefault(username.casefold(), username)

        if not unique_names:
            return []

        async with self._lock:
            if self._closed:
                raise RobloxAPIError("The Roblox client is closed.")

            now = time.monotonic()
            resolved: dict[str, RobloxUser] = {}
            missing: list[str] = []

            for key, username in unique_names.items():
                cached = self._cache.get(key)

                if cached is not None and cached[0] > now:
                    resolved[key] = cached[1]
                else:
                    self._cache.pop(key, None)
                    missing.append(username)

            for offset in range(0, len(missing), 100):
                batch = missing[offset : offset + 100]

                try:
                    records = await self._client.get_users_by_usernames(
                        usernames=batch,
                        expand=False,
                    )

                    if not records:
                        continue

                    thumbnails = (
                        await self._client.thumbnails.get_user_avatar_thumbnails(
                            users=[user.id for user in records],
                            type=AvatarThumbnailType.full_body,
                            size=(420, 420),
                        )
                    )
                except Exception as exc:
                    raise RobloxAPIError(
                        "Failed to retrieve Roblox users or avatar thumbnails."
                    ) from exc

                thumbnails_by_id = {
                    thumbnail.target_id: thumbnail.image_url
                    for thumbnail in thumbnails
                    if thumbnail.image_url is not None
                }

                expires_at = time.monotonic() + self._cache_ttl

                for record in records:
                    avatar_url = thumbnails_by_id.get(record.id)

                    if avatar_url is None:
                        continue

                    username = record.name
                    display_name = record.display_name

                    user = RobloxUser(
                        user_id=record.id,
                        username=username,
                        display_name=(
                            display_name
                            if isinstance(display_name, str) and display_name
                            else username
                        ),
                        avatar_url=avatar_url,
                    )

                    keys = {username.casefold()}
                    requested_username = getattr(
                        record,
                        "requested_username",
                        None,
                    )

                    if isinstance(requested_username, str):
                        keys.add(requested_username.casefold())

                    for key in keys:
                        resolved[key] = user
                        self._cache[key] = (expires_at, user)

            return [
                resolved[key]
                for key in unique_names
                if key in resolved
            ]
