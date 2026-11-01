from random import Random

import pytest

from poxbot.dsl import SafeStringPredicateEvaluator


@pytest.mark.parametrize(
    ("expression", "char", "index", "text", "expected"),
    [
        ("char == 'a'", "a", 0, "abc", "keep"),
        ("char != 'a'", "b", 1, "abc", "keep"),
        ("char == 'z'", "a", 0, "abc", "delete"),
        ("index is 1 && prev_char == 'a'", "b", 1, "abc", "keep"),
        ("char in ['a', 'b']", "a", 0, "abc", "keep"),
        ("index >= 1 || char == 'z'", "b", 1, "abc", "keep"),
        ("char.lower() == 'a'", "A", 0, "ABC", "keep"),
        ("char.startswith('a')", "a", 0, "abc", "keep"),
        ("rmatch('[a-z]')", "a", 0, "abc", "keep"),
        ("not is_digit", "a", 0, "abc", "keep"),
        ("index % 2 == 0", "a", 0, "abc", "keep"),
        ("1 in range(3)", "a", 0, "abc", "keep"),
        ("'upper' if char == 'a' else 'lower'", "a", 0, "abc", "upper"),
        ("'upper' if char == 'a' else 'lower'", "b", 1, "abc", "lower"),
    ],
)
def test_safe_predicate_expressions(
    expression: str,
    char: str,
    index: int,
    text: str,
    expected: str,
) -> None:
    evaluator = SafeStringPredicateEvaluator(expression)

    assert evaluator.error_message is None
    assert evaluator.evaluate(char, index, text) == expected


def test_syntax_aliases_are_supported() -> None:
    assert SafeStringPredicateEvaluator("index eq 0").evaluate("a", 0, "a") == "keep"
    assert SafeStringPredicateEvaluator("index neq 0").evaluate("a", 1, "ab") == "keep"
    assert SafeStringPredicateEvaluator("char == 'x' || char == 'a'").evaluate(
        "a",
        0,
        "a",
    ) == "keep"


def test_character_context_exposes_position_and_neighbors() -> None:
    evaluator = SafeStringPredicateEvaluator(
        "prev_char == 'a' && next_char == 'c' && word_idx == 1",
    )

    assert evaluator.evaluate("b", 1, "abc def") == "keep"


def test_seeded_chance_function_is_deterministic() -> None:
    always = SafeStringPredicateEvaluator("chance(1.0)", rng=Random(1))
    never = SafeStringPredicateEvaluator("chance(0.0)", rng=Random(1))

    assert always.evaluate("a", 0, "a") == "keep"
    assert never.evaluate("a", 0, "a") == "delete"


def test_range_function_is_capped() -> None:
    evaluator = SafeStringPredicateEvaluator("1000 in range(1001)")

    assert evaluator.evaluate("a", 0, "a") == "delete"


def test_invalid_syntax_fails_open() -> None:
    evaluator = SafeStringPredicateEvaluator("char === 'a'")

    assert evaluator.node is None
    assert evaluator.error_message is not None
    assert evaluator.evaluate("a", 0, "a") == "keep"


def test_unsupported_function_does_not_execute() -> None:
    evaluator = SafeStringPredicateEvaluator("__import__('os')")

    assert evaluator.evaluate("a", 0, "a") == "keep"
    assert evaluator.error_message is not None
    assert "Undefined variable" in evaluator.error_message


def test_runtime_error_fails_open_and_records_error() -> None:
    evaluator = SafeStringPredicateEvaluator("1 / 0")

    assert evaluator.evaluate("a", 0, "a") == "keep"
    assert evaluator.error_message is not None
    assert evaluator.error_message.startswith("Runtime Error:")


def test_recursion_limit_fails_open() -> None:
    evaluator = SafeStringPredicateEvaluator(f"{'not ' * 55}True")

    assert evaluator.evaluate("a", 0, "a") == "keep"
    assert evaluator.error_message == "Max recursion depth exceeded"
