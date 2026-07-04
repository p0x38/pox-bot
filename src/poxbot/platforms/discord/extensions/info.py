import asyncio
import platform
import textwrap
from datetime import datetime

import psutil
from discord import (
    ButtonStyle,
    Color,
    Embed,
    Interaction,
    Locale,
    SelectOption,
    TextStyle,
    app_commands,
    ui,
)
from discord.ext import commands
from discord.ui import Select
from pytz import UTC

from ....application.bot import PoxBot
from ....shared.utils.formats.duration import format_duration


class FeedbackModal(ui.Modal):
    def __init__(self, bot: PoxBot):
        super().__init__(title='Feedback', timeout=None, custom_id='feedback-modal')
        self.bot = bot
        self.paginator = commands.Paginator()

        self.feedback = ui.TextInput(
            label='Give me a feedback to the bot.',
            style=TextStyle.long,
            placeholder='Write a feedback here...',
            required=True,
            min_length=25,
            max_length=900,
            custom_id='feedback-text',
        )
        self.add_item(self.feedback)

    async def send_feedback(self, interaction: Interaction):
        try:
            app = self.bot.application or await self.bot.application_info()
            if not app:
                return

            target_user = None

            if app.team and app.team.owner_id:
                target_user = await self.bot.fetch_user(app.team.owner_id)
            elif app.owner:
                target_user = app.owner

            if not target_user:
                self.bot.logger.error("Couldn't find owner")
                return

            feedback_content = textwrap.fill(
                textwrap.dedent(self.feedback.value.strip()), width=50,
            )
            if not feedback_content:
                feedback_content = 'No feedback text'

            self.paginator.add_line('=== New feedback received ===')
            self.paginator.add_line('-' * 30)
            self.paginator.add_line(f'User: {interaction.user.display_name}')
            self.paginator.add_line('Feedback content:')

            for line in feedback_content.splitlines():
                self.paginator.add_line(textwrap.indent(line, prefix=' ' * 4))

            for page in self.paginator.pages:
                await target_user.send(page)

            self.paginator.clear()
        except Exception:
            self.bot.logger.exception('Exception thrown while trying to send feedback!')

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.send_feedback(interaction)
        await interaction.followup.send('Thank you for your feedback!', ephemeral=True)

    async def on_error(self, interaction: Interaction, error: Exception) -> None:  # noqa: ARG002
        self.bot.logger.exception(
            'Exception thrown while trying to process the submission',
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(
                'Oops! something went wrong.', ephemeral=True, delete_after=10,
            )


class DynamicInfoView(ui.View):
    def __init__(self, cog: 'InfoCog', bot: PoxBot, locale: Locale | str):
        super().__init__(timeout=120)
        self.cog = cog
        self.bot = bot
        self.locale = locale

        self.select_callback.options = [
            SelectOption(
                label=self.bot.internal_translator.T(
                    'modal.DynamicInfoView.options.identity.label', locale,
                ),
                value='identity',
                emoji='🛠️',
            ),
            SelectOption(
                label=self.bot.internal_translator.T(
                    'modal.DynamicInfoView.options.stats.label', locale,
                ),
                value='stats',
                emoji='📈',
            ),
            SelectOption(
                label=self.bot.internal_translator.T(
                    'modal.DynamicInfoView.options.hardware.label', locale,
                ),
                value='hardware',
                emoji='🔧',
            ),
        ]
        self.select_callback.placeholder = self.bot.internal_translator.T(
            'modal.DynamicInfoView.options.placeholder', locale,
        )

        url_button = ui.Button(
            label=self.bot.internal_translator.T(
                'modal.DynamicInfoView.buttons.url_button.label', locale,
            ),
            style=ButtonStyle.link,
            url='https://github.com/p0x38/pox-bot',
        )
        self.feedback_button.label = self.bot.internal_translator.T(
            'modal.DynamicInfoView.buttons.suggest_button.label', locale,
        )
        self.add_item(url_button)

    @ui.select(min_values=1, max_values=1)
    async def select_callback(self, interaction: Interaction, select: Select):
        await interaction.response.defer()
        category = select.values[0]

        stats_data = await self.get_stats_data(interaction)
        category_data = stats_data.get(category)

        if not category_data:
            return

        embed = Embed(
            title=category_data['title'],
            color=Color.blue(),
            timestamp=datetime.now(UTC),
        )
        for _, field_info in category_data['fields'].items():
            embed.add_field(
                name=field_info['display'], value=field_info['value'], inline=True,
            )

        await interaction.edit_original_response(embed=embed, view=self)

    @ui.button(style=ButtonStyle.primary)
    async def feedback_button(self, interaction: Interaction, _button: ui.Button):
        await interaction.response.send_modal(FeedbackModal(self.bot))

    async def get_stats_data(self, interaction: Interaction):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if (
                hasattr(self.bot, 'database')
                and self.bot.database
                and self.bot.database.settings
            )
            else interaction.locale
        )

        (
            cpu_usage,
            memory_info,
            disk_usage,
            process_cpu,
            process_memory,
        ) = await asyncio.gather(
            asyncio.to_thread(psutil.cpu_percent, interval=0.1),
            asyncio.to_thread(psutil.virtual_memory),
            asyncio.to_thread(psutil.disk_usage, '/'),
            asyncio.to_thread(self.bot.resources.process.cpu_percent, interval=0.1),
            asyncio.to_thread(self.bot.resources.process.memory_percent),
        )

        uptime_str = self.bot.internal_translator.T('text.unknown', loc)
        if self.bot.statistics.bot_launch_datetime:
            uptime_delta = datetime.now(UTC) - self.bot.statistics.bot_launch_datetime
            uptime_str = format_duration(uptime_delta.total_seconds())

        temp = {
            'identity': {
                'title': self.bot.internal_translator.T(
                    'modal.DynamicInfoView.data.identity.title', loc,
                ),
                'fields': {
                    'uuid': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.identity.uuid.display', loc,
                        ),
                        'value': f'{self.bot.statistics.session_uuid}',
                    },
                    'version': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.identity.version.display', loc,
                        ),
                        'value': (
                            f'git+{
                                self.bot.git_info.commit_hash[:7]
                                if self.bot.git_info.commit_hash
                                else "No commit hash found"
                            }'
                            f'{
                                self.bot.git_info.commit_message
                                if self.bot.git_info.commit_message
                                else "No commit message found"
                            }'
                        ),
                    },
                    'signature': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.identity.signature.display', loc,
                        ),
                        'value': self.bot.statistics.session_signature
                        or 'Unknown signature',
                    },
                    'uptime': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.identity.uptime.display', loc,
                        ),
                        'value': f'{uptime_str}',
                    },
                    'latency': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.identity.latency.display', loc,
                        ),
                        'value': f'{self.bot.latency * 1000:.2f}ms',
                    },
                    'owner': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.identity.owner.display', loc,
                        ),
                        'value': 'Check GitHub repository then',
                    },
                },
            },
            'stats': {
                'title': self.bot.internal_translator.T(
                    'modal.DynamicInfoView.data.stats.title', loc,
                ),
                'fields': {
                    'guilds': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.stats.guilds.display', loc,
                        ),
                        'value': f'{len(self.bot.guilds):,}',
                    },
                    'users': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.stats.users.display', loc,
                        ),
                        'value': f'{len(self.bot.users):,}',
                    },
                    'msgs': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.stats.msgs.display', loc,
                        ),
                        'value': f'{self.bot.statistics.handled_prefix_commands:,}',
                    },
                    'channels': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.stats.channels.display', loc,
                        ),
                        'value': f'{len(list(self.bot.get_all_channels())):,}',
                    },
                    'interactions': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.stats.interactions.display', loc,
                        ),
                        'value': f'P: {
                            self.bot.statistics.interaction_statistics.total
                        } | F: {self.bot.statistics.interaction_statistics.failed}',
                    },
                    'cached_values': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.stats.cached_values.display',
                            loc,
                        ),
                        'value': f'{self.bot.shared_cache.get_count():,}',
                    },
                },
            },
            'hardware': {
                'title': self.bot.internal_translator.T(
                    'modal.DynamicInfoView.data.hardware.title', loc,
                ),
                'fields': {
                    'platform': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.platform.display', loc,
                        ),
                        'value': self.bot.runtime.get_platform_info(),
                    },
                    'cpu': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.cpu.display', loc,
                        ),
                        'value': self.cog.make_bar(cpu_usage),
                    },
                    'cpu_own': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.cpu_own.display', loc,
                        ),
                        'value': self.cog.make_bar(process_cpu),
                    },
                    'ram': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.ram.display', loc,
                        ),
                        'value': self.cog.make_bar(memory_info.percent),
                    },
                    'ram_own': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.ram_own.display', loc,
                        ),
                        'value': self.cog.make_bar(process_memory),
                    },
                    'disk': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.disk.display', loc,
                        ),
                        'value': self.cog.make_bar(disk_usage.percent),
                    },
                    'ram_details': {
                        'display': self.bot.internal_translator.T(
                            'modal.DynamicInfoView.data.hardware.ram_details.display',
                            loc,
                        ),
                        'value': (
                            f'{memory_info.used // (1024**2)}MB /'
                            '{memory_info.total // (1024**2)}MB'
                        ),
                    },
                },
            },
        }

        return temp


class InfoCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

    group = app_commands.Group(
        name='info',
        description=app_commands.locale_str('command.info.description'),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True,
        ),
    )

    def make_bar(self, percent, length=10):
        filled_length = int(length * percent / 100)
        bar = '#' * filled_length + '_' * (length - filled_length)
        return f'[`{bar}`] {percent}%'

    @group.command(
        name='retrieve',
        description=app_commands.locale_str('command.info.retrieve.description'),
    )
    async def retrieve_bot_information(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if (
                hasattr(self.bot, 'database')
                and self.bot.database
                and self.bot.database.settings
            )
            else interaction.locale
        )

        view = DynamicInfoView(self, self.bot, loc)
        e = Embed(
            title=self.bot.internal_translator.T(
                'command.info.retrieve.embeds.default.title', loc,
            ),
            description=self.bot.internal_translator.T(
                'command.info.retrieve.embeds.default.description', loc,
            ),
        )
        e.set_footer(
            text=self.bot.internal_translator.T(
                'command.info.retrieve.embeds.default.footer',
                loc,
                {'platform': platform.system()},
            ),
        )

        await interaction.followup.send(embed=e, view=view)

    @group.command(
        name='ping',
        description=app_commands.locale_str('command.info.ping.description'),
    )
    async def ping_bot(self, interaction: Interaction):
        await interaction.response.defer()
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if (
                hasattr(self.bot, 'database')
                and self.bot.database
                and self.bot.database.settings
            )
            else interaction.locale
        )

        embed = Embed(
            title=self.bot.i18n_manager.T(
                'command.info.ping.embeds.default.title',
                loc,
                latency=str(round(self.bot.latency * 10000) / 100),
            ),
        )

        rows_to_add = {
            'Shard ID': self.bot.shard_id
            or self.bot.i18n_manager.T('text.standalone', loc),
            'Shards': self.bot.shard_count
            or self.bot.i18n_manager.T('text.standalone', loc),
        }

        for k, v in rows_to_add.items():
            embed.add_field(name=k, value=v, inline=True)

        await interaction.followup.send(embed=embed)

    @group.command(
        name='invite',
        description=app_commands.locale_str('command.info.invite.description'),
    )
    async def invite(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            loc = (
                await self.bot.database.settings.get_locale(interaction)
                if (
                    hasattr(self.bot, 'database')
                    and self.bot.database
                    and self.bot.database.settings
                )
                else interaction.locale
            )

            guild_count = len(self.bot.guilds)
            limit = self.bot.constants.max_servers

            scopes = 'bot%20applications.commands'
            perms = 1395868252224

            if not self.bot.user:
                return
            client_id = self.bot.user.id
            invite_url = f'https://discord.com/oauth2/authorize?client_id={client_id}&permissions={perms}&scope={scopes}'

            embed = Embed(
                title=self.bot.i18n_manager.T(
                    'command.info.invite.embeds.default.title', loc,
                ),
                description=self.bot.i18n_manager.T(
                    'command.info.invite.embeds.default.description',
                    loc,
                    {'invite_url': invite_url},
                ),
                color=Color.red() if guild_count >= limit else Color.blurple(),
            )

            if guild_count >= limit:
                embed.description = self.bot.i18n_manager.T(
                    'command.info.invite.error.hardlimited', loc,
                )

            embed.set_footer(
                text=self.bot.i18n_manager.T(
                    'command.info.invite.embeds.default.footer', loc,
                ),
            )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            self.bot.logger.exception(f'Failed to get info: {e}')
            await interaction.followup.send('Error.')

    @group.command(
        name='feedback',
        description=app_commands.locale_str('command.info.feedback.description'),
    )
    async def send_feedback(self, interaction: Interaction):
        await interaction.response.send_modal(FeedbackModal(self.bot))

    @group.command(
        name='memory_check',
        description=app_commands.locale_str('command.info.memory_check.description'),
    )
    async def run_memorycheck(self, interaction: Interaction):
        await interaction.response.defer()

        stats = self.bot.perf_monitor.get_stats()
        embed = self.bot.perf_monitor.create_embed(stats)

        await interaction.followup.send(embed=embed)


async def setup(bot: PoxBot):
    await bot.add_cog(InfoCog(bot))
