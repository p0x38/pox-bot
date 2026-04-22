import asyncio
from datetime import datetime, timedelta
import math
import random
from typing import Optional
from discord.ext import commands
from discord import Activity, ActivityType, ClientStatus, Color, CustomActivity, Embed, Forbidden, Game, HTTPException, Interaction, Member, Role, Spotify, Status, Streaming, TextChannel, app_commands
from aiocache import cached

from bot import PoxBot

from logger import logger
from textwrap import shorten

from stuff import crop_word

def format_status(client_status: ClientStatus):
    result = ""
    if isinstance(client_status.status, Status):
        status = client_status.status

        if status.name in ("dnd", "do_not_disturb"):
            result = "Do not Disturb"
        elif status.name in ("invisible", "offline"):
            result = "Offline"
        elif status.name == "idle":
            result = "Idle"
        elif status.name == "online":
            result = "Online"
        else:
            result = "Unknown"
    elif isinstance(client_status.status, str):
        result = client_status.status
    elif client_status.raw_status.strip() is not None:
        result = client_status.raw_status
    
    platforms = []

    if client_status.mobile is str: platforms.append("Mobile")
    if client_status.desktop is str: platforms.append("Desktop")
    if client_status.web is str: platforms.append("Website")

    if platforms:
        result = result + f" ({", ".join(platforms)})"

    return result

def get_next_power_of_two(n: int) -> int:
    if n <= 0:
        return 1
    
    exponent = math.ceil(math.log2(n+1))

    return 2 ** exponent

