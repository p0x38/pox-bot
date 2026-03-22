
import time
import discord
from discord.ext import commands, tasks
from discord import Color, Interaction, Role, TextChannel, app_commands

import lmstudio as lms

from bot import PoxBot
from logger import logger

class ReactionRolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot

    group = app_commands.Group(name="reaction_roles", description="Manage reaction roles")

    async def get_target_message(self, interaction):
        if not self.bot.user: return None
        async for msg in interaction.channel.history(limit=100):
            if msg.author.id == self.bot.user.id:
                return msg
        return None
    
    async def update_message_content(self, message, emoji, role, action):
        if not message.embeds: return

        embed = message.embeds[0]
        line = f"\n{emoji} : {role.mention}"
        line = f"{emoji} : {role.mention}"

        if action == "add":
            if line not in (embed.description or ""):
                embed.description = (embed.description or "") + line
        elif action == "remove":
            if embed.description:
                embed.description = embed.description.replace(line, "")
        
        await message.edit(embed=embed)
    
    @group.command(name="create_menu", description="Create a reaction role menu. Use this on the channel you want to.")
    async def create_menu(self, interaction: Interaction, title: str):
        embed = discord.Embed(title=title, color=Color.blurple())
        if not isinstance(interaction.channel, TextChannel): return await interaction.response.send_message("This command can only be used in text channels.", ephemeral=True)
        await interaction.response.send_message("Menu created... Now use '/add_reaction' on it.", ephemeral=True)
        await interaction.channel.send(embed=embed)
    
    @group.command(name="add_reaction", description="Link an emoji to a role")
    async def add_reaction(self, interaction: Interaction, emoji: str, role: Role):
        await interaction.response.defer(ephemeral=True)

        msg = await self.get_target_message(interaction)
        if not msg: return await interaction.followup.send("No valid message found to add reaction roles to.", ephemeral=True)

        try:
            await msg.add_reaction(emoji)
        except Exception as e:
            return await interaction.followup.send(f"Failed to add reaction: {e}", ephemeral=True)
        
        if self.bot.mysql is None: return await interaction.followup.send("Database connection not available.", ephemeral=True) 
        async with self.bot.mysql.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO reaction_roles (message_id, emoji, role_id) 
                    VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE role_id=%s
                """, (msg.id, emoji, role.id, role.id))
        
        await self.update_message_content(msg, emoji, role, "add")
        return await interaction.followup.send(f"Reaction role added: {emoji} -> {role.mention}", ephemeral=True)

    @app_commands.command(name="delete_reaction", description="Remove a role from the latest menu! (;_;)")
    async def delete_reaction(self, interaction: discord.Interaction, emoji: str):
        await interaction.response.defer(ephemeral=True)
        
        msg = await self.get_target_message(interaction)
        if not msg:
             return await interaction.followup.send("No menu found! >_<")

        if self.bot.mysql is None: return await interaction.followup.send("Database connection not available.", ephemeral=True)
        async with self.bot.mysql.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM reaction_roles WHERE message_id=%s AND emoji=%s", (msg.id, emoji))
        
        try:
            await msg.remove_reaction(emoji, self.bot.user)
        except: pass

        await interaction.followup.send(f"Removed {emoji} from the menu! o/")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not self.bot.user: return
        if payload.user_id == self.bot.user.id: return

        if self.bot.mysql:
            async with self.bot.mysql.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT role_id FROM reaction_roles WHERE message_id=%s AND emoji=%s", (payload.message_id, str(payload.emoji)))
                    res = await cur.fetchone()
            if res and (guild := self.bot.get_guild(payload.guild_id)):
                if member := guild.get_member(payload.user_id):
                    if role := guild.get_role(res[0]): await member.add_roles(role)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if not self.bot.user: return
        if payload.user_id == self.bot.user.id: return

        if self.bot.mysql:
            async with self.bot.mysql.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT role_id FROM reaction_roles WHERE message_id=%s AND emoji=%s", (payload.message_id, str(payload.emoji)))
                    res = await cur.fetchone()

            if res and (guild := self.bot.get_guild(payload.guild_id)):
                 if member := guild.get_member(payload.user_id):
                    if role := guild.get_role(res[0]): await member.remove_roles(role)
    
async def setup(bot):
    await bot.add_cog(ReactionRolesCog(bot))