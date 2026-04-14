import asyncio
import platform
import time
from discord import ButtonStyle, Color, Embed, Interaction, SelectOption, TextStyle, app_commands
import discord
from discord import ui
from discord.ext import commands
from discord.ui import Select
import distro
from datetime import datetime, timezone
import psutil
import pytz

from bot import PoxBot
from cogs.chatbot import ChatbotCog
from logger import logger
from stuff import get_formatted_from_seconds
import stuff

class FeedbackModal(ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Feedback", timeout=None, custom_id="feedback-modal")
        self.feedback = ui.TextInput(
            label="Give me feedback to the bot.",
            style=TextStyle.long,
            placeholder="Type your feedback, like suggestions, reviews, etc...",
            required=True,
            min_length=25,
            max_length=900,
            custom_id="feedback-text",
        )
        self.add_item(self.feedback)
        
        self.bot: PoxBot = bot
    
    async def send_feedback(self, interaction: Interaction):
        try:
            owner_id = self.bot.owner_id
            if not owner_id: return
            
            owner = self.bot.get_user(owner_id)
            if not owner: raise Exception("Why's owner not found")
            
            embed = Embed(title=f"Bot feedback received from {interaction.user.name}", color=Color.blurple())
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Sent on {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}")
            
            embed.description = self.feedback.value
            
            await owner.send(embed=embed)
        except Exception as e:
            logger.exception(f"Exception thrown: {e}")
    
    async def on_submit(self, interaction: Interaction):
        await self.send_feedback(interaction)
        await interaction.response.send_message(f"Thanks for your feedback!", ephemeral=True, delete_after=10)
    
    async def on_error(self, interaction: Interaction, error: Exception):
        await interaction.response.send_message("Oops! something went wrong.", ephemeral=True, delete_after=10)
        
        logger.exception(f"Error raised: {error}")

class DynamicInfoView(discord.ui.View):
    def __init__(self, cog, bot):
        super().__init__(timeout=120)
        self.cog = cog
        self.bot: PoxBot = bot
        
        url_button = discord.ui.Button(label='Visit source code', style=ButtonStyle.link, url="https://github.com/noteswiper/pox-bot")
        self.add_item(url_button)
    
    async def get_stats_data(self, interaction: Interaction):
        cpu_usage = await asyncio.to_thread(psutil.cpu_percent, interval=0.1)
        mem = await asyncio.to_thread(psutil.virtual_memory)
        disk = await asyncio.to_thread(psutil.disk_usage, '/')
        
        uptime = "Unknown"
        if self.bot.launch_time2:
            uptime = stuff.get_formatted_from_seconds(round(time.time() - self.bot.launch_time2))
        
        platform_info = platform.platform(aliased=True)
        if platform.system() == "Linux":
            try:
                os_rel = platform.freedesktop_os_release()
                if os_rel and os_rel.get("ID") == "ubuntu":
                    platform_info = f"{distro.name()} {distro.version()}"
            except: pass
        elif platform.system() == "Windows":
            platform_info = "Windows" + " ".join(list(platform.win32_ver()))
        
        chatbot_cog = self.bot.get_cog("ChatbotCog")
        channel_id = interaction.channel_id
        
        chan_info = chatbot_cog.channel_data.get(channel_id, {"muted_until": 0}) if chatbot_cog else {}
        is_muted = "Yes" if time.time() < chan_info.get("muted_until", 0) else "No"
        
        return {
            "identity": {
                "title": "Identity & Version",
                "fields": {
                    "uuid": {
                        "display": "Session UUID",
                        "value": f"{self.bot.session_uuid}"
                    },
                    "version": {"display": "Bot Version", "value": f"git+{self.bot.commit_hash or 'No commit hash found'} {self.bot.last_commit or 'No commit message found'}"},
                    "signature": {"display": "Signature", "value": self.bot.name_signature or "Unknown signature"},
                    "uptime": {
                        "display": "Bot uptime",
                        "value": f"{uptime}",
                    },
                    "latency": {
                        "display": "Network latency",
                        "value": f"{self.bot.latency * 1000:.2f}ms"
                    },
                    "owner": {
                        "display": "Bot developer",
                        "value": "\\_\\_\\_\\_\\_"
                    }
                }
            },
            "stats": {
                "title": "Bot Statistics",
                "fields": {
                    "guilds": {
                        "display": "Servers",
                        "value": f"{len(self.bot.guilds):,}",
                    },
                    "users": {
                        "display": "Users",
                        "value": f"{len(self.bot.users):,}",
                    },
                    "msgs": {
                        "display": "Messages seen",
                        "value": f"{self.bot.handled_messages:,}",
                    },
                    "channels": {
                        "display": "Channels",
                        "value": f"{len(list(self.bot.get_all_channels())):,}",
                    },
                    "interactions": {"display": "Interactions", "value": f"P: {self.bot.processed_interactions} | F: {self.bot.failed_interactions}"},
                    "cached_values": {
                        "display": "Caches",
                        "value": f"{self.bot.cache.get_count():,}"
                    }
                }
            },
            "hardware": {
                "title": "Technical details",
                "fields": {
                    "platform": {"display": "Platform", "value": platform_info},
                    "cpu": {
                        "display": "CPU usage",
                        "value": self.cog.make_bar(cpu_usage),
                    },
                    "ram": {
                        "display": "Memory Usage",
                        "value": self.cog.make_bar(mem.percent),
                    },
                    "disk": {"display": "Disk Usage", "value": self.cog.make_bar(disk.percent)},
                    "ram_details": {"display": "Memory Details", "value": f"{mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB"}
                }
            },
            "context": {
                "title": "Local brain data",
                "fields": {
                    "muted": {"display": "Is Jim muted?", "value": is_muted},
                    "memory": {"display": "Context Usage", "value": f"{len(chatbot_cog.history.get(channel_id, []))}/10 messages"},
                    "mode": {"display": "Current Mood", "value": "idk"},
                }
            }
        }
    
    @discord.ui.select(
        placeholder="Choose a category...",
        options=[
            SelectOption(label="Identity", value="identity", emoji="🛠️"),
            SelectOption(label="Statistics", value="stats", emoji="📈"),
            SelectOption(label="Technical details", value="hardware", emoji="🔧"),
            SelectOption(label="AI Context details", value="context", emoji="🗣️")
        ]
    )
    async def select_callback(self, interaction: Interaction, select: Select):
        choice = select.values[0]
        
        full_data = await self.get_stats_data(interaction)
        category = full_data.get(select.values[0], {})
        
        e = Embed(title=f"Bot information - {category.get('title', "Unknown")}")
        
        for field_id, info in category.get('fields', {}).items():
            is_inline = info.get('inline', True)
            e.add_field(name=info.get('display', '???'), value=info.get('value', '???'), inline=is_inline)
        
        await interaction.response.edit_message(embed=e, view=self)
    
class Info(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="info", description="Informations.")
    
    def make_bar(self, percent, length=10):
        filled_length = int(length*percent/100)
        bar = '#' * filled_length + '_' * (length - filled_length)
        return f"[`{bar}`] {percent}%"
    
    @group.command(name="sync", description="syncs command if panic mode")
    @app_commands.check(stuff.is_bot_owner)
    @commands.guild_only()
    async def sync_commands(self,ctx: Interaction):
        if ctx.guild:
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.response.send_message("Commands have been synced.")
        else:
            await ctx.response.send_message("This command can only be used in a server.")
    
    @group.command(name="botserver", description="Join to bot's main server")
    async def send_botserver_invite_link(self, interaction: Interaction):
        await interaction.response.send_message(f"Here's the server:\nhttps://discord.gg/3FVGf5MBJV", ephemeral=True)
    
    @group.command(name="uptime", description="How long this bot is in session")
    async def check_uptime(self,ctx: Interaction):
        global start_time
        await ctx.response.send_message("I have been online for {}.".format(stuff.get_formatted_from_seconds(round(time.time() - self.bot.launch_time2))))
    
    @group.command(name="retrieve", description="I always with you :)")
    async def show_stats(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        
        view = DynamicInfoView(self, self.bot)
        e = Embed(title="Bot Information", description="Select a category below to view specific details.")
        e.set_footer(text="System: " + platform.system())
        
        await interaction.followup.send(embed=e, view=view)
    
    async def script_info(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        
        e = Embed(title="Bot Information")
        
        cpu_usage = await asyncio.to_thread(psutil.cpu_percent, interval=0.1)
        mem = await asyncio.to_thread(psutil.virtual_memory)
        disk = await asyncio.to_thread(psutil.disk_usage, '/')
        
        commit_hash = self.bot.commit_hash or "Unknown hash"
        last_commit_message = self.bot.last_commit or "No description"
        namesignature = self.bot.name_signature or "Unknown"
        
        rows_to_add = {
            'Session UUID': str(self.bot.session_uuid),
            'Version': f"Python {platform.python_version()}, discord.py {discord.__version__}",
            'Bot Version': f"git+{commit_hash} {last_commit_message}; {namesignature}" if commit_hash else "Unknown",
            'Platform': "Unknown",
            'Latency (ms)': f"{round(self.bot.latency * 1000)} ms",
            'Shard': f"{self.bot.shard_id} / {len(self.bot.shards):,}" if self.bot.shard_id is not None else "Standalone",
            'Bot Developer': "\\_\\_\\_\\_\\_",
            'Servers that am in': f"{len(self.bot.guilds):,} servers",
            'Messages I seen': f"{self.bot.handled_messages:,} messages",
            'Interactions I processed': f"processed {self.bot.processed_interactions:,}, failed {self.bot.failed_interactions:,}",
            'Users I see': f"{len(self.bot.users):,} users",
            'Channels I can read': f"{len(list(self.bot.get_all_channels())):,} channels",
            'Messages I can validate': f"{len(self.bot.cached_messages):,} messages",
            'Data I can retrieve': f"{self.bot.cache.get_count():,} values",
            'CPU Usage': self.make_bar(cpu_usage),
            'Memory Usage': self.make_bar(mem.percent),
            'Disk Usage': self.make_bar(disk.percent),
            'Memory Details': f"{mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB"
        }
        
        if platform.system() == "Linux":
            try:
                os_rel = platform.freedesktop_os_release()
                if os_rel and os_rel.get("ID") == "ubuntu":
                    rows_to_add['Platform'] = f"{distro.name()} {distro.version()}"
                else:
                    rows_to_add['Platform'] = platform.platform(aliased=True)
            except Exception:
                rows_to_add['Platform'] = platform.platform(aliased=True)
        elif platform.system() == "Windows":
            rows_to_add['Platform'] = "Windows " + " ".join(list(platform.win32_ver()))
        else:
            rows_to_add['Platform'] = platform.platform(aliased=True)
        
        if self.bot.launch_time2:
            rows_to_add['Launch time'] = get_formatted_from_seconds(round(time.time() - self.bot.launch_time2))
        
        for k,v in rows_to_add.items():
            e.add_field(name=k,value=v)

        await interaction.followup.send(embed=e)
    
    @group.command(name="commit_data", description="Shows bot's latest git commit.")
    async def get_commit_data(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        
        commit_hash = self.bot.commit_hash or "Unknown hash"
        last_commit_message = self.bot.last_commit or "No description"
        temp1 = {
            'Commit Hash': commit_hash,
            'Commit Message': last_commit_message,
        }
        
        e = discord.Embed(title="Current git information", url="https://github.com/NoteSwiper/pox-bot")
        
        for item, value in temp1.items():
            e.add_field(name=item,value=value)
        
        e.set_footer(text="The bot is open-source. Click to this embed to access the site which is published.")
        
        await interaction.followup.send(embed=e)
    
    @group.command(name="ping", description="Pong!")
    async def ping(self, interaction: Interaction):
        await interaction.response.defer()
        e = Embed(title="Pong!")
        rows_to_add = {
            'Latency (ms)': round(self.bot.latency * 10000) / 100,
            'Shard ID': self.bot.shard_id or "Standalone",
            'Shards': self.bot.shard_count or "Standalone"
		}
        
        for k,v in rows_to_add.items():
            e.add_field(name=k,value=v,inline=True)
        
        await interaction.followup.send(embed=e)

    @group.command(name="pox",description="Say him 'p0x38 is retroslop >:3'")
    async def pox_message(self, ctx: discord.Interaction):
        await ctx.response.defer()
        await ctx.followup.send("p0x38 is retroslop.")

    @group.command(name="bot_timestamp", description="Shows time in bot's time")
    async def get_bot_timestamp(self, ctx: discord.Interaction):
        await ctx.response.defer()
        timec = datetime.now(pytz.timezone("Asia/Tokyo"))
        
        await ctx.followup.send(f"I'm on {datetime.strftime(timec, '%Y-%m-%d %H:%M:%S%z')} :3")
    
    async def get_timezone_timestamp_autocomplete(self, interaction: discord.Interaction, current: str):
        timezones = pytz.all_timezones
        return [
            app_commands.Choice(name=tz, value=tz)
            for tz in timezones if current.lower() in tz.lower()
        ][:25]
    
    @group.command(name="timedate", description="Shows time in specified timezone")
    @app_commands.autocomplete(timezone=get_timezone_timestamp_autocomplete)
    async def get_timezone_timestamp(self, ctx: discord.Interaction, timezone: str):
        await ctx.response.defer(ephemeral=True)
        try:
            tz = pytz.timezone(timezone)
            timec = datetime.now(tz)
            await ctx.followup.send(f"In timezone {timezone}, it's **{datetime.strftime(timec, '%Y.%m.%d, %H:%M:%S with the UTC offset %z')}**.", ephemeral=True)
        except Exception as e:
            await ctx.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @group.command(name="invite", description="Invites the bot to server by application url. (LIMITED TO 90 SERVERS)")
    async def invite(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            
            guild_count = len(self.bot.guilds)
            limit = self.bot.bot_servers_limit
            
            status_msg = f"Capacity: **{guild_count}/{limit}** servers"
            
            scopes = "bot%20applications.commands"
            perms = 1395868252224
            
            if not self.bot.user: return
            client_id = self.bot.user.id
            invite_url = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions={perms}&scope={scopes}"
            
            embed = Embed(
                title="Invite Jim",
                description=f"{status_msg}\n\nYou can add me to your server using [this link.]({invite_url})",
                color=Color.red() if guild_count >= limit else Color.blurple()
            )
            
            if guild_count >= limit:
                embed.description = "You can't invite jim right now since count hit the limit."
            
            embed.set_footer(text="Note: Requires advanced permissions for full functionality, and the invitation is limited to 90 servers due to discord limitation.")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception(f"Failed to get info: {e}")
            await interaction.followup.send("Error.")

    @group.command(name="name_signature", description="Shows temporary signature for the bot.")
    async def namesignature(self, interaction: discord.Interaction):
        await interaction.response.defer()

        await interaction.followup.send(f"{self.bot.name_signature}; {self.bot.session_uuid}")

    @group.command(name="school_date",description="Check if owner of the bot is in school")
    async def check_if_pox_is_school_day(self,ctx):
        await ctx.response.send_message(f"Pox is {"in school day." if stuff.is_weekday(datetime.now(pytz.timezone("Asia/Tokyo"))) else "not in school day."}")
    
    @group.command(name="active",description="Check if owner of the bot is active")
    async def is_pox_active(self, ctx: Interaction):
        now = datetime.now(pytz.timezone('Asia/Tokyo'))
        isWeekday = stuff.is_weekday(now)
        isFaster = stuff.is_specificweek(now,2) or stuff.is_specificweek(now,4)
        isInSchool = stuff.is_within_hour(now,7,16) if isWeekday and not isFaster else (stuff.is_within_hour(now,7,15) if isWeekday and isFaster else False)
        isSleeping = stuff.is_sleeping(now,23,7) if isWeekday else stuff.is_within_hour(now,2,12)
        status = ""
        
        if isInSchool:
            status = "Pox is in school."
        elif isSleeping:
            status = "Pox is sleeping."
        else:
            status = "Pox is sometime active."
        
        await ctx.response.send_message(f"{status}\nMay the result varies by the time, cuz it is very advanced to do... also this is not accurate.")
    
    @group.command(name="os_info", description="Shows operating system information.")
    async def os_info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        e = discord.Embed(title="Operating System Information")

        system = platform.system()

        if platform.system() == "Linux":
            os_rel = platform.freedesktop_os_release()
            if os_rel:
                os_type = os_rel.get("ID") if os_rel else "unknown"
                if os_type == "ubuntu":
                    distro_name = distro.name()
                    distro_version = distro.version()
                    e.add_field(name="Distro", value=f"{distro_name} {distro_version}")
                else:
                    e.add_field(name="Platform", value=f"{platform.platform(aliased=True)} ({os_type})")
            else:
                e.add_field(name="Platform", value=platform.platform(aliased=True))
        elif platform.system() == "Windows":
            e.add_field(name="Platform", value="Windows " + " ".join(list(platform.win32_ver())))
        else:
            e.add_field(name="Platform", value=platform.platform(aliased=True))
        
        await interaction.followup.send(embed=e)
    
    @group.command(name="feedback", description="Send developer a feedback.")
    async def send_feedback(self, interaction: Interaction):
        await interaction.response.send_modal(FeedbackModal(self.bot))
async def setup(bot):
    await bot.add_cog(Info(bot))