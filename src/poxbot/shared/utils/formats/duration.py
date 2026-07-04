from datetime import timedelta


def format_duration(n: float) -> str:
    ms = n * 1000

    if ms < 100:
        return f'{ms:.2f}ms'
    if n < 1:
        return f'{int(round(ms))}ms'
    if n < 10:
        return f'{n:.2f}s'
    if n < 60:
        return f'{int(round(n))}s'

    duration = timedelta(seconds=n)
    days = duration.days
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f'{days}d')
    if hours > 0:
        parts.append(f'{hours}h')
    if minutes > 0:
        parts.append(f'{minutes}m')
    if seconds > 0:
        parts.append(f'{seconds}s')

    return ' '.join(parts)
