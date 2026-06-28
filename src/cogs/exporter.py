import asyncio
import json
import os
from typing import Any

from discord import app_commands
from discord.ext import commands

from logger import logger
from src.bot import PoxBot


class ExporterCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

    def _generate_commands_json(self) -> list:
        all_slash_commands = self.bot.tree.get_commands()
        exported_data = []

        def parse_slash_command(
            cmd: app_commands.Command | app_commands.Group | app_commands.ContextMenu,
            parent_name: str = "") -> dict[str, Any]:
            full_name = f"{parent_name} {cmd.name}".strip()

            if isinstance(cmd, app_commands.Group):
                subcommands_data = []
                for sub_cmd in cmd.commands:
                    subcommands_data.append(parse_slash_command(sub_cmd, parent_name=full_name))

                return {
                    "type": "group",
                    "name": cmd.name,
                    "full_name": full_name,
                    "description": str(cmd.description),
                    "sub_commands": subcommands_data,
                    "allowed_contexts": str(cmd.allowed_contexts),
                    "allowed_installs": str(cmd.allowed_installs)
                }
            elif isinstance(cmd, app_commands.Command):
                parameters_data = []

                for param in cmd.parameters:
                    param_type = str(param.type).replace("AppCommandOptionType.", "")

                    parameters_data.append({
                        "name": param.name,
                        "display": param.display_name,
                        "description": str(param.description),
                        "type": param_type,
                        "required": param.required,
                        "has_autocomplete": bool(param.autocomplete),
                        "choices": (
                            [choice.name for choice in param.choices]
                            if param.choices else []
                        )
                    })

                return {
                    "type": "slash_command",
                    "name": cmd.name,
                    "full_name": full_name,
                    "description": str(cmd.description),
                    "arguments": parameters_data,
                    "allowed_contexts": str(cmd.allowed_contexts),
                    "allowed_installs": str(cmd.allowed_installs)
                }
            elif isinstance(cmd, app_commands.ContextMenu):
                return {
                    "type": "context_menu",
                    "name": cmd.name,
                    "full_name": full_name
                }

            return {}

        def parse_prefix_command(cmd: commands.Command | commands.Group,
                                 parent_name: str = "") -> dict[str, Any]:
            full_name = f"{parent_name} {cmd.name}".strip()

            parameters_data = []
            for param_name, param in cmd.clean_params.items():
                param_type = getattr(param.annotation, "__name__", str(param.annotation))
                if "inspect._empty" in param_type:
                    param_type = "Any"

                is_required = param.default is param.empty
                parameters_data.append({
                    "name": param_name,
                    "type": param_type,
                    "required": is_required,
                    "default": str(param.default) if not is_required else None
                })

            base_data = {
                "name": cmd.name,
                "full_name": full_name,
                "aliases": cmd.aliases,
                "description": cmd.help or cmd.brief or "",
                "arguments": parameters_data
            }

            if isinstance(cmd, commands.Group):
                subcommands_data = []
                for sub_cmd in cmd.commands:
                    subcommands_data.append(parse_prefix_command(sub_cmd, parent_name=full_name))

                base_data["type"] = "prefix_group"
                base_data["sub_commands"] = subcommands_data
            else:
                base_data["usage"] = cmd.usage
                base_data["type"] = "prefix_command"

            return base_data

        for cmd in all_slash_commands:
            data = parse_slash_command(cmd)
            if data:
                exported_data.append(data)

        for cmd in self.bot.commands:
            if cmd.parent is None:
                exported_data.append(parse_prefix_command(cmd))

        return exported_data

    def _save_to_file(self) -> str:
        commands_list = self._generate_commands_json()

        save_path = "commands.json"
        if hasattr(self.bot, "root_path") and self.bot.root_path:
            save_path = os.path.join(self.bot.root_path, "commands.json")

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(commands_list, f, indent=4, ensure_ascii=False)

        return save_path

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await asyncio.sleep(2)
            path = self._save_to_file()
            logger.info(f"Auto-exported command tree to '{path}' on startup!")
        except Exception as e:
            logger.error(f"Failed to auto-export commands on ready: {e}")


async def setup(bot: PoxBot):
    await bot.add_cog(ExporterCog(bot))