class UserGroup(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="user", description="An group for Members.")
    
    @group.command(name="guild_duration", description="Checks how long user has been in the server.")
    @app_commands.guild_only()
    async def check_how_long_user_has_been(self, interaction: Interaction, member:Member):
        await interaction.response.defer()
        
        if not interaction.guild: return await interaction.followup.send("You must be run this command in guild mode")
        
        try:
            embed = Embed(title=f"How long {member.name} has been on server?")
            joined_date = member.joined_at
            if not joined_date: raise Exception("Welp")
            
            now = datetime.now(joined_date.tzinfo)
            
            duration = now - joined_date
            
            embed.description = f"{member.name} has been on the server for {duration} days"
            embed.color = Color.green()
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception(e)
            await interaction.followup.send("sry errored")
    
    @group.command(name="info", description="Get user's information.")
    @app_commands.guild_only()
    async def check_user_info(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        try:
            if interaction.guild:
                user = interaction.guild.get_member(member.id)
                if user:
                    roles = [role for role in user.roles if role.name != "@everyone"]
                    temp1 = {
                        'User ID': user.id,
                        'Name': f"`{user.display_name}`",
                        'Is Bot': "Yes" if user.bot else "No",
                        'Created on': user.created_at.strftime("%Y-%m-%d %H:%M:%S") + f" (<t:{int(user.created_at.timestamp())}:R>)",
                        'Highest role': f"<@&{user.top_role.id}>",
                        'Status': format_status(user.client_status),
                        'Nitro since': user.premium_since.strftime("%Y-%m-%d %H:%M:%S") if user.premium_since else "non-Nitro User",
                        'Joined at': user.joined_at.strftime("%Y-%m-%d %H:%M:%S") + f" (<t:{int(user.joined_at.timestamp())}:R>)" if user.joined_at else "Cannot find the date when this bro joined.",
                        'Roles': ", ".join([f"<@&{role.id}>" for role in roles]),
                    }

                    if user.activities:
                        index_activity = 0
                        for activity in user.activities:
                            index_activity += 1
                            if isinstance(activity, Activity):
                                info = ""
                                match (activity.type):
                                    case ActivityType.playing:
                                        info = f"Playing {activity.name}"
                                    case ActivityType.streaming:
                                        info = f"Streaming {activity.name}"
                                    case ActivityType.listening:
                                        info = f"Listening {activity.name}"
                                    case ActivityType.watching:
                                        info = f"Watching {activity.name}"
                                    case ActivityType.custom:
                                        info = activity.name
                                    case ActivityType.competing:
                                        info = f"Competing {activity.name}"
                                    case _:
                                        info = f"Unknown Type, {activity.name}"
                                
                                temp1[f'Activity #{index_activity}'] = f"{info} ({activity.state})"
                            elif isinstance(activity, Game):
                                temp1[f'Activity #{index_activity}'] = f"Playing {activity.name} on {activity.platform}"
                            elif isinstance(activity, Streaming):
                                temp1[f'Activity #{index_activity}'] = f"Streaming {activity.name} at {activity.platform}"
                            elif isinstance(activity, CustomActivity):
                                temp1[f'Activity #{index_activity}'] = activity.name
                            elif isinstance(activity, Spotify):
                                temp1[f'Activity #{index_activity}'] = f"Listening {activity.title} by {activity.artist} in {activity.album}"
                            else:
                                temp1[f'Activity #{index_activity}'] = "Unknown."
                    
                    e = Embed(title=f"Information for {user.display_name}")

                    lines = []

                    for key,value in temp1.items():
                        e.add_field(name=key, value=value, inline=True)

                    if user.display_avatar:
                        e.set_thumbnail(url=user.display_avatar.url)
                    else:
                        e.set_thumbnail(url=user.default_avatar.url)
                    
                    e.description = "\n".join(lines)

                    return await interaction.followup.send(embed=e)
                else:
                    return await interaction.followup.send("User not found.")
            else:
                return await interaction.followup.send("The command only works in guild due to issue with cache.")
        except Exception as e:
            return await interaction.followup.send(f"Error. {e}")
            logger.error(f"Error: {e}")
    
    @cached(60)
    @group.command(name="avatar", description="Display user's avatar in discord.")
    @app_commands.guild_only()
    async def get_user_avatar(self, interaction: Interaction, member: Member):
        await interaction.response.defer()

        embed = Embed(title=f"{member.display_name}'s Avatar")
        embed.set_image(url=member.display_avatar.url if member.display_avatar else member.default_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.name}, the result is cached for a minute.", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)

        return await interaction.followup.send(embed=embed)
    
    @group.command(name="kick", description="Kick a member.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="Member to kick.")
    @app_commands.describe(reason="Reason for member to give in DM.")
    @app_commands.guild_only()
    async def kick(self, interaction: Interaction, member: Member, reason: Optional[str] = None):
        await interaction.response.defer()
        e = Embed(title="Status")
        try:
            await member.kick(reason=(reason if reason is not None else "Reason not provided by issuer."))
            e.description = f"{member.name} has been kicked from the server."
            return await interaction.followup.send(embed=e)
        except Forbidden:
            e.description = f"You do not have permission to kick {member.name}."
            return await interaction.followup.send(embed=e)
        except HTTPException:
            e.description = f"The operation has failed."
            return await interaction.followup.send(embed=e)
        except Exception as ex:
            e.description = f"Uncaught exception. {ex}"
            return await interaction.followup.send(embed=e)

    @group.command(name="ban", description="Bans member from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="Member to ban")
    @app_commands.describe(reason="Reason to ban")
    @app_commands.guild_only()
    async def ban_member(self, ctx: Interaction, member: Member, *, reason: str = ""):
        try:
            await member.ban(reason=reason)
            await member.send(f"You're banned by {ctx.user.name}.\nReason: {reason if reason else 'No reason provided'}")
            return await ctx.response.send_message(f"Banned <@{member.id}>.", ephemeral=True)
        except Exception as e:
            return await ctx.response.send_message(f"Failed to ban. {e}", ephemeral=True)
    
    @group.command(name="unban", description="Unbans member")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="Member to unban")
    @app_commands.guild_only()
    async def unban_member(self, ctx: Interaction, member: Member):
        try:
            await member.unban()
            return await ctx.response.send_message(f"Unbanned {member.name}.", ephemeral=True)
        except Exception as e:
            return await ctx.response.send_message(f"Failed to unban. {e}", ephemeral=True)

    @group.command(name="warn", description="Warns member")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to warn")
    @app_commands.describe(reason="Reason to warn")
    @app_commands.guild_only()
    async def warn_member(self, ctx: Interaction, member: Member, *, reason: str = ""):
        try:
            await member.send(f"You're warned by {ctx.user.name}.\n\nReason: `{reason}`")
            return await ctx.response.send_message(f"Warned <@{member.id}>.", ephemeral=True)
        except Exception as e:
            return await ctx.response.send_message(f"Failed to warn. {e}")
            logger.error(f"Exception occured. {e}")
    
    @group.command(name="timeout", description="Warns member")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to time-out")
    @app_commands.describe(reason="Reason to time-out")
    @app_commands.describe(length="Length of time-out (minutes)")
    @app_commands.guild_only()
    async def timeout_member(self, ctx: Interaction, member: Member, reason: str = '', length: int = 1):
        await member.timeout(timedelta(minutes=length), reason=f"You're timed out. \"{reason if reason else "No reason provided from source"}\", Requested by {ctx.user.name}")
        return await ctx.response.send_message(f"Timed out {member.mention} for {length} minutes.")
    
    @group.command(name="un_timeout", description="Un-timeout member")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to remove timeout")
    @app_commands.guild_only()
    async def untimeout_member(self, ctx: Interaction, member: Member):
        await member.edit(timed_out_until=None)
        return await ctx.response.send_message(f"Took the timeout for {member.mention}.")

    @group.command(name="total_members", description="Returns total members")
    @app_commands.guild_only()
    async def get_list_members(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        embed = Embed(title="Members in this server",description="")
        
        if interaction.guild:
            embed.description = ', '.join([
                f"<@{m.id}>"
                for m in interaction.guild.members
            ])
        else:
            embed.description = "This command only works in guild."
            return await interaction.followup.send(embed=embed)

        return await interaction.followup.send(embed=embed)

    @group.command(name="set_nick", description="Sets user's nickname")
    @app_commands.guild_only()
    async def change_nickname(self, interaction: Interaction, member: Member, new_nick: Optional[str] = None):
        if new_nick is None:
            await member.edit(nick=None, reason=f"Nickname removed by {interaction.user.name}")
            return await interaction.response.send_message(f"Removed {member.name}'s Nickname.")
        else:
            await member.edit(nick=new_nick, reason=f"Nickname changed by {interaction.user.name} via /user nick")
            return await interaction.response.send_message(f"Changed {member.name}'s Nickname to **{new_nick}**.")
    
    @group.command(name="status", description="Checks member's status.")
    @app_commands.guild_only()
    async def get_user_status(self, interaction: Interaction, member: Member):
        await interaction.response.defer()
        result = ""
        
        if interaction.guild:
            member2 = interaction.guild.get_member(member.id)
            if member2:
                result = member2.status

        e = Embed(title=f"`{member.name}`'s status",description=f"<@{member.id}> is {result}!")

        return await interaction.followup.send(embed=e)
    
    @group.command(name="to_reachgoal", description="Returns remaining members to reach a goal value.")
    @app_commands.guild_only()
    async def get_remaining_members(self, interaction: Interaction, goal: Optional[int] = None):
        if interaction.guild is None: return await interaction.response.send_message("Object is not guild", ephemeral=True)

        member_count = len(interaction.guild.members)

        embed = Embed(title="Number of remaining members to reach the desired value")

        await interaction.response.defer()

        if goal is None:
            goal = get_next_power_of_two(member_count)
            #goal = (round(member_count/1000)*1000)+1000
        
        remaining = goal - member_count

        if remaining <= 0:
            embed.description = f"The server has already reached the goal of {goal} members!"
            embed.color = Color.green()
        else:
            embed.description = f"The server needs {remaining} more members to reach the goal of {goal} members."
            embed.color = Color.blurple()

        return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @group.command(name="find_first_message_contains", description="Finds the first message sent by specified user containing the keyword in the current channel.")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to search messages for.")
    @app_commands.describe(keyword="Keyword to search for in messages.")
    async def find_first_message_contains(self, interaction: Interaction, member: Member, keyword: str):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None:
            return await interaction.followup.send("This command can only be used in guild channels.")
        
        first_message = None

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None, oldest_first=True):
                if msg.author.id == member.id and keyword.lower() in msg.content.lower():
                    first_message = msg
                    break

                await asyncio.sleep(0.5)
                
        embed = Embed(title=f"First message by {member.display_name} containing '{keyword}'", description="")

        if first_message:
            embed.description = f"[{first_message.created_at.strftime('%Y-%m-%d %H:%M:%S')}](https://discord.com/channels/{first_message.guild.id}/{first_message.channel.id}/{first_message.id}): {first_message.content}"
            embed.color = Color.blue()
        else:
            embed.description = f"No messages found by {member.display_name} containing '**{keyword}**'."
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)
    
    @cached(120)
    @group.command(name="search_messages", description="Searches messages sent by specified user in the current channel.")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to search messages for.")
    @app_commands.describe(keyword="Keyword to search for in messages.")
    async def search_user_messages(self, interaction: Interaction, member: Member, keyword: str):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None:
            return await interaction.followup.send("This command can only be used in guild channels.")
        
        messages = []

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None):
                if len(messages) >= 15:
                    break

                if msg.author.id == member.id and keyword.lower() in msg.content.lower():
                    logger.debug(f"Found message: {msg.content} by {msg.author.name}")
                    messages.append(msg)
        
        embed = Embed(title=f"Messages by {member.display_name} containing '{keyword}'", description="")

        if messages:
            lines = []
            for msg in messages:
                lines.append(f"- [{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}](https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}): {crop_word(msg.content, keyword) or shorten(msg.content, width=30)}")
            
            embed.description = "\n".join(lines)
            embed.color = Color.blue()
        else:
            embed.description = f"No messages found by {member.display_name} containing '**{keyword}**'."
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)
    
    @cached(120*2)
    @group.command(name="first_message", description="Gets the first message sent by specified user in the current channel.")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to get first message for.")
    async def get_first_user_message(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None or interaction.guild is None:
            return await interaction.followup.send("This command can only be used in guild channels.")
        
        first_message = None

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None, oldest_first=True):
                if msg.author.id == member.id:
                    first_message = msg
                    break
        
        embed = Embed(title=f"First message by {member.display_name}", description="")

        if first_message:
            embed.description = f"[{first_message.created_at.strftime('%Y-%m-%d %H:%M:%S')}](https://discord.com/channels/{first_message.guild.id}/{first_message.channel.id}/{first_message.id}): {first_message.content}"
            embed.color = Color.blue()
        else:
            embed.description = f"No messages found by {member.display_name} in this channel."
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @group.command(name="latest_message", description="Gets the latest message sent by specified user in the current channel.")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to get latest message for.")
    async def get_latest_user_message(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None or interaction.guild is None:
            return await interaction.followup.send("This command can only be used in guild channels.")
        
        latest_message = None

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=1):
                if msg.author.id == member.id:
                    latest_message = msg
                    break
        
        embed = Embed(title=f"Latest message by {member.display_name}", description="")

        if latest_message:
            embed.description = f"[{latest_message.created_at.strftime('%Y-%m-%d %H:%M:%S')}](https://discord.com/channels/{latest_message.guild.id}/{latest_message.channel.id}/{latest_message.id}): {latest_message.content}"
            embed.color = Color.blue()
        else:
            embed.description = f"No messages found by {member.display_name} in this channel."
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @group.command(name="random_message", description="Gets a random message sent by specified user in the current channel.")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to get random message for.")
    async def get_random_user_message(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        if interaction.channel is None:
            return await interaction.followup.send("This command can only be used in guild channels.")
        
        user_messages = []

        if isinstance(interaction.channel, TextChannel):
            async for msg in interaction.channel.history(limit=None):
                if msg.author.id == member.id:
                    user_messages.append(msg)
        
        embed = Embed(title=f"Random message by {member.display_name}", description="")

        if user_messages:
            random_message = random.choice(user_messages)
            embed.description = f"[{random_message.created_at.strftime('%Y-%m-%d %H:%M:%S')}](https://discord.com/channels/{random_message.guild.id}/{random_message.channel.id}/{random_message.id}): {random_message.content}"
            embed.color = Color.blue()
        else:
            embed.description = f"No messages found by {member.display_name} in this channel."
            embed.color = Color.red()

        return await interaction.followup.send(embed=embed)
    
    @group.command(name="is_pepo", description="check if this dude is pepo")
    @app_commands.guild_only()
    async def is_pepo(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        e = Embed(title="Pepo Detector")

        if member.id == 1100132559851098163:
            e.description = f"Yes, <@{member.id}> is pepo."
        else:
            e.description = f"No, <@{member.id}> is not pepo."
        
        return await interaction.followup.send(embed=e)
    
    @cached(120*4)
    @group.command(name="hash_value", description="Get user's hash code.")
    @app_commands.guild_only()
    async def get_user_hash(self, interaction: Interaction, member: Member):
        await interaction.response.defer(thinking=True)
        e = Embed(title="User Hash Code", description=f"`{hash(member)}`")
        return await interaction.followup.send(embed=e)

async def setup(bot):
    await bot.add_cog(UserGroup(bot))