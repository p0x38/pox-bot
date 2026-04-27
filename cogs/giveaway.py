from datetime import datetime, timedelta
import json
import random
import discord
from discord.ext import commands, tasks
from discord import Colour, Embed, TextChannel, app_commands
from os.path import exists, join

import aiofiles

from logger import logger
from bot import PoxBot

GIVEAWAYS_FILE = 'data/giveaways.json'
GIVEAWAYS_EMOJI = "🥳"

class GiveawayCog(commands.Cog):
    giveaway = app_commands.Group(name="giveaway", description="Giveaway cog.")

    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.giveaways = {}
        self.path = join(self.bot.root_path, GIVEAWAYS_FILE)
        self.bot.loop.create_task(self._async_setup())
    
    async def _async_setup(self):
        await self.bot.wait_until_ready()
        await self._load_giveaways()
        self.giveaway_task.start()
    
    async def cog_unload(self):
        self.giveaway_task.cancel()
        self.bot.loop.create_task(self._save_giveaways())
    
    async def _load_giveaways(self):
        if exists(self.path):
            try:
                async with aiofiles.open(self.path, mode='r', encoding="utf-8") as f:
                    content = await f.read()
                
                if content:
                    data = json.loads(content)
                    self.giveaways = {str(k): v for k, v in data.items()}
                    logger.info(f"Loaded {len(self.giveaways)} active giveaways.")
                else:
                    self.giveaways = {}
                    logger.warning(f"Giveaways file was empty.")
            except json.JSONDecodeError:
                logger.error("Error loading giveaways.json. Starting with empty list.")
                self.giveaways = {}
            except Exception as e:
                logger.error(f"An unexcepted error occured during giveaway loading: {e}")
                self.giveaways = {}
        else:
            self.giveaways = {}
    
    async def _save_giveaways(self):
        active_giveaways = {
            mid: data for mid, data in self.giveaways.items()
            if data['end_time'] > datetime.now().timestamp()
        }

        async with aiofiles.open(self.path, mode='w+') as f:
            await f.write(json.dumps(active_giveaways, indent=4))
        
        self.giveaways = active_giveaways
        logger.info(f"Saved {len(self.giveaways)} active giveaways.")
    
    def _parse_duration(self, duration):
        duration = duration.lower()
        digit_index = next((i for i, char in enumerate(duration) if char.isdigit()), 0)
        
        amount_str = duration[digit_index:].strip('smhd')
        unit = duration.strip(amount_str).lower()
        
        if not amount_str.isdigit():
             raise ValueError("Amount must be a number.")
        
        amount = int(amount_str)

        if unit == 's':
            return timedelta(seconds=amount)
        elif unit == 'm':
            return timedelta(minutes=amount)
        elif unit == 'h':
            return timedelta(hours=amount)
        elif unit == 'd':
            return timedelta(days=amount)
        else:
            raise ValueError("Invalid duration unit. Use s, m, h, or d (e.g., '1h', '30m')")
    
    async def _giveaway_finished(self, message_id, giveaway_data):
        try:
            channel = self.bot.get_channel(giveaway_data['channel_id'])
            if not channel:
                logger.warning(f"Channel {giveaway_data['channel_id']} not found for giveaway {message_id}")
                return
            
            if not isinstance(channel, TextChannel): return

            message = await channel.fetch_message(message_id)
            reaction = discord.utils.get(message.reactions, emoji=GIVEAWAYS_EMOJI)

            users = []
            if reaction:
                users = [user async for user in reaction.users() if user != self.bot.user]

            if not users:
                await channel.send(f"Giveaway for **{giveaway_data['prize']}** has ended. No entries is in this giveaways :<")
            else:
                num_winners = min(giveaway_data['winners'], len(users))
                winners = random.sample(users, num_winners)
                winner_mentions = ' '.join([w.mention for w in winners])

                announcement = (
                    "**GIVEAWAY ENDED**\n\n"
                    f"The winner{'s' if num_winners > 1 else ''} of **{giveaway_data['prize']}** are: {winner_mentions}.\n"
                    f"Congratulations. Contact the host ({self.bot.get_user(giveaway_data['host_id']).mention}) to claim your prize."
                ) 
                await channel.send(announcement)

                edited_embed = message.embeds[0]
                edited_embed.title = "Giveaway has ended."
                edited_embed.colour = Colour.dark_red()
                edited_embed.description=f"~~**Prize:** {giveaway_data['prize']}~~\n**Winner{'s' if num_winners > 1 else ''}:** {winner_mentions}"
                await message.edit(embed=edited_embed, content="**Giveaway has finished**")
        except Exception as e:
            logger.exception(f"An error occured while ending giveaway {message_id}: {e}")
        finally:
            self.giveaways.pop(str(message_id), None)
            await self._save_giveaways()
    
    @tasks.loop(seconds=10.0)
    async def giveaway_task(self):
        expired_giveaways = []
        current_time = datetime.now().timestamp()

        for message_id, data in self.giveaways.items():
            if data['end_time'] <= current_time:
                expired_giveaways.append((message_id, data))
        
        for message_id, data in expired_giveaways:
            await self._giveaway_finished(message_id, data)
    
    @giveaway_task.before_loop
    async def before_giveaway_task(self):
        logger.info("Giveaway task started, ready to monitor prizes! :3")
    
    @giveaway.command(name="start", description="Starts a new giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def start_giveaway(self, interaction: discord.Interaction, duration: str, winners: app_commands.Range[int, 1], prize: str):
        await interaction.response.defer(ephemeral=True)

        try:
            time_delta = self._parse_duration(duration)
        except ValueError as e:
            return await interaction.followup.send(f"Whoops. {e}", ephemeral=True)
        
        end_time = datetime.now() + time_delta
        end_timestamp = end_time.timestamp()

        embed = Embed(
            title="Giveaway.",
            description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_timestamp)}:R>\n\nReact with {GIVEAWAYS_EMOJI} to enter.",
            color=Colour.gold(),
            timestamp=end_time
        )
        embed.set_footer(text=f"Hosted by: {interaction.user.display_name}")

        channel = interaction.channel or self.bot.get_channel(interaction.channel_id)
        if channel is None: return await interaction.followup.send("Whoops. An error occured.", ephemeral=True)
        message = await channel.send(embed=embed)
        emjij = await message.add_reaction(GIVEAWAYS_EMOJI)

        giveaway_data = {
            'channel_id': interaction.channel_id,
            'guild_id': interaction.guild_id,
            'end_time': end_timestamp,
            'winners': winners,
            'prize': prize,
            'host_id': interaction.user.id
        }

        self.giveaways[str(message.id)] = giveaway_data
        await self._save_giveaways() # <-- CRITICAL: Await the async save call here

        await interaction.followup.send(f"Giveaway for **{prize}** started. Find it here: ({message.jump_url})", ephemeral=True)

    @giveaway.command(name='end', description='Immediately ends an active giveaway.')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end_giveaway(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)

        if message_id not in self.giveaways:
            return await interaction.followup.send(f"❌ I couldn't find an active giveaway with the ID `{message_id}`. Maybe it already finished?", ephemeral=True)

        giveaway_data = self.giveaways[message_id]

        await self._giveaway_finished(int(message_id), giveaway_data)

        await interaction.followup.send(f"✅ Giveaway `{message_id}` has been forcefully ended and a winner (or winners!) has been selected.", ephemeral=True)
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need the **Manage Server** permission to run this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"An unexpected error happened: `{error}` :o", ephemeral=True)
            print(f"Giveaway Slash Command Error: {error}")


async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))