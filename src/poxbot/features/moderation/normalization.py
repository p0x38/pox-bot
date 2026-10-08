import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

_INVISIBLE_CHARACTERS = re.compile(r'[\u200b-\u200f\uFEFF\u202a-\u202e]')
_TRAILING_URL_PUNCTUATION = '.,;:!?)]}>'


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize('NFKC', text)
    normalized = _INVISIBLE_CHARACTERS.sub('', normalized).casefold()
    return re.sub(r'\s+', ' ', normalized).strip()


def normalize_domain(domain: str) -> str:
    value = domain.strip().rstrip('.').casefold()
    if (
        not value
        or any(char in value for char in '/@:#?')
        or any(char.isspace() for char in value)
    ):
        raise ValueError(f'Invalid domain indicator: {domain!r}')

    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        try:
            return value.encode('idna').decode('ascii')
        except UnicodeError as error:
            raise ValueError(f'Invalid domain indicator: {domain!r}') from error


def extract_url_host(url: str) -> str | None:
    candidate = url.strip().rstrip(_TRAILING_URL_PUNCTUATION)
    if not candidate:
        return None

    if not re.match(r'^[a-z][a-z0-9+.-]*://', candidate, re.IGNORECASE):
        candidate = f'//{candidate}'

    try:
        hostname = urlsplit(candidate).hostname
    except ValueError:
        return None

    if not hostname:
        return None

    try:
        return normalize_domain(hostname)
    except ValueError:
        return None


def domain_matches(hostname: str, indicator_domain: str) -> bool:
    return hostname == indicator_domain or hostname.endswith(f'.{indicator_domain}')
