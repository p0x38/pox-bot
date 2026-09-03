import asyncio
import json
from pathlib import Path
from typing import Any

from discord import app_commands
from discord.ext import commands

from poxbot.application import PoxBot
from poxbot.infrastructure.logger import get_logger
from poxbot.shared.utils import app_dir

from ....shared.utils.formats import (
    context_to_intflag,
    installation_type_to_intflag,
)


class ExporterExtension(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.filename = 'commands.json'
        self.logger = get_logger(
            __name__,
            prefix='Exporter',
            extension='ExporterExtension',
        )

    def _generate_commands_json(self) -> list:
        all_slash_commands = self.bot.tree.get_commands()
        exported_data = []

        def parse_slash_command(
            cmd: app_commands.Command | app_commands.Group | app_commands.ContextMenu,
            parent_name: str = '',
        ) -> dict[str, Any]:
            full_name = f'{parent_name} {cmd.name}'.strip()

            if isinstance(cmd, app_commands.Group):
                subcommands_data = [
                    parse_slash_command(sub_cmd, parent_name=full_name)
                    for sub_cmd in cmd.commands
                ]

                return {
                    'type': 'group',
                    'name': cmd.name,
                    'full_name': full_name,
                    'description': str(cmd.description),
                    'sub_commands': subcommands_data,
                    'allowed_context_flag': (
                        int(context_to_intflag(cmd.allowed_contexts))
                        if cmd.allowed_contexts
                        else 0
                    ),
                    'allowed_install_flag': (
                        int(installation_type_to_intflag(cmd.allowed_installs))
                        if cmd.allowed_installs
                        else 0
                    ),
                    'is_nsfw': cmd.nsfw,
                }
            if isinstance(cmd, app_commands.Command):
                parameters_data = []

                for param in cmd.parameters:
                    param_type = str(param.type).replace('AppCommandOptionType.', '')

                    parameters_data.append(
                        {
                            'name': param.name,
                            'display': param.display_name,
                            'description': str(param.description),
                            'type': param_type,
                            'required': param.required,
                            'has_autocomplete': bool(param.autocomplete),
                            'choices': (
                                [choice.name for choice in param.choices]
                                if param.choices
                                else []
                            ),
                        }
                    )

                return {
                    'type': 'slash_command',
                    'name': cmd.name,
                    'full_name': full_name,
                    'description': str(cmd.description),
                    'arguments': parameters_data,
                    'allowed_context_flag': (
                        int(context_to_intflag(cmd.allowed_contexts))
                        if cmd.allowed_contexts
                        else 0
                    ),
                    'allowed_install_flag': (
                        int(installation_type_to_intflag(cmd.allowed_installs))
                        if cmd.allowed_installs
                        else 0
                    ),
                    'is_nsfw': cmd.nsfw,
                }
            if isinstance(cmd, app_commands.ContextMenu):
                return {
                    'type': 'context_menu',
                    'name': cmd.name,
                    'full_name': full_name,
                }

            return {}

        def parse_prefix_command(
            cmd: commands.Command | commands.Group,
            parent_name: str = '',
        ) -> dict[str, Any]:
            full_name = f'{parent_name} {cmd.name}'.strip()

            parameters_data = []
            for param_name, param in cmd.clean_params.items():
                param_type = getattr(
                    param.annotation,
                    '__name__',
                    str(param.annotation),
                )
                if 'inspect._empty' in param_type:
                    param_type = 'Any'

                is_required = param.default is param.empty
                parameters_data.append(
                    {
                        'name': param_name,
                        'type': param_type,
                        'required': is_required,
                        'default': str(param.default) if not is_required else None,
                    }
                )

            base_data = {
                'name': cmd.name,
                'full_name': full_name,
                'aliases': cmd.aliases,
                'description': cmd.help or cmd.brief or '',
                'arguments': parameters_data,
            }

            if isinstance(cmd, commands.Group):
                subcommands_data = [
                    parse_prefix_command(sub_cmd, parent_name=full_name)
                    for sub_cmd in cmd.commands
                ]

                base_data['type'] = 'prefix_group'
                base_data['sub_commands'] = subcommands_data
            else:
                base_data['usage'] = cmd.usage
                base_data['type'] = 'prefix_command'

            return base_data

        for cmd in all_slash_commands:
            data = parse_slash_command(cmd)
            if data:
                exported_data.append(data)

        exported_data.extend(
            parse_prefix_command(cmd) for cmd in self.bot.commands if cmd.parent is None
        )

        return exported_data

    def _save_to_file(self) -> Path:
        commands_list = self._generate_commands_json()

        save_path = app_dir.user_data_path / self.filename

        with save_path.open('w', encoding='utf-8') as f:
            json.dump(commands_list, f, indent=4, ensure_ascii=False)

        return save_path

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await asyncio.sleep(2)
            path = self._save_to_file()
            self.logger.info("Auto-exported command tree to '%s' on startup!", path)
        except Exception as e:
            self.logger.exception('Failed to auto-export commands on ready: %s', e)


async def setup(bot: PoxBot):
    await bot.add_cog(ExporterExtension(bot))
