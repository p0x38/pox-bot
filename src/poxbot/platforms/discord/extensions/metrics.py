import asyncio
import math
from time import perf_counter

from discord import Interaction, InteractionType, Message, app_commands
from discord.ext import commands, tasks

from ....application.bot import PoxBot


class OpenTelemetryMetrics(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self._original_tree_error = bot.tree.on_error
        # self._initialized_guilds = False

    async def _loop_lag_monitor(self):
        self._max_lag = 0.0
        while not self.bot.is_closed():
            try:
                start = perf_counter()
                await asyncio.sleep(0.1)
                lag = (perf_counter() - start) - 0.1

                if lag > self._max_lag:
                    self._max_lag = lag
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def cog_load(self):
        self.bot.tree.on_error = self._instrumented_tree_error
        self._lag_monitor_task = asyncio.create_task(self._loop_lag_monitor())
        self.update_all_gauges.start()

    async def cog_unload(self) -> None:
        self.bot.tree.on_error = self._original_tree_error
        self._lag_monitor_task.cancel()
        self.update_all_gauges.cancel()

    async def _instrumented_tree_error(
        self,
        interaction: Interaction,
        error: app_commands.AppCommandError,
    ):
        original_error = getattr(error, 'original', None)
        error_name = error.__class__.__name__

        if original_error is not None:
            full_error_string = (
                f'{error.__class__.__name__}:{original_error.__class__.__name__}'
            )
        else:
            full_error_string = error_name

        cmd_name = (
            interaction.command.qualified_name if interaction.command else 'unknown'
        )
        guild_name = (
            getattr(interaction.guild, 'name', 'DM') if interaction.guild else 'DM'
        )

        if self.bot.metrics:
            self.bot.metrics.increment_counter(
                name='bot_app_commands_total',
                description='Total count of error thrown in application commands.',
                amount=1,
                labels={
                    'command_name': cmd_name,
                    'server': str(interaction.guild.id if interaction.guild else 'DM'),
                    'guild_name': guild_name,
                    'status': 'error',
                    'error_type': full_error_string,
                },
            )

        await self._original_tree_error(interaction, error)  # type: ignore

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        start_time = perf_counter()
        interaction.extras['start_time'] = start_time

        interaction_type_str = interaction.type.name
        cmd_name = (
            interaction.command.qualified_name if interaction.command else 'unknown'
        )
        if interaction.type in (
            InteractionType.component,
            InteractionType.modal_submit,
        ):
            cmd_name = (
                interaction.data.get('custom_id', 'unknown_component')
                if interaction.data
                else 'unknown_component'
            )
        guild_name = (
            getattr(interaction.guild, 'name', 'DM') if interaction.guild else 'DM'
        )

        if self.bot.metrics:
            self.bot.metrics.increment_counter(
                name='bot_interactions_total',
                description='Total number of all Discord interaction received.',
                amount=1,
                labels={
                    'type': interaction_type_str,
                    'command_or_id': cmd_name,
                    'guild': str(interaction.guild_id or 'DM'),
                    'guild_name': guild_name,
                },
            )

        self.bot.counter_manager.increment('total_interactions')

        if interaction.guild:
            self.bot.counter_manager.increment_interaction(interaction.guild)
        elif interaction.channel:
            self.bot.counter_manager.increment_interaction(interaction.channel)

        if interaction.type != InteractionType.application_command:
            duration = perf_counter() - start_time

            if self.bot.metrics:
                self.bot.metrics.record_histogram(
                    name='bot_interaction_duration_seconds',
                    description=(
                        'The execution duration of all received interactions in seconds'
                    ),
                    value=duration,
                    labels={
                        'type': interaction_type_str,
                        'command_or_id': cmd_name,
                        'guild': str(interaction.guild_id or 'DM'),
                        'guild_name': guild_name,
                    },
                )

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: Interaction, command):
        if not command:
            return

        start = interaction.extras.pop('start_time', None)
        if start:
            duration = perf_counter() - start
            guild_name = (
                getattr(interaction.guild, 'name', 'DM') if interaction.guild else 'DM'
            )

            if self.bot.metrics:
                self.bot.metrics.record_histogram(
                    name='bot_app_command_duration_seconds',
                    description=(
                        'The execution duration of application commands in seconds'
                    ),
                    value=duration,
                    labels={
                        'command': command.qualified_name,
                        'guild': str(interaction.guild_id or 'DM'),
                        'guild_name': guild_name,
                        'status': 'success',
                    },
                )

                self.bot.metrics.record_histogram(
                    name='bot_interaction_duration_seconds',
                    description=(
                        'The execution duration of all received interactions in seconds'
                    ),
                    value=duration,
                    labels={
                        'type': 'application_command',
                        'command_or_id': command.qualified_name,
                        'guild': str(interaction.guild_id or 'DM'),
                        'guild_name': guild_name,
                    },
                )

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return

        guild_name = getattr(message.guild, 'name', 'DM') if message.guild else 'DM'

        if self.bot.metrics:
            self.bot.metrics.increment_counter(
                name='bot_message_events_total',
                description='Total count of messages sent in every servers.',
                amount=1,
                labels={
                    'server': str(message.guild.id) if message.guild else 'DM',
                    'guild_name': guild_name,
                },
            )

        self.bot.counter_manager.increment('total_messages')
        if message.guild:
            self.bot.counter_manager.increment_guild(message.guild)
        else:
            self.bot.counter_manager.increment(f'messages:{message.channel.id}')

    @commands.Cog.listener()
    async def on_resumed(self):
        if self.bot.metrics:
            self.bot.metrics.increment_counter(
                name='bot_gateway_reconnects_total',
                description='Total number of Gatway reconnections.',
                amount=1,
            )

    @commands.Cog.listener()
    async def on_socket_event_type(self, event_type: str):
        if self.bot.metrics:
            self.bot.metrics.increment_counter(
                name='bot_gateway_events_total',
                description='Total number of Gateway events received from Discord.',
                amount=1,
                labels={'event_type': event_type},
            )

    async def calculate_loop_lag(self):
        lag_to_record = getattr(self, '_max_lag', 0.0)
        self._max_lag = 0.0

        lag_to_record = max(0.0, lag_to_record)
        if self.bot.metrics:
            self.bot.metrics.set_gauge(
                'bot_event_loop_lag_seconds',
                'The current event loop execution lag in seconds',
                lag_to_record,
            )

    async def record_latency_per_shard(self):
        for _id, latency in self.bot.latencies:
            if math.isinf(latency) or math.isnan(latency):
                continue

            if self.bot.metrics:
                self.bot.metrics.set_gauge(
                    name='bot_shard_latency_seconds',
                    description=(
                        'The current WebSocket latency'
                        'to the Discord API Gateway in seconds per shard'
                    ),
                    value=latency,
                    labels={
                        'shard_id': str(id),
                    },
                )

    @tasks.loop(seconds=15)
    async def update_all_gauges(self):
        if not self.bot.is_ready():
            return

        await self.calculate_loop_lag()
        await self.record_latency_per_shard()

        await self.bot.counter_manager.save_async()

        if self.bot.metrics:
            self.bot.metrics.set_gauge(
                'bot_guilds',
                'The total number of Discord guild the bot is currently connected to',
                len(self.bot.guilds),
            )
            self.bot.metrics.set_gauge(
                'bot_users',
                'The total number of unique users visible to the bot across all shards',
                len(self.bot.users),
            )
            self.bot.metrics.set_gauge(
                'bot_shards',
                'The total number of shards configured for this bot instance',
                self.bot.shard_count or 1,
            )

    @update_all_gauges.before_loop
    async def before_update_all_gauges(self):
        await self.bot.wait_until_ready()

        if self.bot.metrics:
            for key, value in list(self.bot.counter_manager._counters.items()):
                if value <= 0:
                    continue

                if key.startswith('messages:'):
                    guild_id_str = key.split(':')[1]
                    if guild_id_str.isdigit() and (
                        guild := self.bot.get_guild(int(guild_id_str))
                    ):
                        self.bot.metrics.increment_counter(
                            name='bot_message_events_total',
                            description=(
                                'Total count of messages sent in every servers.'
                            ),
                            amount=value,
                            labels={'server': guild_id_str, 'guild_name': guild.name},
                        )
                elif key.startswith('interactions:guild:'):
                    guild_id_str = key.split(':')[2]
                    if guild_id_str.isdigit() and (
                        guild := self.bot.get_guild(int(guild_id_str))
                    ):
                        self.bot.metrics.increment_counter(
                            name='bot_interactions_total',
                            description=(
                                'Total number of all Discord interaction received.'
                            ),
                            amount=value,
                            labels={
                                'type': 'application_command',
                                'guild': guild_id_str,
                                'guild_name': guild.name,
                            },
                        )


async def setup(bot: PoxBot):
    await bot.add_cog(OpenTelemetryMetrics(bot))
