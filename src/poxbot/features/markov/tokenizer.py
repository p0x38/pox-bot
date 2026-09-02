from __future__ import annotations

import re
from collections.abc import Iterable


class MarkovTokenizer:
    """Tokenizes Discord messages for Markov training."""

    TOKEN_PATTERN = re.compile(
        r'https?://\S+'
        r'|<[@#&]!?[0-9]+>'
        r'|<:[^:]+:[0-9]+>'
        r'|[\w]+'
        r'|[^\w\s]',
        re.UNICODE,
    )

    def tokenize(self, text: str) -> list[str]:
        """Convert text into Markov tokens."""
        if not text:
            return []

        return self.TOKEN_PATTERN.findall(text)

    def detokenize(
        self,
        tokens: Iterable[str],
    ) -> str:
        """Convert tokens back into readable text."""
        output = ''

        for token in tokens:
            if not output:
                output = token
                continue

            # Don't put spaces before punctuation.
            if token in '.,!?;:%)]}' or output[-1] in '([{':
                output += token

            else:
                output += ' ' + token

        return output
