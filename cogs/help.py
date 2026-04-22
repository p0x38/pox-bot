from typing import Optional, Union
from discord.ext import commands
from discord import Embed, Interaction, app_commands

from bot import PoxBot

def _get_command_signature(command: Union[app_commands.Command, app_commands.Group], prefix: str = "") -> str:
    """Recursively formats the command name and its parameters."""
    
    # Base command name (Group or Command)
    full_name = f"/{prefix}{command.name}" if prefix else f"/{command.name}"
    
    # Check if it's a Command (has options)
    if isinstance(command, app_commands.Command):
        
        # Build parameter string from options
        params = []
        for option in command.parameters:
            name = option.name
            type_str = option.display_name # Use display_name for user-friendly type
            
            # Check for required vs. optional
            if option.required:
                params.append(f"<{name}: {type_str}>")
            else:
                params.append(f"[{name}: {type_str}]")

        sig = f"{full_name} {' '.join(params)}"
        return f"{sig} - {command.description or '...'}"
    
    # If it's a Group, we'll stop here for the main help list (groups without subcommands
    # don't execute, but let's list them just by name)
    elif isinstance(command, app_commands.Group):
        # Recursively get signatures for all subcommands
        subcommand_lines = []
        for subcommand in command.commands:
            # The prefix for a subcommand is "parent_group subcommand"
            new_prefix = f"{prefix}{command.name} " if prefix else f"{command.name} "
            subcommand_lines.append(_get_command_signature(subcommand, prefix=new_prefix))
        
        # If the group has no subcommands, just show the group name
        if not subcommand_lines:
            return f"{full_name} - {command.description or '...'}"
        
        # Join the subcommands together, indented for clarity
        return "\n".join(subcommand_lines)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.command_map = {}
        self.commands_per_page = 12
    
    @app_commands.command(name="help_v2")
    async def help_command(self, interaction: Interaction, index_number: Optional[int] = 0):
        if index_number is None:
            index_number = 0

        e = Embed(title="Bot Commands")
        
        all_commands = self.bot.tree.get_commands()
        
        if index_number > (round(len(all_commands) / self.commands_per_page) - 1):
            await interaction.response.send_message("Requested search index is larger than list length.",ephemeral=True)
            return
        
        remaining = len(all_commands) - len(all_commands[:(index_number + 1) * self.commands_per_page])
        limited_commands = all_commands[(index_number * self.commands_per_page):(index_number + 1) * self.commands_per_page]

        lines = []

        lines.append(f"Index: {index_number} / {(round(len(all_commands) / self.commands_per_page) - 1)}")
        lines.append(f"Remaining: {remaining}")
        
        for command in limited_commands:
            if not isinstance(command, app_commands.ContextMenu):
                lines.append(_get_command_signature(command))
        
        e.description = "\n".join(lines)
        
        await interaction.response.send_message(embed=e, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))