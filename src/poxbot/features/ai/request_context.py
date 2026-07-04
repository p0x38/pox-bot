from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

from pytz import UTC


@dataclass(frozen=True)
class LLMRequestContext:
    """Holds the exact 'now' snapshot when an LLM request started.
    
    Combines datetime for wall-clock logging and perf_counter for
    high-orecision monotonic latency metrics.
    """
    
    start_time: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    start_tick: float = field(default_factory=perf_counter)
    
    @property
    def elapsed_seconds(self) -> float:
        """Calculate the precise elapsed duration since the request started."""
        return perf_counter() - self.start_tick
