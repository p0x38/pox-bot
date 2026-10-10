# The cog uses P2PQuake API to get EEW information and display it in Discord.
#
# The documentation of API can be found here:
# https://www.p2pquake.net/develop/json_api_v2/
#
# Also, the cog uses JMA's data for displaying earthquake & tsunami information.
# The copyright of JMA's data belongs to Japan Meteorological Agency, and
# P2PQuake is not affiliated with JMA.
# I do not claim any rights to JMA's data, or P2PQuake's data.
#
# I do NOT take any responsibility for any damage caused by using the API.
# https://www.p2pquake.net/secondary_use/

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import OrderedDict
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from types import TracebackType
from typing import Annotated, Any, Literal, Self

import aiohttp
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)
from pytz import timezone

from ...infrastructure.logger.setup import get_logger

API_BASE_URL = "https://api.p2pquake.net/v2"
JST = timezone("Asia/Tokyo")

EventCode = Literal[551, 552, 556]
DEFAULT_CODES: tuple[EventCode, ...] = (551, 552, 556)


def parse_p2p_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return JST.localize(value)
        return value.astimezone(JST)

    if not isinstance(value, str):
        raise ValueError(f"Expected a datetime string, got {type(value).__name__}")

    value = value.strip()

    for fmt in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)  # ruff: ignore[call-datetime-strptime-without-zone]
            return JST.localize(parsed)
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Unsupported timestamp: {value!r}") from exc

    if parsed.tzinfo is None:
        return JST.localize(parsed)

    return parsed.astimezone(JST)


P2PDateTime = Annotated[datetime, BeforeValidator(parse_p2p_datetime)]


class P2PModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class P2PData(P2PModel):
    id: str
    time: P2PDateTime


class QuakeIssue(P2PModel):
    source: str | None = None
    time: P2PDateTime
    type: str
    correct: str | None = None


class QuakeHypocenter(P2PModel):
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    depth: int | None = None
    magnitude: float | None = None


class QuakeDetails(P2PModel):
    time: P2PDateTime
    hypocenter: QuakeHypocenter | None = None
    max_scale: int | None = Field(default=None, alias="maxScale")
    domestic_tsunami: str | None = Field(
        default=None,
        alias="domesticTsunami",
    )
    foreign_tsunami: str | None = Field(
        default=None,
        alias="foreignTsunami",
    )


class QuakePoint(P2PModel):
    pref: str
    addr: str
    is_area: bool = Field(alias="isArea")
    scale: float


class QuakeComments(P2PModel):
    free_form_comment: str = Field(
        default="",
        alias="freeFormComment",
    )


class JMAQuake(P2PData):
    code: Literal[551]
    issue: QuakeIssue
    earthquake: QuakeDetails
    points: list[QuakePoint] = Field(default_factory=list)
    comments: QuakeComments = Field(default_factory=QuakeComments)


class TsunamiIssue(P2PModel):
    source: str
    time: P2PDateTime
    type: str


class TsunamiFirstHeight(P2PModel):
    arrival_time: P2PDateTime | None = Field(
        default=None,
        alias="arrivalTime",
    )
    condition: str | None = None


class TsunamiMaxHeight(P2PModel):
    description: str | None = None
    value: float | None = None


class TsunamiArea(P2PModel):
    grade: str | None = None
    immediate: bool | None = None
    name: str
    first_height: TsunamiFirstHeight | None = Field(
        default=None,
        alias="firstHeight",
    )
    max_height: TsunamiMaxHeight | None = Field(
        default=None,
        alias="maxHeight",
    )


class JMATsunami(P2PData):
    code: Literal[552]
    cancelled: bool
    issue: TsunamiIssue
    areas: list[TsunamiArea] = Field(default_factory=list)


class EEWHypocenter(P2PModel):
    name: str | None = None
    reduce_name: str | None = Field(default=None, alias="reduceName")
    latitude: float | None = None
    longitude: float | None = None
    depth: float | None = None
    magnitude: float | None = None


