from __future__ import annotations

from pathlib import Path
from typing import Any

from aiocache import cached
from discord import Interaction, app_commands
from discord.ext import commands

from ....application.bot import PoxBot
from ....features.text_transform.models import TransformerRequest
from ....shared.exceptions.text_transform import (
    TextTransformError,
)


class ConversionCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.manager = bot.text_converter
        self.transformers_dir = (
            Path(__file__).parent / 'text_transformers' / 'transformers'
        )

    group = app_commands.Group(
        name='conversion',
        description=app_commands.locale_str('command.conversion.description'),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True,
            dm_channel=True,
            private_channel=True,
        ),
    )

    async def _run_transform(
        self,
        interaction: Interaction,
        transformer: str,
        text: str,
        *,
        decode: bool = False,
        **kwargs: Any,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            request = TransformerRequest(
                text=text,
                decode=decode,
                options=kwargs,
            )

            result = self.manager.transform(
                transformer,
                request,
            )
        except TextTransformError as e:
            await interaction.followup.send(
                f'Failed to convert text: {e}',
            )
        else:
            await interaction.followup.send(
                f'{result.output}\n'
                f'\n'
                f'Took {result.metrics.elapsed_ms:.2f} ms to transform',
            )

    @cached(60)
    @group.command(
        name='caesar',
        description=app_commands.locale_str('command.conversion.caesar.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        shift=app_commands.locale_str('command.conversion.caesar.parameters.shift'),
    )
    async def _caesar_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
        shift: int = 3,
    ):
        await self._run_transform(
            interaction,
            'caesar',
            text,
            decode=decode,
            shift=shift,
        )

    @cached(60)
    @group.command(
        name='binary',
        description=app_commands.locale_str('command.conversion.binary.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        block_size=app_commands.locale_str(
            'command.conversion.binary.parameters.block_size',
        ),
    )
    async def _binary_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
        block_size: int = 8,
    ):
        await self._run_transform(
            interaction,
            'binary',
            text,
            decode=decode,
            block_size=block_size,
        )

    @cached(60)
    @group.command(
        name='cellular_automata_text',
        description=app_commands.locale_str(
            'command.conversion.cellular_automata_text.description',
        ),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        generations=app_commands.locale_str(
            'command.conversion.cellular_automata_text.parameters.generations',
        ),
        survival=app_commands.locale_str(
            'command.conversion.cellular_automata_text.parameters.survival',
        ),
        birth=app_commands.locale_str(
            'command.conversion.cellular_automata_text.parameters.birth',
        ),
    )
    async def _cellular_text_automata_transform(
        self,
        interaction: Interaction,
        text: str,
        generations: int = 5,
        survival: str = '2,3',
        birth: str = '3',
    ):
        await self._run_transform(
            interaction,
            'cellular_automata',
            text,
            generations=generations,
            survival=survival,
            birth=birth,
        )

    @cached(60)
    @group.command(
        name='glitch',
        description=app_commands.locale_str('command.conversion.glitch.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        rate=app_commands.locale_str(
            'command.conversion.glitch.parameters.rate',
        ),
    )
    async def _glitch_transform(
        self,
        interaction: Interaction,
        text: str,
        rate: float = 0.25,
    ):
        await self._run_transform(
            interaction,
            'glitch',
            text,
            rate=rate,
        )

    @cached(60)
    @group.command(
        name='hill',
        description=app_commands.locale_str('command.conversion.hill.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        key_matrix=app_commands.locale_str(
            'command.conversion.hill.parameters.key_matrix',
        ),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        pad_str=app_commands.locale_str(
            'command.conversion.hill.parameters.pad_char',
        ),
    )
    async def _hill_transform(
        self,
        interaction: Interaction,
        text: str,
        key_matrix: str = '3,3;2,5',
        decode: bool = False,
        pad_str: str = 'X',
    ):
        await self._run_transform(
            interaction,
            'hill',
            text,
            decode=decode,
            key_matrix=key_matrix,
            pad_str=pad_str,
        )

    @cached(60)
    @group.command(
        name='image_scramble',
        description=app_commands.locale_str(
            'command.conversion.image_scramble.description',
        ),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        seed=app_commands.locale_str(
            'command.conversion.image_scramble.parameters.seed',
        ),
    )
    async def _image_scramble(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
        seed: int = 42,
    ):
        await self._run_transform(
            interaction,
            'image_scramble',
            text,
            decode=decode,
            seed_key=seed,
        )

    @cached(60)
    @group.command(
        name='morse',
        description=app_commands.locale_str('command.conversion.morse.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        word_separator=app_commands.locale_str(
            'command.conversion.morse.parameters.word_separator',
        ),
    )
    async def _morse_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
        word_separator: str = '/',
    ):
        await self._run_transform(
            interaction,
            'morse',
            text,
            decode=decode,
            word_sep=word_separator,
        )

    @cached(60)
    @group.command(
        name='psc1',
        description=app_commands.locale_str('command.conversion.psc1.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        chunk_size=app_commands.locale_str(
            'command.conversion.psc1.parameters.chunk_size',
        ),
    )
    async def _psc1_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
        chunk_size: int = 42,
    ):
        await self._run_transform(
            interaction,
            'psc1',
            text,
            decode=decode,
            chunk_size=chunk_size,
        )

    @cached(60)
    @group.command(
        name='rail_fence',
        description=app_commands.locale_str(
            'command.conversion.rail_fence.description',
        ),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
        key=app_commands.locale_str(
            'command.conversion.rail_fence.parameters.key',
        ),
    )
    async def _rail_fence_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
        key: int = 2,
    ):
        await self._run_transform(
            interaction,
            'rail_fence',
            text,
            decode=decode,
            key=key,
        )

    @cached(60)
    @group.command(
        name='reverse',
        description=app_commands.locale_str(
            'command.conversion.reverse.description',
        ),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        mode=app_commands.locale_str('command.conversion.reverse.parameters.mode'),
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(
                name=app_commands.locale_str(
                    'command.conversion.reverse.choices.words',
                ),
                value='word',
            ),
            app_commands.Choice(
                name=app_commands.locale_str(
                    'command.conversion.reverse.choices.letters',
                ),
                value='letters',
            ),
            app_commands.Choice(
                name=app_commands.locale_str('command.conversion.reverse.choices.both'),
                value='both',
            ),
        ],
    )
    async def _reverse_letter_transform(
        self,
        interaction: Interaction,
        text: str,
        mode: str = 'words',
    ):
        await self._run_transform(
            interaction,
            'reverse',
            text,
            mode=mode,
        )

    @cached(60)
    @group.command(
        name='mocking',
        description=app_commands.locale_str('command.conversion.mocking.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        mode=app_commands.locale_str(
            'command.conversion.mocking.parameters.mode',
        ),
    )
    async def _mocking_transform(
        self,
        interaction: Interaction,
        text: str,
        mode: str = 'random',
    ):
        await self._run_transform(
            interaction,
            'mocking',
            text,
            mode=mode,
        )

    @cached(60)
    @group.command(
        name='wide',
        description=app_commands.locale_str('command.conversion.wide.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
    )
    async def _wide_transform(
        self,
        interaction: Interaction,
        text: str,
    ):
        await self._run_transform(
            interaction,
            'wide',
            text,
        )

    @cached(60)
    @group.command(
        name='zalgo',
        description=app_commands.locale_str('command.conversion.zalgo.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
    )
    async def _zalgo_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
    ):
        await self._run_transform(
            interaction,
            'zalgo',
            text,
            decode=decode,
        )

    @cached(60)
    @group.command(
        name='uwu',
        description=app_commands.locale_str('command.conversion.uwu.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        stutters=app_commands.locale_str('command.conversion.uwu.parameters.stutters'),
        faces=app_commands.locale_str('command.conversion.uwu.parameters.faces'),
        actions=app_commands.locale_str('command.conversion.uwu.parameters.actions'),
    )
    async def _uwu_transform(
        self,
        interaction: Interaction,
        text: str,
        stutters: app_commands.Range[float, 0, 1] = 0.39,
        faces: app_commands.Range[float, 0, 1] = 0.07,
        actions: app_commands.Range[float, 0, 1] = 0.0,
        lowercase: bool = True,
    ):
        raw_options = {
            'stutter': bool(stutters),
            'faces': bool(faces),
            'actions': bool(actions),
            'lowercase': lowercase,
            'stutter_chance': stutters,
            'stutter_max': 3,
            'face_chance': faces,
            'action_chance': actions,
        }

        parsed_opts = self.bot.text_converter.get_transformer('uwu').parse_options(
            **raw_options
        )

        await self._run_transform(
            interaction,
            'uwu',
            text,
            **parsed_opts,
        )

    @cached(60)
    @group.command(
        name='base64',
        description=app_commands.locale_str('command.conversion.base64.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        decode=app_commands.locale_str('command.conversion.parameters.decode'),
    )
    async def _base64_transform(
        self,
        interaction: Interaction,
        text: str,
        decode: bool = False,
    ):
        await self._run_transform(
            interaction,
            'base64',
            text,
            decode=decode,
        )

    async def predicate_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        suggestions = [
            'idx',
            'index',
            'char',
            'is_vowel',
            'is_alpha',
            'is_digit',
            'is_space',
            'idx % 2 == 0',
            "char in 'aeiou'",
            'idx < 5',
            'not is_space',
        ]

        current_lower = current.lower()

        return [
            app_commands.Choice(name=opt, value=opt)
            for opt in suggestions
            if current_lower in opt.lower()
        ][:25]

    @group.command(
        name='predicate',
        description=app_commands.locale_str('command.conversion.predicate.description'),
    )
    @app_commands.describe(
        text=app_commands.locale_str('command.conversion.parameters.text'),
        predicate=app_commands.locale_str(
            'command.conversion.predicate.parameters.predicate'
        ),
    )
    @app_commands.autocomplete(predicate=predicate_autocomplete)
    async def _custom_predicate_transform(
        self, interaction: Interaction, text: str, predicate: str
    ):
        await self._run_transform(
            interaction,
            'predicate',
            text,
            predicate=predicate,
        )


async def setup(bot: PoxBot):
    await bot.add_cog(ConversionCog(bot))
