import asyncio
from datetime import datetime, timedelta
import math
import random
import re
from typing import Optional, Union
from discord.ext import commands
from discord import Activity, ActivityType, ClientStatus, Color, CustomActivity, Embed, Forbidden, Game, HTTPException, Interaction, Locale, Member, Role, Spotify, Status, Streaming, TextChannel, TextStyle, User, app_commands, ui
from aiocache import cached

from bot import PoxBot

from logger import logger
from textwrap import shorten

from src.translator import translator_instance as i18n

from stuff import crop_word

def format_status(client_status: ClientStatus, locale: Union[Locale, str]):
    result = ""
    if isinstance(client_status.status, Status):
        status = client_status.status

        if status == Status.do_not_disturb:
            result = i18n.T("text.status.dnd", locale)
        else:
            result = i18n.T(f"text.status.{status.name}", locale)
    elif isinstance(client_status.status, str):
        result = client_status.status
    elif client_status.raw_status.strip() is not None:
        result = client_status.raw_status
    
    platforms = []

    if client_status.mobile is str: platforms.append(i18n.T("text.device.mobile", locale))
    if client_status.desktop is str: platforms.append(i18n.T("text.device.desktop", locale))
    if client_status.web is str: platforms.append(i18n.T("text.device.website", locale))

    if platforms:
        result = result + f" ({', '.join(platforms)})"

    return result

def get_next_power_of_two(n: int) -> int:
    if n <= 0:
        return 1
    
    exponent = math.ceil(math.log2(n+1))

    return 2 ** exponent

DURATION_REGEX = re.compile(
    r"(?:(?P<weeks>\d+)\s*w)?\s*"
    r"(?:(?P<days>\d+)\s*d)?\s*"
    r"(?:(?P<hours>\d+)\s*h)?\s*"
    r"(?:(?P<minutes>\d+)\s*m)?\s*"
    r"(?:(?P<seconds>\d+)\s*s)?",
    re.IGNORECASE
)

MAX_TIMEOUT = timedelta(days=28)

def parse_duration(text: str) -> timedelta:
    text = text.strip().lower()
    
    if text.isdigit():
        return timedelta(seconds=int(text))
    
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            m, s = parts
            return timedelta(minutes=int(m), seconds=int(s))
        elif len(parts) == 3:
            h, m, s = parts
            return timedelta(hours=int(h), minutes=int(m), seconds=int(s))
        elif len(parts) == 4:
            d, h, m, s = parts
            return timedelta(days=int(d), hours=int(h), minutes=int(m), seconds=int(s))
        else:
            raise ValueError("Invalid time format!!! 3:<")
    
    match = DURATION_REGEX.fullmatch(text)
    if match:
        parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
        return timedelta(**parts)
    
    raise ValueError("Couldn't parse duration.. 3:")

SUFFIX = "Action taken by {} via ContextMenu"

class TimeoutModal(ui.Modal, title="User timeout"):
    def __init__(self, target: Member):
        super().__init__()
        self.target = target
        self.reason_suffix = SUFFIX.format(target.display_name)
        self.embed = Embed(color=Color.red())
    
    duration = ui.TextInput(
        label="Duration",
        placeholder="e.g. 1d 2h (1 day 2 hours), 02:00 (2 minutes), 3600 (1 hour)",
        required=True
    )
    
    reason = ui.TextInput(
        label="Reason",
        style=TextStyle.paragraph,
        required=False,
        max_length=250
    )
    
    async def on_submit(self, interaction: Interaction):
        loc = str(interaction.locale)
        try:
            td = parse_duration(self.duration.value)
            
            if td.total_seconds() <= 0:
                raise ValueError(i18n.T("error.custom.timeout_duration_lessflow", loc))
            
            if td > MAX_TIMEOUT:
                td = MAX_TIMEOUT
            
            if not interaction.guild:
                raise Exception(i18n.T("error.custom.guild_only", loc))
            
            if isinstance(interaction.user, User):
                raise Exception()
            
            if self.target == interaction.user:
                raise Exception(i18n.T("error.custom.tried_to_timeout_himself", loc))
            
            if self.target == interaction.guild.owner:
                raise Exception(i18n.T("error.custom.tried_to_timeout_owner", loc))
            
            if self.target.top_role >= interaction.user.top_role:
                raise Exception(i18n.T("error.custom.tried_to_timeout_higher", loc))
            
            if not interaction.guild.me.guild_permissions.moderate_members:
                raise Exception(i18n.T("error.custom.forbidden_timeout", loc))
            
            if self.target.top_role >= interaction.guild.me.top_role:
                raise Exception(i18n.T("error.custom.cannot_timeout_higher", loc))
            
            try:
                timeout_reason = self.reason.value or "No reason specified from executor"
                await self.target.timeout(td, reason=timeout_reason + self.reason_suffix)
            except Exception as e:
                self.embed.description = f"Exception thrown!\n{e}"
                logger.exception(e)
                await interaction.response.send_message(embed=self.embed)
                return
            
            self.embed.description = i18n.T("messages.timed_out_user", loc, {"user": self.target.mention, "length": td})
            
            await interaction.response.send_message(embed=self.embed)
        except Exception as e:
            self.embed.description = f"Exception thrown!\n{e}"
            logger.exception(e)
            await interaction.response.send_message(embed=self.embed)
            

