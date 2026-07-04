from __future__ import annotations

import numpy as np

from ....shared.exceptions.text_transform import CellularAutomataArgumentError
from ..base import ascii_to_ndarray
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class CellularAutomataMaskTransformer(BaseTextTransformer):
    """Mask text using a Conway-like cellular automata grid generation."""

    def _transform(
        self, request: TransformerRequest, *, context: TransformerContext | None = None,
    ) -> str:
        """XOR mask the text bits using a generated cellular automata grid."""
        text = request.text
        options = request.options

        try:
            generations = options.get('generations', 5)
            survival = options.get('survival', [2, 3])
            birth = options.get('birth', [3])
        except (ValueError, TypeError) as e:
            raise CellularAutomataArgumentError() from e

        if (
            generations < 0
            or not isinstance(survival, list)
            or not isinstance(birth, list)
        ):
            raise CellularAutomataArgumentError()

        bits = np.unpackbits(ascii_to_ndarray(text))
        side = int(np.ceil(np.sqrt(bits.size)))
        padded = np.zeros(side * side, dtype=np.uint8)
        padded[: bits.size] = bits

        grid = padded.reshape(side, side)

        for _ in range(generations):
            neighbours = (
                np.roll(grid, 1, 0)
                + np.roll(grid, -1, 0)
                + np.roll(grid, 1, 1)
                + np.roll(grid, -1, 1)
            )

            survive_mask = np.isin(neighbours, survival)
            birth_mask = np.isin(neighbours, birth)

            grid = np.where(
                (grid == 1) & survive_mask,
                1,
                np.where((grid == 0) & birth_mask, 1, 0),
            )

        masked = bits ^ grid.ravel()[: bits.size]
        return np.packbits(masked).tobytes().decode('ascii', errors='replace')
    
    @classmethod
    def _parse_int_list(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, list):
            return value
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    
    @classmethod
    def parse_options(cls, **options):
        return {
            "generations": int(options.get("generations", 5)),
            "survival": cls._parse_int_list(options.get("survival", [2, 3])),
            "birth": cls._parse_int_list(options.get("birth", [3])),
        }
