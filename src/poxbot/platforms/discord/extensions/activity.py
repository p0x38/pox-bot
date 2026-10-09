import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime
from importlib import import_module
from random import Random
from typing import Any, ClassVar

import aiofiles
import numpy as np
from aiohttp.client_exceptions import ClientConnectionError
from discord import (
    Activity,
    ActivityType,
    ConnectionClosed,
    CustomActivity,
    HTTPException,
    Status,
)
from discord.ext import commands, tasks
from pytz import UTC

from ....application.bot import PoxBot
from ....shared.utils.formats.probability import parse_probability


def create_japanese_tagger() -> Any | None:
    """Create a Fugashi tokenizer, falling back if unavailable."""
    try:
        fugashi = import_module('fugashi')
        tagger_type = fugashi.Tagger
        return tagger_type()
    except (ImportError, AttributeError, RuntimeError, OSError, ValueError):
        return None


class MarkovStatusGenerator:
    """Variable-order Markov generator for short, multilingual statuses."""

    _BEGIN = '\0BEGIN'
    _END = '\0END'

    _JAPANESE_CHARS = (
        r'\u3040-\u30ff'
        r'\u3400-\u4dbf'
        r'\u4e00-\u9fff'
        r'\uF900-\uFAFF'
        r'々〆ヵヶー'
    )

    _JAPANESE_SPAN_RE = re.compile(
        rf'[{_JAPANESE_CHARS}]+',
    )

    _EMOTICON_RE = re.compile(
        r"(?:<3|[:;=8Xx][-^']?[)(/DdPp3])",
        re.IGNORECASE,
    )

    # ruff: ignore[ambiguous-unicode-character-string]
    _TOKEN_RE = re.compile(
        r'<3'
        r'|(?:[:;=8Xx][-^\']?[)(/DdPp3])'
        r'|[A-Za-z0-9_]+(?:[\'’][A-Za-z0-9_]+)*'
        rf'|[{_JAPANESE_CHARS}]+'
        r'|[^\W\d_]+(?:[\'’][^\W\d_]+)*'
        r'|[^\s]',
        re.UNICODE,
    )

    # ruff: ignore[ambiguous-unicode-character-string]
    _NO_SPACE_BEFORE: ClassVar[set] = set(
        '.,!?;:%)]}…。，、？！。；：」』）】〉》〕］｝”’'
    )

    # ruff: ignore[ambiguous-unicode-character-string]
    _NO_SPACE_AFTER: ClassVar[set] = set('([{「『（【〈《〔［｛“‘')

    def __init__(
        self,
        order: int = 3,
        *,
        japanese_tagger: Any | None = None,
        seed: int | None = None,
    ) -> None:
        if order < 1:
            raise ValueError('order must be at least 1')

        self.order = order
        self._rng = Random(seed)
        self._japanese_tagger = japanese_tagger

        self._transitions: defaultdict[
            tuple[str, ...],
            Counter[str],
        ] = defaultdict(Counter)

        self._sentence_count = 0

        self._seed_contexts: list[tuple[str, ...]] = []
        self._source_texts: set[str] = set()

    @classmethod
    def _contains_japanese(cls, token: str) -> bool:
        return bool(cls._JAPANESE_SPAN_RE.search(token))

    @classmethod
    def _is_word(cls, token: str) -> bool:
        if cls._EMOTICON_RE.fullmatch(token):
            return False
        
        return any(character.isalnum() for character in token)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize English and Japanese while retaining punctuation."""
        tokens: list[str] = []

        for raw_token in self._TOKEN_RE.findall(text):
            if self._JAPANESE_SPAN_RE.fullmatch(raw_token):
                if self._japanese_tagger is not None:
                    tokens.extend(
                        word.surface for word in self._japanese_tagger(raw_token)
                    )
                else:
                    # Character-level fallback if Fugashi is unavailable.
                    tokens.extend(raw_token)
            else:
                tokens.append(raw_token)

        return tokens

    @classmethod
    def _detokenize(cls, tokens: list[str]) -> str:
        """Reconstruct text using English spacing and Japanese punctuation."""
        output = ''
        previous = ''
        quote_open = False

        for token in tokens:
            if not output:
                output = token

            elif token == '"':
                if not quote_open and previous not in cls._NO_SPACE_AFTER:
                    output += ' '

                output += token
                quote_open = not quote_open

            elif (
                token in cls._NO_SPACE_BEFORE
                or previous in cls._NO_SPACE_AFTER
                or (previous == '"' and quote_open)
                or (cls._contains_japanese(previous) and cls._contains_japanese(token))
            ):
                output += token

            else:
                output += ' ' + token

            previous = token

        return output.strip()

    def train(self, sentences: Iterable[str]) -> None:
        """Replace the existing model with transitions from the supplied text."""
        self._transitions.clear()
        self._seed_contexts.clear()
        self._source_texts.clear()
        self._sentence_count = 0

        for sentence in sentences:
            if not sentence or not sentence.strip():
                continue

            tokens = self._tokenize(sentence)

            if not tokens:
                continue

            self._sentence_count += 1
            self._source_texts.add(
                self._detokenize(tokens).casefold(),
            )

            for index in range(1, len(tokens)):
                max_context = min(self.order, index)

                for size in range(1, max_context + 1):
                    context = tuple(tokens[index - size:index])

                    if any(self._is_word(token) for token in context):
                        self._seed_contexts.append(context)

            sequence = [self._BEGIN] * self.order + tokens + [self._END]

            for index in range(self.order, len(sequence)):
                next_token = sequence[index]

                for size in range(1, self.order + 1):
                    context = tuple(sequence[index - size : index])
                    self._transitions[context][next_token] += 1

    def _get_transitions(
        self,
        history: list[str],
    ) -> Counter[str] | None:
        """Find the longest context with known transitions."""
        max_context = min(self.order, len(history))

        for size in range(max_context, 0, -1):
            context = tuple(history[-size:])
            transitions = self._transitions.get(context)

            if transitions:
                return transitions

        return None

    def _weighted_choice(
        self,
        transitions: Counter[str],
        temperature: float,
    ) -> str:
        """Sample a next token using observed frequencies."""
        items = list(transitions.items())
        max_count = max(count for _, count in items)
        exponent = 1.0 / max(temperature, 1e-6)

        tokens = [token for token, _ in items]
        weights = [(count / max_count) ** exponent for _, count in items]

        return self._rng.choices(
            tokens,
            weights=weights,
            k=1,
        )[0]

    @staticmethod
    def _repeats_ngram(
        generated: list[str],
        candidate: str,
        size: int,
    ) -> bool:
        """Check whether appending a token repeats an existing n-gram."""
        combined = [*generated, candidate]

        if len(combined) < size:
            return False

        target = tuple(combined[-size:])

        return any(
            tuple(combined[index : index + size]) == target
            for index in range(len(combined) - size)
        )

    def generate(
        self,
        *,
        min_words: int = 3,
        max_words: int = 14,
        temperature: float = 0.9,
        no_repeat_ngram_size: int = 3,
    ) -> str:
        """Generate a status while avoiding exact copies of training lines."""
        if self._sentence_count == 0:
            raise RuntimeError(
                'Train the generator before generating statuses.',
            )

        if min_words < 0 or max_words < 1 or min_words > max_words:
            raise ValueError('Invalid minimum or maximum word count.')

        if not math.isfinite(temperature) or temperature <= 0:
            raise ValueError(
                'temperature must be finite and greater than zero.',
            )

        if no_repeat_ngram_size < 0:
            raise ValueError(
                'no_repeat_ngram_size cannot be negative.',
            )

        candidate = ''

        # Retry if a generated status exactly matches a training line.
        for _ in range(8):
            candidate = self._generate_once(
                min_words=min_words,
                max_words=max_words,
                temperature=temperature,
                no_repeat_ngram_size=no_repeat_ngram_size,
            )

            if (
                candidate.strip()
                and candidate.casefold() not in self._source_texts
            ):
                return candidate

        # A small corpus may not contain enough transitions for a novel result.
        return candidate

    def _generate_once(
        self,
        *,
        min_words: int,
        max_words: int,
        temperature: float,
        no_repeat_ngram_size: int,
    ) -> str:
        """Generate a status starting from the beginning of a sentence."""
        history = [self._BEGIN] * self.order
        generated: list[str] = []
        word_count = 0

        max_steps = max(32, max_words * 4 + self.order * 2)

        for _ in range(max_steps):
            transitions = self._get_transitions(history)

            if not transitions:
                break

            choices = dict(transitions)

            if word_count < min_words:
                without_end = {
                    token: count
                    for token, count in choices.items()
                    if token != self._END
                }

                if without_end:
                    choices = without_end

            if word_count >= max_words:
                terminal_choices = {
                    token: count
                    for token, count in choices.items()
                    if token == self._END or not self._is_word(token)
                }

                if terminal_choices:
                    choices = terminal_choices
                else:
                    break

            if no_repeat_ngram_size >= 2 and len(choices) > 1:
                filtered = {
                    token: count
                    for token, count in choices.items()
                    if (
                        token == self._END
                        or not self._repeats_ngram(
                            generated,
                            token,
                            no_repeat_ngram_size,
                        )
                    )
                }

                if filtered:
                    choices = filtered

            next_token = self._weighted_choice(
                Counter(choices),
                temperature,
            )

            if next_token == self._END:
                break

            generated.append(next_token)

            if self._is_word(next_token):
                word_count += 1

            history.append(next_token)

            if len(history) > self.order:
                history = history[-self.order:]

        return self._detokenize(generated)


class ActivityCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.rng = np.random.default_rng()
        self.last_activity_timestamp = datetime.now(UTC)

        self.status_directory = bot.resources.get_asset_path(
            'texts/status/en.txt',
        ).parent

        self.japanese_tagger = create_japanese_tagger()

        self.status_datasets: list[tuple[str, list[str], MarkovStatusGenerator]] = []

        self.watching_chance: float = parse_probability("1/500")
        self.cat_face_chance: float = parse_probability("1/3")

        self.cat_faces = (":3", ">:3", "x3", "3:")

    async def cog_load(self) -> None:
        self.status_datasets.clear()

        if self.japanese_tagger is None:
            self.bot.logger.warning(
                'Fugashi is unavailable; Japanese statuses will use '
                'character-level tokenization.',
            )

        if not self.status_directory.is_dir():
            self.bot.logger.warning(
                'Status directory %s not found.',
                self.status_directory.resolve(),
            )
        else:
            status_files = sorted(
                path
                for path in self.status_directory.glob('??.txt')
                if len(path.stem) == 2 and path.stem.isascii() and path.stem.isalpha()
            )

            for path in status_files:
                try:
                    async with aiofiles.open(
                        path,
                        encoding='utf-8',
                    ) as file:
                        content = await file.read()
                except (OSError, UnicodeError):
                    self.bot.logger.exception(
                        'Failed to read status file %s.',
                        path.resolve(),
                    )
                    continue

                messages = [
                    line.strip() for line in content.splitlines() if line.strip()
                ]

                if not messages:
                    self.bot.logger.warning(
                        'Status file %s contains no messages.',
                        path.resolve(),
                    )
                    continue

                generator = MarkovStatusGenerator(
                    order=3,
                    japanese_tagger=self.japanese_tagger,
                )
                generator.train(messages)

                self.status_datasets.append(
                    (path.stem.lower(), messages, generator),
                )

        if not self.status_datasets:
            self.bot.logger.warning(
                'No valid status datasets found; using fallback status.',
            )

            messages = [
                'It seems there are no status messages loaded.',
            ]

            generator = MarkovStatusGenerator(
                order=3,
                japanese_tagger=self.japanese_tagger,
            )
            generator.train(messages)

            self.status_datasets.append(
                ('fallback', messages, generator),
            )

        self.bot.logger.info(
            'Loaded %d status datasets: %s',
            len(self.status_datasets),
            ', '.join(locale for locale, _, _ in self.status_datasets),
        )

        self.status_check_loop.start()

    async def cog_unload(self) -> None:
        self.status_check_loop.cancel()

    async def generate_status(self) -> dict:
        # Preserve the occasional "Watching You" activity.
        if self.rng.random() < self.watching_chance:
            return {
                'status': Status.online,
                'activity': Activity(
                    type=ActivityType.watching,
                    name='You.',
                ),
            }

        # Pick a language independently for every text-status generation.
        index = int(
            self.rng.integers(0, len(self.status_datasets)),
        )
        locale, messages, generator = self.status_datasets[index]

        try:
            chosen = generator.generate(
                min_words=3,
                max_words=14,
                temperature=0.8,
                no_repeat_ngram_size=3,
            )

            if not chosen.strip():
                raise RuntimeError(
                    'Markov generator returned an empty status.',
                )

            # self.bot.logger.info(
            #     'Status source: MARKOV | locale=%s | status=%r',
            #     locale,
            #     chosen,
            # )

        except (RuntimeError, ValueError):
            self.bot.logger.exception(
                'Markov generation failed for locale %s; '
                'falling back to a source status.',
                locale,
            )
            chosen = str(self.rng.choice(messages))

        if (
            not any(face in chosen for face in self.cat_faces)
            and self.rng.random() < self.cat_face_chance
        ):
            chosen = f"{chosen.rstrip()} {self.rng.choice(self.cat_faces)}"

        return {
            'status': Status.online,
            'activity': CustomActivity(name=chosen),
        }

    @tasks.loop(seconds=30.0)
    async def status_check_loop(self) -> None:
        await self.bot.wait_until_ready()

        try:
            presence_data = await self.generate_status()

            if 'status' in presence_data and 'activity' in presence_data:
                await self.bot.change_presence(
                    status=presence_data['status'],
                    activity=presence_data['activity'],
                )
            else:
                self.bot.logger.warning(
                    'Failed to verify the generated presence_data.',
                )

        except (
            ConnectionClosed,
            ClientConnectionError,
            HTTPException,
        ) as e:
            self.bot.logger.warning(
                'Connection has been closed unexpectedly, with exception %s',
                e,
                exc_info=False,
            )
        except Exception:
            self.bot.logger.exception(
                'Exception thrown while trying to change presence.',
            )
            raise


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(ActivityCog(bot))