class EEWEarthquake(P2PModel):
    origin_time: P2PDateTime = Field(alias="originTime")
    arrival_time: P2PDateTime = Field(alias="arrivalTime")
    condition: str | None = None
    hypocenter: EEWHypocenter


class EEWIssue(P2PModel):
    time: P2PDateTime
    event_id: str = Field(alias="eventId")
    serial: str


class EEWArea(P2PModel):
    pref: str
    name: str
    scale_from: float = Field(alias="scaleFrom")
    scale_to: float = Field(alias="scaleTo")
    kind_code: str | None = Field(default=None, alias="kindCode")
    arrival_time: P2PDateTime | None = Field(
        default=None,
        alias="arrivalTime",
    )


class EEW(P2PData):
    code: Literal[556]
    test: bool | None = None
    earthquake: EEWEarthquake | None = None
    issue: EEWIssue
    cancelled: bool
    areas: list[EEWArea] = Field(default_factory=list)


P2PEvent = Annotated[
    JMAQuake | JMATsunami | EEW,
    Field(discriminator="code"),
]

EVENT_ADAPTER = TypeAdapter(P2PEvent)


class P2PQuakeAPIError(RuntimeError):
    pass


class P2PQuakeRateLimitError(P2PQuakeAPIError):
    pass


class P2PQuakeManager:
    def __init__(
        self,
        *,
        session: aiohttp.ClientSession | None = None,
        base_url: str = API_BASE_URL,
        timeout: aiohttp.ClientTimeout | None = None,
        cache_size: int = 100,
    ) -> None:
        if cache_size < 1:
            raise ValueError("cache_size must be positive")
        
        self.logger = get_logger(__name__, prefix="P2PQuakeManager")

        self._session = session
        self._owns_session = session is None
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout or aiohttp.ClientTimeout(total=10)

        self._cache_size = cache_size
        self._events: OrderedDict[str, P2PEvent] = OrderedDict()
        self._ws_task: asyncio.Task[None] | None = None

        self._initial_history_loaded = False

    @property
    def cached_events(self) -> tuple[P2PEvent, ...]:
        """Return a snapshot of cached events, newest first."""
        return tuple(
            sorted(
                self._events.values(),
                key=lambda event: event.time,
                reverse=True,
            )
        )

    async def _load_initial_history(self) -> None:
        if self._initial_history_loaded:
            return

        self._initial_history_loaded = True

        try:
            events = await self.get_events(
                codes=(551, 552, 556),
                limit=min(self._cache_size, 100),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger.exception(
                "Failed to preload P2PQuake history; "
                "continuing with WebSocket events."
            )
            return

        for event in reversed(events):
            self._cache_event(event)

        self.logger.info(
            "Preloaded %d P2PQuake events into cache.",
            len(events),
        )

    def get_cached_events(
            self,
            *,
            codes: tuple[int, ...] = (551, 552, 556),
            limit: int | None = None,
    ) -> list[P2PEvent]:
        events = [
            event
            for event in self.cached_events
            if event.code in codes
        ]

        return events if limit is None else events[:limit]

    def _cache_event(self, event: P2PEvent) -> bool:
        """Cache an event; return False if its ID was already seen."""
        if event.id in self._events:
            return False

        self._events[event.id] = event
        self._events.move_to_end(event.id, last=False)

        while len(self._events) > self._cache_size:
            self._events.popitem(last=True)

        return True

    def _websocket_url(self) -> str:
        base_url = self._base_url.rstrip("/")

        if base_url.startswith("https://"):
            base_url = "wss://" + base_url.removeprefix("https://")
        elif base_url.startswith("http://"):
            base_url = "ws://" + base_url.removeprefix("http://")

        return f"{base_url}/ws"

    async def start(self) -> None:
        """Start the WebSocket consumer once."""
        if self._ws_task is not None and not self._ws_task.done():
            return

        await self._get_session()

        self._ws_task = asyncio.create_task(
            self._listen_websocket(),
            name="p2pquake-websocket",
        )

    async def _listen_websocket(self) -> None:
        await self._load_initial_history()

        accepted_codes = {551, 552, 556}
        delay = 1.0
        max_delay = 30.0
        url = self._websocket_url()

        while True:
            try:
                session = await self._get_session()

                async with session.ws_connect(
                    url,
                    heartbeat=25,
                    max_msg_size=1_048_576,
                ) as websocket:
                    self.logger.info("Connected to P2PQuake WebSocket.")

                    async for message in websocket:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(message.data)
                            except json.JSONDecodeError:
                                self.logger.warning(
                                    "Received invalid JSON from P2PQuake.",
                                )
                                continue

                            if not isinstance(payload, dict):
                                continue

                            code = payload.get("code")
                            if code not in accepted_codes:
                                continue

                            try:
                                event = EVENT_ADAPTER.validate_python(
                                    payload,
                                )
                            except ValidationError:
                                self.logger.exception(
                                    "Failed to validate P2PQuake event.",
                                )
                                continue

                            if self._cache_event(event):
                                self.logger.debug(
                                    "Cached P2PQuake event %s (code=%s).",
                                    event.id,
                                    event.code,
                                )

                            delay = 1.0
                        elif message.type == aiohttp.WSMsgType.ERROR:
                            raise websocket.exception() or aiohttp.ClientError(
                                "WebSocket connection failed.",
                            )
                        elif message.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSING
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, TimeoutError, OSError):
                self.logger.warning(
                    "P2PQuake WebSocket disconnected.",
                    exc_info=True,
                )

            self.logger.info(
                "Reconnecting to P2PQuake in %.1f seconds.",
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)

    async def iter_events(
        self,
        *,
        codes: Sequence[EventCode] = DEFAULT_CODES,
        reconnect_initial_delay: float = 1.0,
        reconnect_max_delay: float = 30.0,
        backfill_on_reconnect: bool = True,
        backfill_limit: int = 100,
        dedupe_cache_size: int = 4096,
    ) -> AsyncIterator[P2PEvent]:
        if not codes:
            raise ValueError("At least one event code is required")

        if not set(codes).issubset({551, 552, 556}):
            raise ValueError("Supported event codes are 551, 552, and 556")

        if reconnect_initial_delay <= 0:
            raise ValueError("Initial reconnect delay must be positive")

        if reconnect_max_delay < reconnect_initial_delay:
            raise ValueError(
                "Maximum reconnect delay must be >= initial delay"
            )

        if not 1 <= backfill_limit <= 100:
            raise ValueError("backfill_limit must be between 1 and 100")

        if dedupe_cache_size < 1:
            raise ValueError("dedupe_cache_size must be positive")

        accepted_codes = set(codes)
        seen_ids: OrderedDict[str, None] = OrderedDict()

        def remember(event: P2PEvent) -> bool:
            if event.id in seen_ids:
                return False

            seen_ids[event.id] = None

            while len(seen_ids) > dedupe_cache_size:
                seen_ids.popitem(last=False)

            return True

        delay = reconnect_initial_delay
        connected_once = False
        backfill_pending = False
        websocket_url = self._websocket_url()

        while True:
            if backfill_pending and backfill_on_reconnect:
                backfill_pending = False

                try:
                    historical = await self.get_events(
                        codes=codes,
                        limit=backfill_limit,
                    )
                except (
                    aiohttp.ClientError,
                    P2PQuakeAPIError,
                    ValidationError,
                    TimeoutError,
                ):
                    self.logger.warning(
                        "Failed to retrieve P2PQuake history after "
                        "a WebSocket disconnection.",
                        exc_info=True,
                    )
                else:
                    # History is newest-first; replay missed events oldest-first.
                    for event in reversed(historical):
                        if remember(event):
                            yield event

            try:
                session = await self._get_session()

                async with session.ws_connect(
                    websocket_url,
                    heartbeat=25,
                    autoping=True,
                    max_msg_size=1_048_576,
                ) as websocket:
                    connected_once = True

                    async for message in websocket:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            delay = reconnect_initial_delay

                            try:
                                payload = json.loads(message.data)
                            except json.JSONDecodeError:
                                self.logger.warning(
                                    "Received invalid JSON from P2PQuake."
                                )
                                continue

                            if not isinstance(payload, dict):
                                continue

                            try:
                                code = int(payload.get("code", -1))
                            except (TypeError, ValueError):
                                continue

                            # /ws delivers several event types. Ignore unrelated
                            # ones before validating against our discriminated union.
                            if code not in accepted_codes:
                                continue

                            try:
                                event = EVENT_ADAPTER.validate_python(payload)
                            except ValidationError:
                                self.logger.warning(
                                    "Invalid P2PQuake payload for code %s.",
                                    code,
                                    exc_info=True,
                                )
                                continue

                            if self._cache_event(event):
                                self.logger.debug(
                                    "Cached P2PQuake event %s (code=%s).",
                                    event.id,
                                    event.code,
                                )

                        elif message.type == aiohttp.WSMsgType.ERROR:
                            error = websocket.exception()
                            if error is not None:
                                raise error

                            raise aiohttp.ClientError(
                                "P2PQuake WebSocket failed"
                            )

                        elif message.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSING,
                        ):
                            break

            except asyncio.CancelledError:
                raise

            except (aiohttp.ClientError, TimeoutError, OSError):
                self.logger.warning(
                    "P2PQuake WebSocket disconnected; reconnecting.",
                    exc_info=True,
                )

            if connected_once:
                backfill_pending = True

            await asyncio.sleep(delay)
            delay = min(delay * 2, reconnect_max_delay)

    async def __aenter__(self) -> Self:
        await self._get_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._ws_task is not None:
            self._ws_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await self._ws_task

            self._ws_task = None

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True

        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def get_events(
        self,
        *,
        codes: Sequence[EventCode] = DEFAULT_CODES,
        limit: int = 10,
        offset: int = 0,
    ) -> list[P2PEvent]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        if offset < 0:
            raise ValueError("offset must be non-negative")

        if not codes:
            raise ValueError("At least one event code is required")

        if not set(codes).issubset({551, 552, 556}):
            raise ValueError("Supported event codes are 551, 552, and 556")

        session = await self._get_session()

        params: list[tuple[str, str | int]] = [
            ("codes", code) for code in dict.fromkeys(codes)
        ]
        params.extend([
            ("limit", limit),
            ("offset", offset),
        ])

        async with session.get(
            f"{self._base_url}/history",
            params=params,
        ) as response:
            if response.status == 429:
                raise P2PQuakeRateLimitError(
                    "P2PQuake API rate limit exceeded"
                )

            response.raise_for_status()
            payload = await response.json()

        if not isinstance(payload, list):
            raise P2PQuakeAPIError(
                "Expected a JSON array from the history endpoint"
            )

        return [
            EVENT_ADAPTER.validate_python(item)
            for item in payload
        ]

    async def get_latest_event(
        self,
        *,
        codes: Sequence[EventCode] = DEFAULT_CODES,
    ) -> P2PEvent | None:
        events = await self.get_events(codes=codes, limit=1)
        return events[0] if events else None

    async def get_eews(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[EEW]:
        events = await self.get_events(
            codes=(556,),
            limit=limit,
            offset=offset,
        )
        return [event for event in events if isinstance(event, EEW)]

    async def get_latest_eew(self) -> EEW | None:
        eews = await self.get_eews(limit=1)
        return eews[0] if eews else None
