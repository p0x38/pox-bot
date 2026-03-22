from discord.ext import commands
from discord import Embed, Forbidden, HTTPException, Interaction, Member, Permissions, Role, app_commands

from bot import PoxBot

from logger import logger

ALLOWED_PERMISSIONS_TO_EDIT = [
    "manage_channels",
    "kick_members",
    "ban_members",
    "administrator",
    "mention_everyone",
    "view_audit_log",
    "manage_nicknames",
    "change_nickname",
    "send_messages",
    "read_message_history",
    "connect",
    "read_messages",
    "request_to_speak",
    "speak",
    "stream",
    "view_channel",
    "send_polls",
    "send_tts_messages",
    "pin_messages",
    "priority_speaker",
]

class RoleGroup(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="role", description="An group for Roles.")

    @group.command(name="give_role", description="Gives member a role.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    async def give_member_role(self, interaction: Interaction, member: Member, role: Role):
        if role in member.roles:
            return await interaction.response.send_message(f"{member.name} has already given that role.")
        
        try:
            await member.add_roles(role, reason=f"Role given by {interaction.user.name}")
            return await interaction.response.send_message(f"Gived role {role.name} to {member.name}.")
        except Forbidden:
            return await interaction.response.send_message("I do not have permission to give him role.")
        except Exception as e:
            raise
    
    @group.command(name="take_role", description="Takes role from member.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    async def take_member_role(self, interaction: Interaction, member: Member, role: Role):
        if role in member.roles:
            return await interaction.response.send_message(f"{member.name} hasn't that role.")
        
        try:
            await member.add_roles(role, reason=f"Role taken by {interaction.user.name}")
            return await interaction.response.send_message(f"Taken role {role.name} from {member.name}.")
        except Forbidden:
            return await interaction.response.send_message("I do not have permission to take role from him.")
        except Exception:
            raise
    
    @group.command(name="list", description="Lists roles.")
    @app_commands.guild_only()
    async def list_roles(self, interaction: Interaction):
        if interaction.guild is None: return await interaction.response.send_message("You're using User-mode.")
        lines = []
        for role in interaction.guild.roles:
            lines.append(f"<@&{role.id}>")
        
        embed = Embed(title="Role list", description="\n".join(lines[::-1]))

        return await interaction.response.send_message(embed=embed)
    
    @group.command(name="user_roles", description="Lists user's role.")
    @app_commands.guild_only()
    async def list_user_roles(self, interaction: Interaction, member: Member):
        if interaction.guild is None: return await interaction.response.send_message("You're using User-mode.")
        lines = []
        for role in member.roles:
            lines.append(f"<@&{role.id}>")
        
        embed = Embed(title=f"{member.name}'s role list", description="\n".join(lines))

        return await interaction.response.send_message(embed=embed)
    
    async def permission_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = [
            app_commands.Choice(name=perm, value=perm)
            for perm in ALLOWED_PERMISSIONS_TO_EDIT if current.lower() in perm.lower()
        ]

        return choices[:25]

    @group.command(name="edit_role", description="Edits role's permission.")
    @app_commands.guild_only()
    @app_commands.autocomplete(permission=permission_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def edit_role_permission(
        self,
        interaction: Interaction,
        role: Role,
        permission: str,
        new_value: bool
    ): 
        if interaction.guild is None: return await interaction.response.send_message("You're using User-mode.")
        if not interaction.guild.me.guild_permissions.manage_roles: return await interaction.response.send_message("I do not have permission to manage roles.")
        if role.position >= interaction.guild.me.top_role.position: return await interaction.response.send_message("I do not have permission to manage roles that is higher than my highest roles.")
        if permission not in ALLOWED_PERMISSIONS_TO_EDIT: return await interaction.response.send_message(f"Permission ID {permission} is not allowed.", ephemeral=True)
        if not hasattr(Permissions, permission): return await interaction.response.send_message(f"Permission {permission} not found.")

        new_perms = role.permissions

        setattr(new_perms, permission, new_value)

        await interaction.response.defer(ephemeral=False)

        try:
            await role.edit(
                permissions=new_perms,
                reason=f"Edited by {interaction.user.name} via /role edit command"
            )

            action = ("Granted {} to role {}." if new_value else "Revoked {} from role {}.").format(permission, role.name)

            return await interaction.followup.send(f"Successfully {action}")
        except Forbidden:
            return await interaction.response.send_message("I don't have the necessary permissions to edit the role.")
        except Exception as e:
            raise
    
    @group.command(name="add_role", description="Adds a role.")
    async def add_role(self, interaction: Interaction, name: str):
        if interaction.guild is None: return await interaction.response.send_message("You're using User-mode.")

        await interaction.response.defer(thinking=True)

        try:
            role = await interaction.guild.create_role(name=name, reason=f"Created by {interaction.user.name} via /role add")
            return await interaction.followup.send("Successfully created role :3", ephemeral=True)
        except Forbidden:
            return await interaction.followup.send("Failed to create role; I do not have permission to add role in guild.")
        except HTTPException as e:
            logger.exception(f"HTTPException: {e}")
            return
        except Exception as e:
            logger.exception(f"Uncaught exception: {e}")
            return
    
    @group.command(name="delete_role", description="Deletes a role.")
    async def delete_role(self, interaction: Interaction, role: Role):
        if interaction.guild is None: return await interaction.response.send_message("You're using User-mode.")

        await interaction.response.defer(thinking=True)

        try:
            await role.delete(reason=f"Deleted by {interaction.user.name} via /role delete")
            return await interaction.followup.send("Successfully deleted role :3", ephemeral=True)
        except Forbidden:
            return await interaction.followup.send("Failed to delete role; I do not have permission to delete role in guild.")
        except HTTPException as e:
            logger.exception(f"HTTPException: {e}")
            return
        except Exception as e:
            logger.exception(f"Uncaught exception: {e}")
            return
async def setup(bot):
    await bot.add_cog(RoleGroup(bot))