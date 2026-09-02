from __future__ import annotations

import base64

from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class Base64Transformer(BaseTextTransformer):
    """Encodes to & Decodes from Base64."""
    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        if request.decode:
            return base64.b64decode(request.text).decode('utf-8')
        
        return base64.b64encode(
            request.text.encode("utf-8"),
        ).decode("ascii")
