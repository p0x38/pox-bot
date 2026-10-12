import contextlib
from datetime import timedelta
from time import monotonic, time
from typing import Any

from discord import (
    Color,
    Embed,
    File,
    Interaction,
    app_commands,
)
from discord.ext import commands

from ....application import PoxBot
from ....features.tts.manager import TTSManager
from ....shared.enums.tts import TTSEngineType
from ....shared.exceptions.tts_error import EmptyInputError
from ....shared.utils.fuzzy_search import fuzzy_search_objects


class TextToSpeechCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.tts_manager = TTSManager(bot)

    async def cog_load(self):
        await self.tts_manager.cog_load()

    async def googletts_autocomplete(
        self,
        _interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        google_engine = self.tts_manager.engines.get(TTSEngineType.GOOGLE_TTS)

        gtts_languages = getattr(google_engine, 'gtts_languages', {})

        matched_items = fuzzy_search_objects(
            current,
            gtts_languages.items(),
            lambda item: [item[0], item[1]],
        )
        return [
            app_commands.Choice(name=full, value=code) for code, full in matched_items
        ]

    async def edgetts_autocomplete(
        self,
        _interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        edge_engine = self.tts_manager.engines.get(TTSEngineType.EDGE_TTS)

        edge_tts_voices = getattr(edge_engine, 'edge_tts_voices', {})

        matched_items = fuzzy_search_objects(
            current,
            edge_tts_voices,
            lambda v: [getattr(v, 'name', ''), getattr(v, 'friendly_name', '')],
        )
        return [
            app_commands.Choice(
                name=getattr(v, 'friendly_name', ''),
                value=getattr(v, 'name', ''),
            )
            for v in matched_items
        ]

    async def pockettts_autocomplete(
        self,
        _interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        pocket_engine = self.tts_manager.engines.get(TTSEngineType.POCKET_TTS)

        custom_models = getattr(pocket_engine, 'custom_models', [])
        builtin_models = getattr(pocket_engine, 'builtin_models', [])

        all_models = custom_models + builtin_models

        matched_models = fuzzy_search_objects(
            current,
            all_models,
            lambda m: [m.name, m.friendly_name],
        )

        choices = []
        for model_info in matched_models:
            if model_info in custom_models:
                display_name = f'{model_info.friendly_name} (Custom)'
            else:
                display_name = f'{model_info.name} (Built-in)'

            choices.append(
                app_commands.Choice(name=display_name, value=str(model_info.model)),
            )
        return choices

    async def pipertts_autocomplete(
        self,
        _interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        allowed_voices = self.bot.settings.piper_tts.allowed_voices

        matched_voices = fuzzy_search_objects(
            current,
            allowed_voices,
            lambda voice: [voice],
        )

        return [
            app_commands.Choice(
                name=voice,
                value=voice,
            )
            for voice in matched_voices[:25]
        ]

    async def voice_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        engine_value = getattr(interaction.namespace, 'engine', None)

        try:
            engine = TTSEngineType(engine_value)
        except (TypeError, ValueError):
            return []

        if engine is TTSEngineType.PIPER_TTS:
            return await self.pipertts_autocomplete(interaction, current)

        if engine is TTSEngineType.GOOGLE_TTS:
            return await self.googletts_autocomplete(interaction, current)

        if engine is TTSEngineType.EDGE_TTS:
            return await self.edgetts_autocomplete(interaction, current)

        if engine is TTSEngineType.POCKET_TTS:
            return await self.pockettts_autocomplete(interaction, current)

        return []

    async def _generate_tts(
        self, interaction: Interaction, request_data: dict[str, Any]
    ):
        await interaction.response.defer(thinking=True)

        with contextlib.suppress(Exception):
            await self.tts_manager.generate_speech(request_data)

    @app_commands.command(
        name='tts',
        description=app_commands.locale_str('command.tts.description'),
    )
    @app_commands.autocomplete(voice=voice_autocomplete)
    @app_commands.describe(
        text=app_commands.locale_str('command.tts.parameters.text'),
        engine=app_commands.locale_str('command.tts.parameters.engine'),
        voice=app_commands.locale_str('command.tts.parameters.voice'),
    )
    async def generate_tts(
        self,
        interaction: Interaction,
        text: str,
        engine: TTSEngineType,
        voice: str | None = None,
    ):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(thinking=True)

        if engine is TTSEngineType.PIPER_TTS:
            selected_voice = voice or self.bot.settings.piper_tts.default_voice

            status = self.bot.internal_translator.T(
                'command.tts.texts.status.piper',
                loc,
                {'voice': selected_voice},
            )
        else:
            status = self.bot.internal_translator.T(
                'command.tts.texts.status.generating',
                loc,
            )

        await interaction.edit_original_response(content=status)

        embed = Embed()

        def _assert_valid_result(res: Any) -> None:
            if not res or not getattr(res, 'output', None):
                raise EmptyInputError()

        progress_callback = None

        if engine is TTSEngineType.PIPER_TTS:
            progress_state = {
                'start_time': monotonic(),
                'last_update': 0.0,
                'last_percent': 0,
                'last_bytes': 0,
            }

            async def on_piper_progress(
                filename: str,
                downloaded_bytes: int,
                total_bytes: int,
            ) -> None:
                now = monotonic()
                downloaded_mib = downloaded_bytes / (1024 * 1024)

                elapsed = now - progress_state['start_time']

                if (
                    total_bytes > 0
                    and downloaded_bytes >= 1024 * 1024
                    and elapsed >= 2
                ):
                    bytes_per_second = downloaded_bytes / elapsed
                    remaining_bytes = max(0, total_bytes - downloaded_bytes)
                    remaining_seconds = remaining_bytes / bytes_per_second

                    eta = str(timedelta(seconds=round(remaining_seconds)))
                else:
                    eta = self.bot.internal_translator.T(
                        'command.tts.texts.status.eta_estimating',
                        loc,
                    )

                if total_bytes > 0:
                    percent = min(
                        100,
                        int(downloaded_bytes * 100 / total_bytes),
                    )

                    should_update = percent == 100 or (
                        percent >= progress_state['last_percent'] + 5
                        and now - progress_state['last_update'] >= 2
                    )

                    total_mib = total_bytes / (1024 * 1024)
                    progress = (
                        f'{percent}% ({downloaded_mib:.1f} / {total_mib:.1f} MiB)'
                    )
                else:
                    percent = None
                    should_update = (
                        downloaded_bytes
                        >= progress_state['last_bytes'] + 5 * 1024 * 1024
                        and now - progress_state['last_update'] >= 2
                    )
                    progress = f'{downloaded_mib:.1f} MiB downloaded'

                if not should_update:
                    return

                progress_state['last_update'] = now
                progress_state['last_bytes'] = downloaded_bytes

                if percent is not None:
                    progress_state['last_percent'] = percent

                progress_status = self.bot.internal_translator.T(
                    'command.tts.texts.status.piper_download',
                    loc,
                    {
                        'voice': voice or self.bot.settings.piper_tts.default_voice,
                        'filename': filename,
                        'progress': progress,
                        'eta': eta,
                    },
                )

                try:
                    await interaction.edit_original_response(
                        content=progress_status,
                    )
                except Exception:
                    self.bot.logger.debug(
                        'Failed to update Piper download progress message.',
                        exc_info=True,
                    )

            progress_callback = on_piper_progress

        try:
            data = {'input': text, 'engine': engine, 'voice': voice}
            result = await self.tts_manager.generate_speech(
                data,
                progress_callback=progress_callback,
            )

            _assert_valid_result(result)

            filename = (
                f'{str(engine.name).replace(" ", "")}_{int(time())!s}.'
                + result.media_type
            )

            file = File(result.output, filename)

            embed.color = Color.green()
            embed.set_footer(
                text=f'Generated by {interaction.user.display_name}',
                icon_url=interaction.user.display_avatar.url,
            )

            duration = result.metrics.duration
            chunk_count = result.metrics.chunk_count

            temp_tts = {
                'tts_input': text,
                'tts_engine': str(engine.name),
                'tts_voice': voice if voice else 'None',
            }

            if isinstance(duration, timedelta):
                temp_tts['tts_generation_took'] = f'{duration.total_seconds():.3f}'

            if chunk_count > 0:
                temp_tts['tts_chunk'] = str(chunk_count)

            temp_tts = self.bot.internal_translator.translate_map(temp_tts, str(loc))

            for name, value in temp_tts.items():
                embed.add_field(name=name, value=value, inline=True)

            await interaction.edit_original_response(
                content=None,
                embed=embed,
                attachments=[file],
            )
        except Exception as e:
            self.bot.logger.exception('Unexpected exception raised')
            embed.color = Color.red()
            embed.title = self.bot.internal_translator.T(
                'error.embeds.generic.title',
                loc,
            )
            embed.description = str(e)

            await interaction.edit_original_response(content=None, embed=embed)


async def setup(bot):
    await bot.add_cog(TextToSpeechCog(bot))
