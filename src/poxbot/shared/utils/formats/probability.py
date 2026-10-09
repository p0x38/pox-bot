import math
from fractions import Fraction


def parse_probability(
    value: str | int | float,
    *,
    maxv: float = 1.0,
) -> float:
    """
    Parse a probability expressed as a percentage, fraction, or decimal.

    Args:
        value: The probability to parse.
        maxv: The maximum permitted result. Defaults to 1.0.

    Examples:
        parse_probability("30%")       -> 0.3
        parse_probability("1/2")       -> 0.5
        parse_probability("0.3")       -> 0.3
        parse_probability(0.3)         -> 0.3
        parse_probability(50, max=100) -> 50.0

    Raises:
        ValueError: If the input is invalid or outside the allowed range.
    """
    if isinstance(value, bool):
        raise ValueError("A boolean is not a valid probability.")

    if isinstance(maxv, bool) or not math.isfinite(maxv) or maxv < 0:
        raise ValueError("max must be a finite, non-negative number.")

    try:
        if isinstance(value, str):
            text = value.strip()

            if not text:
                raise ValueError("Probability cannot be empty.")

            if text.endswith("%"):
                probability = float(
                    Fraction(text[:-1].strip()) / 100,
                )
            else:
                probability = float(Fraction(text))
        else:
            probability = float(value)

    except (ValueError, ZeroDivisionError, TypeError, OverflowError) as exc:
        raise ValueError(
            f"Invalid probability: {value!r}",
        ) from exc

    if (
        not math.isfinite(probability)
        or not 0.0 <= probability <= maxv
    ):
        raise ValueError(
            f"Probability must be between 0 and {maxv}: {value!r}",
        )

    return probability
