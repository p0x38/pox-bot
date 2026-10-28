import asyncio
import os
import threading
import tracemalloc
from collections.abc import Iterable
from typing import Any, TypedDict

import psutil
from discord import Color, Embed

MIB = 1024**2
TRACEBACK_DEPTH = 8
TRACEBACK_FRAME_LIMIT = 3
MAX_TRACEBACK_CHARS = 180
MAX_GROWTH_REPORTS = 4
CPU_SAMPLE_INTERVAL = 0.25


class MemoryGrowthReport(TypedDict):
    size_diff_bytes: int
    count_diff: int
    traceback: str


class PerformanceStats(TypedDict):
    latency_ms: float
    cpu_percent: float
    cpu_percent_host: float
    cpu_logical_count: int
    ram_usage_mib: float
    traced_memory_mib: float
    traced_peak_mib: float
    tracemalloc_overhead_mib: float
    memory_growth_since_previous: list[MemoryGrowthReport]
    memory_growth_since_start: list[MemoryGrowthReport]


class PerformanceMonitor:
    """Collect process performance and Python memory-allocation statistics."""

    def __init__(self, bot: Any) -> None:
        self.bot = bot
        self.process = psutil.Process(os.getpid())
        self.logical_cpu_count = psutil.cpu_count(logical=True) or 1

        if not tracemalloc.is_tracing():
            tracemalloc.start(TRACEBACK_DEPTH)

        self._sample_lock = threading.Lock()

        self._baseline_snapshot = tracemalloc.take_snapshot()
        self._last_snapshot = self._baseline_snapshot

    async def get_stats(self) -> PerformanceStats:
        """Collect statistics without blocking the Discord event loop."""
        latency_seconds = self.bot.latency
        latency_ms = round(latency_seconds * 1000, 1) if latency_seconds else 0.0

        return await asyncio.to_thread(
            self._collect_stats,
            latency_ms,
        )

    def _collect_stats(
        self,
        latency_ms: float,
    ) -> PerformanceStats:
        """Perform synchronous process and memory measurements."""
        with self._sample_lock:
            cpu_usage = self.process.cpu_percent(
                interval=CPU_SAMPLE_INTERVAL,
            )
            cpu_usage_host = cpu_usage / self.logical_cpu_count

            process_memory = self.process.memory_info()
            rss_memory_mib = process_memory.rss / MIB

            traced_current, traced_peak = tracemalloc.get_traced_memory()
            tracer_overhead = tracemalloc.get_tracemalloc_memory()

            current_snapshot = tracemalloc.take_snapshot()

            recent_diffs = current_snapshot.compare_to(
                self._last_snapshot,
                'lineno',
            )

            baseline_diffs = current_snapshot.compare_to(
                self._baseline_snapshot,
                'lineno',
            )

            self._last_snapshot = current_snapshot

        return {
            'latency_ms': latency_ms,
            'cpu_percent': cpu_usage,
            'cpu_percent_host': cpu_usage_host,
            'cpu_logical_count': self.logical_cpu_count,
            'ram_usage_mib': rss_memory_mib,
            'traced_memory_mib': traced_current / MIB,
            'traced_peak_mib': traced_peak / MIB,
            'tracemalloc_overhead_mib': tracer_overhead / MIB,
            'memory_growth_since_previous': self._build_growth_reports(
                recent_diffs,
            ),
            'memory_growth_since_start': self._build_growth_reports(
                baseline_diffs,
            ),
        }

    @staticmethod
    def _build_growth_reports(
        differences: Iterable[tracemalloc.StatisticDiff],
    ) -> list[MemoryGrowthReport]:
        """Return the four largest positive allocation differences."""
        top_growth = sorted(
            (stat for stat in differences if stat.size_diff > 0),
            key=lambda stat: stat.size_diff,
            reverse=True,
        )[:MAX_GROWTH_REPORTS]

        reports: list[MemoryGrowthReport] = []

        for stat in top_growth:
            traceback_text = '\n'.join(
                stat.traceback.format(
                    limit=TRACEBACK_FRAME_LIMIT,
                    most_recent_first=True,
                ),
            ).strip()

            if len(traceback_text) > MAX_TRACEBACK_CHARS:
                traceback_text = (
                    traceback_text[: MAX_TRACEBACK_CHARS - 3].rstrip() + '...'
                )

            reports.append(
                {
                    'size_diff_bytes': stat.size_diff,
                    'count_diff': stat.count_diff,
                    'traceback': traceback_text or 'Traceback unavailable',
                },
            )

        return reports

    @staticmethod
    def _format_growth(
        reports: list[MemoryGrowthReport],
    ) -> str:
        """Format allocation differences for a Discord embed field."""
        if not reports:
            return 'No positive allocation growth detected during this period.'

        sections = [
            (
                f'`{report["size_diff_bytes"] / 1024:+.1f} KiB` '
                f'(`{report["count_diff"]:+,} blocks`)\n'
                f'```py\n{report["traceback"]}\n```'
            )
            for report in reports
        ]

        message = '\n\n'.join(sections)

        if len(message) > 1024:
            message = message[:1021].rstrip() + '...'

        return message

    def create_embed(
        self,
        stats: PerformanceStats,
        locale: str = 'en',
    ) -> Embed:
        """Create an embed with process and memory-allocation statistics."""
        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.info.memory_check.embeds.default.title',
                locale,
            ),
            color=Color.blue(),
        )

        embed.add_field(
            name='Gateway Latency',
            value=f'`{stats["latency_ms"]:.1f} ms`',
            inline=True,
        )
        embed.add_field(
            name='Process CPU (one logical CPU = 100%)',
            value=f'`{stats["cpu_percent"]:.1f}%`',
            inline=True,
        )
        embed.add_field(
            name='Process CPU (% of host CPU capacity)',
            value=(
                f'`{stats["cpu_percent_host"]:.1f}%` '
                f'({stats["cpu_logical_count"]} logical CPUs)'
            ),
            inline=True,
        )
        embed.add_field(
            name='Process RSS',
            value=f'`{stats["ram_usage_mib"]:.1f} MiB`',
            inline=True,
        )
        embed.add_field(
            name='Python Traced Memory',
            value=f'`{stats["traced_memory_mib"]:.1f} MiB`',
            inline=True,
        )
        embed.add_field(
            name='Traced Memory Peak',
            value=f'`{stats["traced_peak_mib"]:.1f} MiB`',
            inline=True,
        )
        embed.add_field(
            name='tracemalloc Overhead',
            value=f'`{stats["tracemalloc_overhead_mib"]:.1f} MiB`',
            inline=True,
        )
        embed.add_field(
            name='Allocation Growth: Since Previous Check',
            value=self._format_growth(
                stats['memory_growth_since_previous'],
            ),
            inline=False,
        )
        embed.add_field(
            name='Allocation Growth: Since Monitor Start',
            value=self._format_growth(
                stats['memory_growth_since_start'],
            ),
            inline=False,
        )

        return embed
