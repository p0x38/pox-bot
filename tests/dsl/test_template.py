import pytest

from poxbot.dsl.template_parser import (
    TemplateError,
    render_template,
    validate_template,
)

CONTEXT: dict[str, object] = {
    'user': {
        'mention': '<@123>',
        'name': 'pox',
        'display': 'Pox',
        'avatar': 'https://example.com/avatar.png',
    },
    'server': {
        'name': 'Galaxy SMP',
        'members': 42,
    },
}


def test_render_placeholders() -> None:
    result = render_template(
        'Hello {user.mention}! Welcome to {server.name}!',
        CONTEXT,
    )

    assert result == 'Hello <@123>! Welcome to Galaxy SMP!'


def test_render_aliases() -> None:
    assert render_template('{user} | {server}', CONTEXT) == ('<@123> | Galaxy SMP')


def test_render_humanize() -> None:
    assert (
        render_template(
            "You're the {humanize, server.members} member!",
            CONTEXT,
        )
        == "You're the 42nd member!"
    )


@pytest.mark.parametrize(
    ('number', 'expected'),
    [
        (1, '1st'),
        (2, '2nd'),
        (3, '3rd'),
        (4, '4th'),
        (11, '11th'),
        (12, '12th'),
        (13, '13th'),
        (21, '21st'),
        (22, '22nd'),
        (23, '23rd'),
        (111, '111th'),
        (0, '0th'),
        (-1, '-1st'),
    ],
)
def test_ordinal_suffixes(number: int, expected: str) -> None:
    context: dict[str, object] = {
        **CONTEXT,
        'server': {'name': 'Galaxy SMP', 'members': number},
    }

    assert render_template('{humanize, server.members}', context) == expected


def test_escaped_braces() -> None:
    assert render_template('Use {{user}} literally.', CONTEXT) == (
        'Use {user} literally.'
    )


@pytest.mark.parametrize(
    'template',
    [
        '{unknown}',
        '{user.unknown}',
        '{unknown, server.members}',
        '{humanize, server.name}',
        '{user.name',
        'user.name}',
        'unexpected }',
        '{user.{name}}',
    ],
)
def test_invalid_templates(template: str) -> None:
    with pytest.raises(TemplateError):
        validate_template(template)


def test_missing_context_value() -> None:
    with pytest.raises(TemplateError):
        render_template('{user.name}', {})


def test_output_length_limit() -> None:
    with pytest.raises(TemplateError):
        render_template('x' * 2001, CONTEXT)