class UserGroup(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        
        @app_commands.context_menu(name=app_commands.locale_str("Kick", message="context_menu.kick_member.name"))
        @app_commands.checks.has_permissions(kick_members=True)
        @app_commands.guild_only()
        async def contextmenu_kick(interaction: Interaction, member: Member):
            loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
            embed = Embed(color=Color.red())

            await interaction.response.defer()

            try:
                await member.kick(reason=f"{interaction.user.display_name} kicked user via Context menu")
                embed.description = i18n.T("messages.kick_user", loc, {"user": member.display_name})
            except Forbidden:
                embed.description = i18n.T("error.custom.insufficient_permission_kick", loc, {"user": member.display_name})
            except HTTPException:
                embed.description = i18n.T("error.exceptions.HTTPException", loc)
            except Exception as e:
                embed.description = i18n.T("error.exceptions.Unknown", loc, {"e": e})
            finally:
                return await interaction.followup.send(embed=embed)
        
        @app_commands.context_menu(name=app_commands.locale_str("Ban", message="context_menu.ban_membee.name"))
        @app_commands.checks.has_permissions(ban_members=True)
        @app_commands.guild_only()
        async def contextmenu_ban(interaction: Interaction, member: Member):
            loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
            embed = Embed(color=Color.red())
            
            await interaction.response.defer()
            
            try:
                await member.ban(reason=f"{interaction.user.display_name} banned user via Context menu")
                embed.description = i18n.T("messages.ban_user", loc, {"user": member.display_name})
            except Forbidden:
                embed.description = i18n.T("error.custom.insufficient_permission_ban", loc, {"user": member.display_name})
            except HTTPException:
                embed.description = i18n.T("error.exceptions.HTTPException", loc)
            except Exception as e:
                embed.description = i18n.T("error.exceptions.Unknown", loc, {"e": e})
            finally:
                return await interaction.followup.send(embed=embed)
        
        @app_commands.context_menu(name=app_commands.locale_str("Timeout", message="context_menu.timeout_member.name"))
        @app_commands.checks.has_permissions(moderate_members=True)
        @app_commands.guild_only()
        async def contextmenu_timeout(interaction: Interaction, member: Member):
            await interaction.response.send_modal(TimeoutModal(member))
        
        bot.tree.add_command(contextmenu_kick)
        bot.tree.add_command(contextmenu_ban)
        bot.tree.add_command(contextmenu_timeout)
    
    group = app_commands.Group(name=app_commands.locale_str("user", message="command.user.name"), description=app_commands.locale_str("A group for user.", message="command.user.description"))
    
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
    
    @group.command(name=app_commands.locale_str("info", message="command.user.info.name"), description=app_commands.locale_str("Retrieves user's information.", message="command.user.info.description"))
    @app_commands.guild_only()
    async def check_user_info(self, interaction: Interaction, member: Member):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        await interaction.response.defer(thinking=True)
        try:
            if interaction.guild:
                user = interaction.guild.get_member(member.id)
                if user:
                    roles = [role for role in user.roles if role.name != "@everyone"]
                    temp1 = {
                        'user_id': user.id,
                        'user_name': f"`{user.display_name}`",
                        'user_bot': i18n.T("text.boolean.true" if user.bot else "text.boolean.false", loc),
                        'user_creation': user.created_at.strftime("%Y-%m-%d %H:%M:%S") + f" (<t:{int(user.created_at.timestamp())}:R>)",
                        'user_highest_role': f"<@&{user.top_role.id}>",
                        'user_status': format_status(user.client_status, loc),
                        'user_nitro': user.premium_since.strftime("%Y-%m-%d %H:%M:%S") if user.premium_since else i18n.T("label.non_nitro", loc),
                        'user_join': user.joined_at.strftime("%Y-%m-%d %H:%M:%S") + f" (<t:{int(user.joined_at.timestamp())}:R>)" if user.joined_at else i18n.T("text.unknown_join", loc),
                        'user_roles': ", ".join([f"<@&{role.id}>" for role in roles]),
                    }
                    
                    temp1 = i18n.translate_map(temp1, loc)

                    if user.activities:
                        index_activity = 0
                        for activity in user.activities:
                            index_activity += 1
                            if isinstance(activity, Activity):
                                info = ""
                                match (activity.type):
                                    case ActivityType.custom:
                                        info = activity.name
                                    case _:
                                        info = i18n.T(f"text.activity_type.{activity.type.name}", loc, {"activity": activity.name})
                                
                                temp1[f'Activity #{index_activity}'] = f"{info} ({activity.state})"
                            elif isinstance(activity, Game):
                                temp1[f'Activity #{index_activity}'] = i18n.T("text.activity_type.game", loc, {"activity": activity.name, "platform": activity.platform})
                            elif isinstance(activity, Streaming):
                                temp1[f'Activity #{index_activity}'] = i18n.T("text.activity_type.stream", loc, {"activity": activity.name, "platform": activity.platform})
                            elif isinstance(activity, CustomActivity):
                                temp1[f'Activity #{index_activity}'] = activity.name
                            elif isinstance(activity, Spotify):
                                temp1[f'Activity #{index_activity}'] = i18n.T("text.activity_type.spotify", loc, {"title": activity.title, "artist": activity.artist, "album": activity.album})
                            else:
                                temp1[f'Activity #{index_activity}'] = i18n.T("text.unknown", loc)
                    
                    if self.bot.stats_db and self.bot.stats_db.pool:
                        async with self.bot.stats_db.pool.acquire() as conn:
                            row = await conn.fetchrow(
                                "SELECT message_count FROM user_stats WHERE user_id = $1",
                                interaction.user.id
                            )
                        
                        count = row['message_count'] if row else 0
                        temp1['user_message_count'] = i18n.T("label.user_message_count_value", loc, {"messages": count})
                    
                    e = Embed(title=i18n.T("command.user.info.embeds.default.title", loc, {"user": user.display_name}))

                    for key,value in temp1.items():
                        e.add_field(name=key, value=value, inline=True)

                    if user.display_avatar:
                        e.set_thumbnail(url=user.display_avatar.url)
                    else:
                        e.set_thumbnail(url=user.default_avatar.url)

                    return await interaction.followup.send(embed=e)
                else:
                    return await interaction.followup.send(i18n.T("error.custom.user_not_found", loc))
            else:
                return await interaction.followup.send(i18n.T("error.custom.invalidated_cache", loc))
        except Exception as e:
            logger.error(f"Error: {e}")
            return await interaction.followup.send(f"Error. {e}")
    
    @cached(60)
    @group.command(name="avatar", description=app_commands.locale_str("Shows Discord user's avatar.", message="command.user.avatar.description"))
    @app_commands.guild_only()
    async def get_user_avatar(self, interaction: Interaction, member: Member):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()

        embed = Embed(title=i18n.T("command.user.avatar.embeds.default.title", loc, {"user": member.name}))
        embed.set_image(url=member.display_avatar.url if member.display_avatar else member.default_avatar.url)
        embed.set_footer(text=i18n.T("command.user.avatar.embeds.default.footer", loc, {"author": interaction.user.display_name}), icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)

        return await interaction.followup.send(embed=embed)
    
    @group.command(name="kick", description="Kick a member.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="Member to kick.")
    @app_commands.describe(reason="Reason for member to give in DM.")
    @app_commands.guild_only()
    async def kick(self, interaction: Interaction, member: Member, reason: Optional[str] = None):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        embed = Embed()
        try:
            await member.kick(reason=(reason if reason is not None else "Reason not provided by issuer."))
            embed.description = i18n.T("messages.kick_user", loc, {"user": member.display_name})
        except Forbidden:
            embed.description = i18n.T("error.custom.insufficient_permission_kick", loc, {"user": member.display_name})
        except HTTPException:
            embed.description = i18n.T("error.exceptions.HTTPException", loc)
        except Exception as e:
            embed.description = i18n.T("error.exceptions.Unknown", loc, {"e": e})
        finally:
            return await interaction.followup.send(embed=embed)

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
    
    @group.command(name="remove_timeout", description="Un-timeout member")
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

    @group.command(name="set_nick", description=app_commands.locale_str("Sets user's nickname.", message="command.user.set_nick.description"))
    @app_commands.guild_only()
    async def change_nickname(self, interaction: Interaction, member: Member, new_nick: Optional[str] = None):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        
        embed = Embed()

        if new_nick is None:
            await member.edit(nick=None, reason=i18n.T("command.user.set_nick.reasons.reset", loc, {"user": member.mention, "author": interaction.user.name}))
            embed.description = i18n.T("command.user.set_nick.embeds.reset.description", loc, {"user": member.mention})
            return await interaction.followup.send(embed=embed)
        else:
            await member.edit(nick=None, reason=i18n.T("command.user.set_nick.reasons.changed", loc, {"user": member.mention, "author": interaction.user.name}))
            embed.description = i18n.T("command.user.set_nick.embeds.changed.description", loc, {"user": member.mention, "new_nickname": new_nick})
            return await interaction.followup.send(embed=embed)
    
    @group.command(name="status", description=app_commands.locale_str("Retrieves user's status.", message="command.user.status.description"))
    @app_commands.guild_only()
    async def get_user_status(self, interaction: Interaction, member: Member):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer()
        result = i18n.T("text.unknown", loc)
        
        if interaction.guild:
            member2 = interaction.guild.get_member(member.id)
            if member2:
                result = member2.client_status

        e = Embed()
        e.title = i18n.T("command.user.status.embeds.default.title", loc, {"user": member.display_name})
        e.description = format_status(result, loc) if isinstance(result, ClientStatus) else result
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