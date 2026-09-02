from poxbot.features.text_transform.models import TransformerRequest
from poxbot.features.text_transform.transformers.cellular_automata import (
    CellularAutomataMaskTransformer,
)


def test_cellular_automata_masking() -> None:
    """Verify Conway rules introduce structural masks successfully."""
    transformer = CellularAutomataMaskTransformer()
    secret = 'Confidential Information'

    masked = transformer.transform(
        TransformerRequest(
            text=secret,
            options={'generations': 2},
        ),
    )

    assert masked.output != secret
