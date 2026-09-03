import os
import tracemalloc

import psutil
from discord import Color, Embed


class PerformanceMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.process = psutil.Process(os.getpid())

        if not tracemalloc.is_tracing():
            tracemalloc.start()

        self.last_snapshot = tracemalloc.take_snapshot()

    def get_stats(self) -> dict:
        latency = round(self.bot.latency * 1000, 1) if self.bot.latency else 0.0

        cpu_usage = self.process.cpu_percent(interval=0.1)

        mem_info = self.process.memory_info()
        rss_memory_mb = mem_info.rss / (1024 * 1024)

        current_snapshot = tracemalloc.take_snapshot()
        stats = current_snapshot.compare_to(self.last_snapshot, 'lineno')
        top_stats = [stat for stat in stats[:3] if stat.size_diff > 0]

        self.last_snapshot = current_snapshot

        leak_reports = []
        for stat in top_stats:
            traceback_str = ''.join(stat.traceback.format()).strip().replace('\n', ' ')
            if len(traceback_str) > 80:
                traceback_str = traceback_str[-80:]

            leak_reports.append(
                {
                    'size_diff_kb': stat.size_diff / 1024,
                    'traceback': traceback_str,
                }
            )

        return {
            'latency_ms': latency,
            'cpu_percent': cpu_usage,
            'ram_usage_mb': rss_memory_mb,
            'leaks': leak_reports,
        }

    def create_embed(self, stats: dict) -> Embed:
        embed = Embed(title='Bot performance statistics', color=Color.blue())

        embed.add_field(
            name='API Latency',
            value=f'`{stats["latency_ms"]} ms`',
            inline=True,
        )
        embed.add_field(
            name='CPU Usage',
            value=f'`{stats["cpu_percent"]} %`',
            inline=True,
        )
        embed.add_field(
            name='RAM Usage',
            value=f'`{stats["ram_usage_mb"]:.1f} MB`',
            inline=True,
        )

        leak_msg = ''
        if stats['leaks']:
            for leak in stats['leaks']:
                leak_msg += (
                    f'`+{leak["size_diff_kb"]:.1f} KiB`\n└ `{leak["traceback"]}`\n'
                )
        else:
            leak_msg = 'No leaks have been detected since the last check.'

        embed.add_field(
            name='Trace of Memory leaks (Top 3, vs. previous)',
            value=leak_msg,
            inline=False,
        )
        return embed
