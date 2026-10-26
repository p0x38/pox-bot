import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

MAX_TEMPLATE_LENGTH = 2000

_PATH_PATTERN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')

_ALIASES = {
    'user': 'user.mention',
    'server': 'server.name',
}

_ALLOWED_PATHS = frozenset(
    {
        'user.mention',
        'user.name',
        'user.display',
        'user.avatar',
        'server.name',
        'server.members',
    }
)


class TemplateError(ValueError):
    """Raised when a template is invalid or cannot be rendered."""


@dataclass(frozen=True, slots=True)
class _Literal:
    value: str


@dataclass(frozen=True, slots=True)
class _Expression:
    path: str
    function: str | None = None


_Segment = _Literal | _Expression


def _ordinal(value: object) -> str:
    if isinstance(value, bool):
        raise TemplateError('humanize expects an integer')

    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        try:
            number = int(value)
        except ValueError as exc:
            raise TemplateError('humanize expects an integer') from exc
    else:
        raise TemplateError('humanize expects an integer')

    absolute = abs(number)

    if 10 <= absolute % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {
            1: 'st',
            2: 'nd',
            3: 'rd',
        }.get(absolute % 10, 'th')

    return f'{number}{suffix}'


_FUNCTIONS: dict[str, Callable[[object], str]] = {
    'humanize': _ordinal,
    'ordinal': _ordinal,
}

_FUNCTION_ARGUMENTS = {
    'humanize': frozenset({'server.members'}),
    'ordinal': frozenset({'server.members'}),
}


def _normalize_path(path: str) -> str:
    path = path.strip()

    if not _PATH_PATTERN.fullmatch(path):
        raise TemplateError(f'Invalid placeholder: {path!r}')

    path = _ALIASES.get(path, path)

    if path not in _ALLOWED_PATHS:
        raise TemplateError(f'Unknown placeholder: {path}')

    return path


def _parse_expression(expression: str) -> _Expression:
    expression = expression.strip()

    if not expression:
        raise TemplateError('Empty placeholder')

    if ',' not in expression:
        return _Expression(path=_normalize_path(expression))

    function_name, _, argument = expression.partition(',')
    function_name = function_name.strip()

    if function_name not in _FUNCTIONS:
        raise TemplateError(f'Unknown function: {function_name}')

    path = _normalize_path(argument)

    if path not in _FUNCTION_ARGUMENTS[function_name]:
        raise TemplateError(f'Function {function_name!r} does not support {path!r}')

    return _Expression(path=path, function=function_name)


def _parse_template(template: str) -> tuple[_Segment, ...]:
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise TemplateError(f'Template exceeds {MAX_TEMPLATE_LENGTH} characters')

    segments: list[_Segment] = []
    literal: list[str] = []
    index = 0

    def flush_literal() -> None:
        if literal:
            segments.append(_Literal(''.join(literal)))
            literal.clear()

    while index < len(template):
        if template.startswith('{{', index):
            literal.append('{')
            index += 2
            continue

        if template.startswith('}}', index):
            literal.append('}')
            index += 2
            continue

        char = template[index]

        if char == '{':
            flush_literal()

            closing = template.find('}', index + 1)

            if closing == -1:
                raise TemplateError('Unclosed placeholder')

            expression = template[index + 1 : closing]

            if '{' in expression:
                raise TemplateError('Nested placeholders are not supported')

            segments.append(_parse_expression(expression))
            index = closing + 1
            continue

        if char == '}':
            raise TemplateError('Unexpected closing brace')

        literal.append(char)
        index += 1

    flush_literal()
    return tuple(segments)


def validate_template(template: str) -> None:
    """Validate template syntax without requiring Discord event data."""
    _parse_template(template)


def _resolve_path(
    path: str,
    context: Mapping[str, object],
) -> object:
    value: object = context

    for part in path.split('.'):
        if not isinstance(value, Mapping) or part not in value:
            raise TemplateError(f'Missing context value: {path}')

        value = value[part]

    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TemplateError(f'Invalid value for placeholder: {path}')

    return value


def render_template(
    template: str,
    context: Mapping[str, object],
) -> str:
    """Render a validated template using explicitly supplied values."""
    segments = _parse_template(template)
    output: list[str] = []

    for segment in segments:
        if isinstance(segment, _Literal):
            output.append(segment.value)
            continue

        value = _resolve_path(segment.path, context)

        if segment.function is not None:
            value = _FUNCTIONS[segment.function](value)

        output.append(str(value))

    result = ''.join(output)

    if len(result) > MAX_TEMPLATE_LENGTH:
        raise TemplateError(
            f'Rendered message exceeds {MAX_TEMPLATE_LENGTH} characters'
        )

    return result
