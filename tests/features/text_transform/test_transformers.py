import numpy as np
import pytest

from poxbot.features.text_transform.base import (
    ascii_to_ndarray,
    get_integer_adjugate,
    ndarray_to_ascii,
)
from poxbot.features.text_transform.base_transformer import BaseTextTransformer
from poxbot.features.text_transform.manager import TextTransformManager
from poxbot.features.text_transform.models import TransformerRequest
from poxbot.features.text_transform.transformers.base64 import Base64Transformer
from poxbot.features.text_transform.transformers.caesar import CaesarCipherTransformer
from poxbot.features.text_transform.transformers.predicate import PredicateCaseTransformer
from poxbot.features.text_transform.transformers.reverse import ReverseLetterTransformer
from poxbot.shared.exceptions.text_transform import (
    InvalidCaesarShiftError,
    NoTextTransformerObjectError,
)


def test_ascii_array_round_trip_replaces_non_ascii_characters() -> None:
    array = ascii_to_ndarray("Pox café")

    assert array.dtype == np.uint8
    assert ndarray_to_ascii(array) == "Pox caf?"


def test_integer_adjugate_for_two_by_two_matrix() -> None:
    matrix = np.array([[1, 2], [3, 4]], dtype=int)

    assert get_integer_adjugate(matrix).tolist() == [[4, -2], [-3, 1]]


def test_base_transformer_populates_result_metrics() -> None:
    transformer = Base64Transformer()
    result = transformer.transform(TransformerRequest(text="hello"))

    assert result.transformer == "base64"
    assert result.output == "aGVsbG8="
    assert result.input_length == 5
    assert result.output_length == 8
    assert result.metrics.finished_at >= result.metrics.started_at
    assert result.metrics.elapsed_ms >= 0


def test_base64_transformer_round_trips_unicode() -> None:
    transformer = Base64Transformer()
    encoded = transformer.transform(TransformerRequest(text="Pox こんにちは"))

    decoded = transformer.transform(
        TransformerRequest(text=encoded.output, decode=True),
    )

    assert decoded.output == "Pox こんにちは"


def test_caesar_cipher_round_trip_and_shift_validation() -> None:
    transformer = CaesarCipherTransformer()
    encoded = transformer.transform(
        TransformerRequest(text="Hello, World!", options={"shift": 3}),
    )
    decoded = transformer.transform(
        TransformerRequest(
            text=encoded.output,
            decode=True,
            options={"shift": 3},
        ),
    )

    assert decoded.output == "Hello, World!"

    with pytest.raises(InvalidCaesarShiftError):
        transformer.transform(TransformerRequest(text="hello", options={"shift": 0}))

    with pytest.raises(InvalidCaesarShiftError):
        transformer.transform(TransformerRequest(text="hello", options={"shift": "bad"}))


def test_reverse_transformer_supports_word_and_letter_modes() -> None:
    transformer = ReverseLetterTransformer()

    words = transformer.transform(
        TransformerRequest(text="hello world", options={"type": "words"}),
    )
    letters = transformer.transform(
        TransformerRequest(text="ABC xyz", options={"type": "letters"}),
    )

    assert words.output == "olleh dlrow"
    assert letters.output == "ZYX cba"


def test_reverse_transformer_decode_is_the_inverse_of_letters() -> None:
    transformer = ReverseLetterTransformer()
    encoded = transformer.transform(
        TransformerRequest(text="Pox 38", options={"type": "letters"}),
    )
    decoded = transformer.transform(
        TransformerRequest(
            text=encoded.output,
            decode=True,
            options={"type": "letters"},
        ),
    )

    assert decoded.output == "Pox 38"


def test_predicate_transformer_supports_dsl_actions() -> None:
    transformer = PredicateCaseTransformer()
    result = transformer.transform(
        TransformerRequest(
            text="ab",
            options={"predicate": "'upper' if char == 'a' else 'lower'"},
        ),
    )

    assert result.output == "Ab"


def test_predicate_transformer_supports_callable_actions() -> None:
    transformer = PredicateCaseTransformer()
    result = transformer.transform(
        TransformerRequest(
            text="abcd",
            options={
                "predicate": lambda char, index: (
                    "upper" if index == 0 else
                    "delete" if index == 1 else
                    "reverse" if index == 2 else
                    "keep"
                ),
            },
        ),
    )

    assert result.output == "Axd"


def test_predicate_transformer_falls_back_to_lowercase_on_callable_error() -> None:
    def fail(_char: str) -> bool:
        raise RuntimeError("test failure")

    result = PredicateCaseTransformer().transform(
        TransformerRequest(text="HeLLo", options={"predicate": fail}),
    )

    assert result.output == "hello"


def test_base_transformer_option_coercion_and_validation() -> None:
    assert Base64Transformer.option({"enabled": 1}, "enabled", bool, False) is True
    assert Base64Transformer.option({"count": "3"}, "count", int, 0) == 3
    assert Base64Transformer.option({"ratio": "0.5"}, "ratio", float, 1.0) == 0.5
    assert Base64Transformer.option(
        {"values": [1, 2]},
        "values",
        np.ndarray,
        [],
    ).tolist() == [1, 2]

    with pytest.raises(TypeError, match="label"):
        Base64Transformer.option({"label": 1}, "label", str, "")


def test_transform_manager_discovers_and_executes_transformers() -> None:
    manager = TextTransformManager(seed=42)

    assert "base64" in manager.list_transformers()
    request = manager.create_request("base64", "hello")
    result = manager.transform("base64", request)

    assert result.output == "aGVsbG8="


def test_transform_manager_pipeline_and_missing_transformer() -> None:
    manager = TextTransformManager(seed=42)
    request = TransformerRequest(text="hello")
    result = manager.pipeline(
        request,
        [
            ("base64", {}),
            ("reverse", {"type": "words"}),
        ],
    )

    assert result.output == "=8GbsVGa"

    with pytest.raises(NoTextTransformerObjectError):
        manager.get_transformer("does-not-exist")

    with pytest.raises(ValueError, match="at least one"):
        manager.pipeline(request, [])
