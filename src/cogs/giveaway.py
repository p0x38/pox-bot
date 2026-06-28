import random
from datetime import datetime, timedelta

import discord
from discord import Colour, Embed, TextChannel, app_commands
from discord.abc import Messageable
from discord.ext import commands, tasks
from pytz import UTC

from logger import logger
from src.bot import PoxBot
from src.models import GiveawayData


class GiveawayCog(commands.Cog):
    giveaway = app_commands.Group(name="giveaway", description="Giveaway cog.")

    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.giveaways = {}
        self.giveaway_emoji = "🥳"
        self.bot.loop.create_task(self._async_setup())

    async def _async_setup(self):
        await self.bot.wait_until_ready()
        await self._load_giveaways()
        self.giveaway_task.start()

    async def cog_unload(self):
        self.giveaway_task.cancel()
        self.bot.loop.create_task(self._save_giveaways())

    async def _load_giveaways(self):
        self.giveaways = {}
        if not getattr(self.bot, "giveaway_db", None) or not self.bot.giveaway_db:
            logger.warning("Giveaway database pool not available, skipping giveaway load.")
            return

        try:
            rows = await self.bot.giveaway_db.get_active_giveaways()
        except Exception as e:
            logger.exception(f"Failed to load giveaways from database: {e}")
            return

        self.giveaways = {
            str(g.message_id): g.to_dict()
            for g in rows if g
        }

        logger.info(f"Loaded {len(self.giveaways)} active giveaways from PostgreSQL.")

    async def _persist_giveaway(self, message_id: int, giveaway_data: dict):
        if not getattr(self.bot, "giveaway_db", None) or not self.bot.giveaway_db:
            return

        giveaway = GiveawayData(
            message_id=message_id,
            channel_id=giveaway_data["channel_id"],
            guild_id=giveaway_data["guild_id"],
            end_time=int(giveaway_data["end_time"]),
            winners=giveaway_data["winners"],
            prize=giveaway_data["prize"],
            host_id=giveaway_data["host_id"],
        )

        await self.bot.giveaway_db.save_giveaway(giveaway)

    async def _delete_giveaway(self, message_id: int):
        if not getattr(self.bot, "giveaway_db", None) or not self.bot.giveaway_db:
            return

        await self.bot.giveaway_db.delete_giveaway(message_id)

    async def _save_giveaways(self):
        active_giveaways = {
            mid: data for mid, data in self.giveaways.items()
            if data["end_time"] > datetime.now(UTC).timestamp()
        }

        self.giveaways = active_giveaways

        if getattr(self.bot, "giveaway_db", None) and self.bot.giveaway_db:
            for message_id, data in active_giveaways.items():
                await self._persist_giveaway(int(message_id), data)

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
                logger.warning(
                    f"Channel {giveaway_data['channel_id']} not found for giveaway {message_id}")
                return

            if not isinstance(channel, TextChannel):
                return

            message = await channel.fetch_message(message_id)
            reaction = discord.utils.get(message.reactions, emoji=self.giveaway_emoji)

            users = []
            if reaction:
                users = [user async for user in reaction.users() if user != self.bot.user]

            if not users:
                await channel.send(
                    f"Giveaway for **{giveaway_data['prize']}** has ended. "
                    f"No entries is in this giveaways :<")
            else:
                num_winners = min(giveaway_data['winners'], len(users))
                winners = random.sample(users, num_winners)
                winner_mentions = ' '.join([w.mention for w in winners])

                host_user = self.bot.get_user(giveaway_data['host_id'])

                if not host_user:
                    return  # TODO: Improve this shit

                announcement = (
                    "**GIVEAWAY ENDED**\n\n"
                    f"The winner{
                        's'if num_winners > 1 else ''
                        } of **{giveaway_data['prize']}** are: {winner_mentions}.\n"
                    f"Congratulations. Contact the host ({host_user.mention}) to claim your prize."
                )
                await channel.send(announcement)

                edited_embed = message.embeds[0]
                edited_embed.title = "Giveaway has ended."
                edited_embed.colour = Colour.dark_red()
                edited_embed.description = f"~~**Prize:** {giveaway_data['prize']}~~\n**Winner{
                    's' if num_winners > 1 else ''}:** {winner_mentions}"
                await message.edit(embed=edited_embed, content="**Giveaway has finished**")
        except Exception as e:
            logger.exception(f"An error occured while ending giveaway {message_id}: {e}")
        finally:
            self.giveaways.pop(str(message_id), None)
            await self._delete_giveaway(message_id)

    @tasks.loop(seconds=10.0)
    async def giveaway_task(self):
        expired_giveaways = []
        current_time = datetime.now(UTC).timestamp()

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
    async def start_giveaway(self, interaction: discord.Interaction, duration: str,
                             winners: app_commands.Range[int, 1], prize: str):
        await interaction.response.defer(ephemeral=True)

        try:
            time_delta = self._parse_duration(duration)
        except ValueError as e:
            return await interaction.followup.send(f"Whoops. {e}", ephemeral=True)

        end_time = datetime.now(UTC) + time_delta
        end_timestamp = end_time.timestamp()

        embed = Embed(
            title="Giveaway.",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{int(end_timestamp)}:R>\n\n"
                f"React with {self.giveaway_emoji} to enter."
            ),
            color=Colour.gold(),
            timestamp=end_time
        )
        embed.set_footer(text=f"Hosted by: {interaction.user.display_name}")

        channel = interaction.channel or (
            self.bot.get_channel(interaction.channel_id) if interaction.channel_id else None)
        if channel is None or not isinstance(channel, Messageable):
            return await interaction.followup.send("Whoops. An error occured.", ephemeral=True)
        message = await channel.send(embed=embed)
        await message.add_reaction(self.giveaway_emoji)

        giveaway_data = {
            'channel_id': interaction.channel_id,
            'guild_id': interaction.guild_id,
            'end_time': end_timestamp,
            'winners': winners,
            'prize': prize,
            'host_id': interaction.user.id
        }

        self.giveaways[str(message.id)] = giveaway_data
        await self._persist_giveaway(message.id, giveaway_data)

        await interaction.followup.send(
            f"Giveaway for **{prize}** started. Find it here: ({message.jump_url})", ephemeral=True)

    @giveaway.command(name='end', description='Immediately ends an active giveaway.')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end_giveaway(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)

        if message_id not in self.giveaways:
            return await interaction.followup.send(
                f"❌ I couldn't find an active giveaway with the ID `{message_id}`. "
                f"Maybe it already finished?", ephemeral=True)

        giveaway_data = self.giveaways[message_id]

        await self._giveaway_finished(int(message_id), giveaway_data)

        await interaction.followup.send(
            f"✅ Giveaway `{message_id}` has been forcefully ended.", ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Server** permission to run this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"An unexpected error happened: `{error}` :o",
                                                    ephemeral=True)
            print(f"Giveaway Slash Command Error: {error}")


async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))
