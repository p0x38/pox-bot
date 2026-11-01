from datetime import timedelta

import pytest
from discord import ClientStatus, Status, app_commands

from poxbot.shared.enums.app_command_context import (
    AppCommandContextFlag,
    AppInstallationFlag,
)
from poxbot.shared.utils.formats.app_command_context import (
    context_to_intflag,
    installation_type_to_intflag,
)
from poxbot.shared.utils.formats.boolean import format_boolean
from poxbot.shared.utils.formats.duration import format_duration, parse_duration
from poxbot.shared.utils.formats.probability import parse_probability
from poxbot.shared.utils.formats.status import format_status
from poxbot.shared.utils.fuzzy_search import fuzzy_search_objects
from poxbot.shared.utils.math_util import approach_target, clamp, get_next_power_of_two


def test_format_boolean_distinguishes_false_from_missing() -> None:
    assert format_boolean(True) == "Yes"
    assert format_boolean(False) == "No"
    assert format_boolean(None) == "None"


def test_format_boolean_supports_custom_labels() -> None:
    assert format_boolean(True, "enabled", "disabled", "unknown") == "enabled"
    assert format_boolean(False, "enabled", "disabled", "unknown") == "disabled"
    assert format_boolean(None, "enabled", "disabled", "unknown") == "unknown"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("90", timedelta(seconds=90)),
        ("1w 2d 3h 4m 5s", timedelta(weeks=1, days=2, hours=3, minutes=4, seconds=5)),
        ("2h30m", timedelta(hours=2, minutes=30)),
        ("1:02", timedelta(minutes=1, seconds=2)),
        ("1:02:03", timedelta(hours=1, minutes=2, seconds=3)),
        ("1:02:03:04", timedelta(days=1, hours=2, minutes=3, seconds=4)),
        ("  15S ", timedelta(seconds=15)),
    ],
)
def test_parse_duration(value: str, expected: timedelta) -> None:
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["", " ", "abc", "1x", "1:2:3:4:5", "-1s"])
def test_parse_duration_rejects_invalid_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.05, "50.00ms"),
        (0.5, "500ms"),
        (5, "5.00s"),
        (15, "15s"),
        (61, "1m 1s"),
        (90061, "1d 1h 1m 1s"),
    ],
)
def test_format_duration(value: float, expected: str) -> None:
    assert format_duration(value) == expected


@pytest.mark.parametrize(
    ("value", "expected", "maxv"),
    [
        ("30%", 0.3, 1.0),
        ("1/2", 0.5, 1.0),
        ("0.125", 0.125, 1.0),
        (0.75, 0.75, 1.0),
        (50, 50.0, 100.0),
    ],
)
def test_parse_probability(
    value: str | int | float,
    expected: float,
    maxv: float,
) -> None:
    assert parse_probability(value, maxv=maxv) == expected


@pytest.mark.parametrize(
    "value",
    [
        True,
        "",
        " ",
        "abc",
        "1/0",
        "-0.1",
        "1.1",
        float("nan"),
        float("inf"),
    ],
)
def test_parse_probability_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        parse_probability(value)  # type: ignore[arg-type]


def test_parse_probability_validates_maximum() -> None:
    with pytest.raises(ValueError, match="max"):
        parse_probability("0.5", maxv=-1)
    with pytest.raises(ValueError, match="max"):
        parse_probability("0.5", maxv=float("inf"))


def test_fuzzy_search_matches_case_insensitively_and_deduplicates_objects() -> None:
    first = {"name": "Apple", "aliases": ["Macintosh", "Pomme"]}
    second = {"name": "Banana", "aliases": ["Plantain"]}

    result = fuzzy_search_objects(
        "aple",
        [first, second],
        lambda item: [item["name"], *item["aliases"]],
        limit=5,
        score_cutoff=60,
    )

    assert result == [first]


def test_fuzzy_search_empty_query_returns_limited_original_choices() -> None:
    choices = ["first", "second", "third"]

    assert fuzzy_search_objects("", choices, lambda item: [item], limit=2) == [
        "first",
        "second",
    ]


def test_fuzzy_search_respects_score_cutoff() -> None:
    assert fuzzy_search_objects(
        "unrelated",
        ["apple"],
        lambda item: [item],
        score_cutoff=100,
    ) == []


def test_clamp_and_next_power_of_two_boundaries() -> None:
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10
    assert get_next_power_of_two(0) == 1
    assert get_next_power_of_two(1) == 2
    assert get_next_power_of_two(7) == 8
    assert get_next_power_of_two(8) == 16


def test_approach_target_is_reproducible_with_a_seed() -> None:
    first = approach_target(10.0, max_iterations=8, seed=42)
    second = approach_target(10.0, max_iterations=8, seed=42)

    assert first == second
    assert 1 <= len(first) <= 9


class _Translator:
    def T(self, key: str, locale: str) -> str:
        translations = {
            "text.status.online": "Online",
            "text.status.dnd": "Do not disturb",
            "text.device.mobile": "Mobile",
            "text.device.desktop": "Desktop",
            "text.device.website": "Website",
        }
        return translations.get(key, key)


def test_format_status_includes_every_reported_platform() -> None:
    client_status = ClientStatus(
        status="online",
        mobile="online",
        desktop="idle",
        web="online",
    )
    bot = type("Bot", (), {"internal_translator": _Translator()})()

    assert format_status(bot, client_status, "en") == "Online (Mobile, Desktop, Website)"


def test_format_status_uses_dnd_translation() -> None:
    client_status = ClientStatus(status=Status.do_not_disturb.value)
    bot = type("Bot", (), {"internal_translator": _Translator()})()

    assert format_status(bot, client_status, "en") == "Do not disturb"


def test_application_command_context_flags() -> None:
    context = app_commands.AppCommandContext(
        guild=True,
        dm_channel=False,
        private_channel=True,
    )

    assert context_to_intflag(context) == (
        AppCommandContextFlag.GUILDS | AppCommandContextFlag.PRIVATE
    )


def test_application_installation_flags() -> None:
    installation = app_commands.AppInstallationType(guild=True, user=False)

    assert installation_type_to_intflag(installation) == AppInstallationFlag.GUILD
