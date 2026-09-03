import re
from datetime import timedelta

DURATION_REGEX = re.compile(
    r'(?:(?P<weeks>\d+)\s*w)?\s*'
    r'(?:(?P<days>\d+)\s*d)?\s*'
    r'(?:(?P<hours>\d+)\s*h)?\s*'
    r'(?:(?P<minutes>\d+)\s*m)?\s*'
    r'(?:(?P<seconds>\d+)\s*s)?',
    re.IGNORECASE,
)


def format_duration(n: float) -> str:
    ms = n * 1000

    if ms < 100:
        return f'{ms:.2f}ms'
    if n < 1:
        return f'{round(ms)}ms'
    if n < 10:
        return f'{n:.2f}s'
    if n < 60:
        return f'{round(n)}s'

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


def parse_duration(text: str) -> timedelta:
    text = text.strip().lower()

    if text.isdigit():
        return timedelta(seconds=int(text))

    if ':' in text:
        parts = text.split(':')

        if len(parts) == 2:
            m, s = parts
            return timedelta(minutes=int(m), seconds=int(s))
        if len(parts) == 3:
            h, m, s = parts
            return timedelta(hours=int(h), minutes=int(m), seconds=int(s))
        if len(parts) == 4:
            d, h, m, s = parts
            return timedelta(
                days=int(d),
                hours=int(h),
                minutes=int(m),
                seconds=int(s),
            )
        raise ValueError()

    match = DURATION_REGEX.fullmatch(text)
    if match:
        parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
        return timedelta(**parts)

    raise ValueError()
