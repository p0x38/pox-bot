# ruff: file-ignore[import-outside-top-level]
from __future__ import annotations

import asyncio
import pathlib
import re
import threading
from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING, Any

from discord import (
    Color,
    Embed,
    File,
    Interaction,
    Message,
    TextChannel,
    Thread,
    app_commands,
)
from discord.ext import commands
from pytz import (UTC, timezone)

if TYPE_CHECKING:
    from ....application import PoxBot
    from ....persistence.database.stats import StatisticsDatabase


JST = timezone('Asia/Tokyo')
ACTIVE_PATTERN_SAMPLE_SIZE = 2000
MIN_ACTIVITY_SAMPLE_SIZE = 20


class StatsCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot
        self.db: StatisticsDatabase | None = bot.database.stats
        self._wordcloud_resources: (
            tuple[
                Any,
                set[str],
                set[str],
                set[str],
            ]
            | None
        ) = None
        self._wordcloud_resources_lock = threading.Lock()

    def _get_wordcloud_resources(
        self,
    ) -> tuple[Any, set[str], set[str], set[str]]:
        """Load and cache NLP resources only when word-cloud generation needs them."""
        with self._wordcloud_resources_lock:
            resources = self._wordcloud_resources
            if resources is None:
                from janome.tokenizer import Tokenizer
                from nltk.stem.snowball import stopwords

                resources = (
                    Tokenizer(),
                    set(stopwords.words('english')),
                    set(stopwords.words('spanish')),
                    set(stopwords.words('russian')),
                )
                self._wordcloud_resources = resources

            return resources

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if (
            message.author.bot
            or not message.guild
            or message.content.startswith(('!', '/'))
            or not message.content.strip()
        ):
            return

        if not self.db:
            return

        text_length = len(message.clean_content)

        xp_process_result = await self.db.add_xp(
            user_id=message.author.id,
            count=text_length,
            guild_id=message.guild.id,
        )

        if xp_process_result.get('leveled_up'):
            new_level = xp_process_result.get('new_level')

            self.bot.logger.debug(
                '%s reached to %d!',
                message.author.name,
                new_level,
            )

    group = app_commands.Group(
        name='stats',
        description=app_commands.locale_str('command.stats.description'),
    )

    @group.command(
        name='globaltop',
        description=app_commands.locale_str('command.stats.globaltop.description'),
    )
    async def global_leaderboard(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        embed = Embed()

        await interaction.response.defer()

        if self.db:
            rows = await self.db.get_leaderboard(sort_by='xp', limit=25)

            embed = Embed(
                title=self.bot.internal_translator.T(
                    'command.stats.top.embeds.default.title',
                    loc,
                ),
                color=Color.gold(),
            )
            description = ''

            if rows:
                for i, row in enumerate(rows, 1):
                    user = self.bot.get_user(row.user_id) or f'User({row.user_id})'
                    description += f'**{i}.** {user} • Lvl {row.level} ({row.xp} XP)\n'
            else:
                description = "Wow, there's no one inside here."

            embed.description = description
            await interaction.followup.send(embed=embed)
        else:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.database_not_available.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.database_not_available.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

    @group.command(
        name='top',
        description=app_commands.locale_str('command.stats.top.description'),
    )
    async def local_leaderboard(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)
        embed = Embed()

        await interaction.response.defer()

        if self.db:
            rows = await self.db.get_leaderboard(sort_by='xp', limit=25)

            embed = Embed(
                title=self.bot.internal_translator.T(
                    'command.stats.top.embeds.default.title',
                    loc,
                ),
                color=Color.gold(),
            )
            description = ''

            if rows:
                for i, row in enumerate(rows, 1):
                    user = self.bot.get_user(row.user_id) or f'User({row.user_id})'
                    description += f'**{i}.** {user} • Lvl {row.level} ({row.xp} XP)\n'
            else:
                description = "Wow, there's no one inside here."

            embed.description = description
            await interaction.followup.send(embed=embed)
        else:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.database_not_available.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.database_not_available.description',
                loc,
            )
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

    @group.command(
        name='wordcloud',
        description=app_commands.locale_str('command.stats.wordcloud.description'),
    )
    @app_commands.guild_only()
    async def wordcloud(self, interaction: Interaction, limit: int = 1000):
        limit = min(max(10, limit), 2000)

        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        channel = interaction.channel
        if not isinstance(channel, (TextChannel, Thread)):
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.unsupported_channel_type.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.unsupported_channel_type.description',
                        loc,
                    ),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                ),
                ephemeral=True,
            )

        guild = interaction.guild
        bot_member = guild.me if guild else None

        if bot_member is None and guild and self.bot.user:
            bot_member = guild.get_member(self.bot.user.id)

        if bot_member is None:
            return await interaction.followup.send(
                'Could not resolve the bot member.',
                ephemeral=True,
            )

        permissions = channel.permissions_for(bot_member)

        if not permissions.view_channel or not permissions.read_message_history:
            return await interaction.followup.send(
                'I need permission to view this channel and read its history.',
                ephemeral=True,
            )
        
        messages = [
            message
            async for message in channel.history(
                limit=limit,
                oldest_first=False,
            )
            if not message.author.bot and message.content.strip()
        ]

        contents = [message.clean_content for message in messages]
        message_count = len(contents)

        del messages

        if not contents:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.data_not_found.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.data_not_found.description',
                        loc,
                    ),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                ),
                ephemeral=True,
            )

        def extract_words() -> list[str]:
            from janome.tokenizer import Token
            from nltk.tokenize import word_tokenize

            tokenizer, eng_stopwords, spa_stopwords, rus_stopwords = (
                self._get_wordcloud_resources()
            )
            valid_words: list[str] = []
            url_pattern = re.compile(r'https?://\S+|www\.\S+')
            japanese_pattern = re.compile(
                r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]',
            )
            mention_pattern = re.compile(
                r'<@!?\d+>|<#\d+>|<@&\d+>|:\w+:|\d+',
            )

            for content in contents:
                content = url_pattern.sub('', content)  # ruff: ignore[redefined-loop-name]
                content = mention_pattern.sub('', content)  # ruff: ignore[redefined-loop-name]

                if not content.strip():
                    continue

                if japanese_pattern.search(content):
                    for token in tokenizer.tokenize(content, wakati=False):
                        if not isinstance(token, Token):
                            continue

                        surface = token.surface
                        main_pos = token.part_of_speech.split(',', maxsplit=1)[0]

                        if (
                            main_pos == '名詞'
                            and len(surface) > 1
                            and not surface.isspace()
                            and not surface.isdigit()
                        ):
                            valid_words.append(surface)

                valid_words.extend(
                    word
                    for word in word_tokenize(content.lower())
                    if (
                        len(word) > 1
                        and word.isalnum()
                        and word not in eng_stopwords
                        and word not in spa_stopwords
                        and word not in rus_stopwords
                        and not japanese_pattern.search(word)
                    )
                )

            return valid_words

        valid_words = await asyncio.to_thread(extract_words)

        if not valid_words:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.data_not_found.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.data_not_found.description',
                        loc,
                    ),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                ),
            )

        words_text = ' '.join(valid_words)

        try:
            font_path = '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'
            if not pathlib.Path(font_path).exists():  # ruff: ignore[blocking-path-method-in-async-function]
                font_path = '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf'

            def generate_wc():
                from wordcloud import WordCloud

                wc = WordCloud(
                    font_path=font_path,
                    width=900,
                    height=650,
                    background_color='black',
                    colormap='pastel',
                    regexp=r'\S+',
                ).generate(words_text)

                buf = BytesIO()
                wc.to_image().save(buf, format='PNG')
                buf.seek(0)
                return buf

            img_buffer = await self.bot.loop.run_in_executor(None, generate_wc)

            discord_file = File(fp=img_buffer, filename='wordcloud.png')
            await interaction.followup.send(
                content=(
                    f'Generated a word cloud from {message_count} recent messages. '
                    'Messages were processed temporarily and were not stored.'
                ),
                file=discord_file,
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f'画像生成でエラーが発生しちゃった D:< \nエラー内容: `{e}`',
            )

    @group.command(
        name='active_pattern',
        description=app_commands.locale_str(
            'command.stats.active_pattern.description',
        ),
    )
    @app_commands.guild_only()
    async def active_pattern_command(
        self,
        interaction: Interaction,
    ) -> None:
        loc = await self.bot.get_locale(interaction)  # ruff: ignore[unused-variable]
        await interaction.response.defer(thinking=True, ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel

        if guild is None or not isinstance(channel, (TextChannel, Thread)):
            return await interaction.followup.send(
                'This command requires a server text channel or thread.',
                ephemeral=True,
            )
        
        bot_member = guild.me

        if bot_member is None and self.bot.user:
            bot_member = guild.get_member(self.bot.user.id)

        if bot_member is None:
            return await interaction.followup.send(
                'Could not resolve the bot member.',
                ephemeral=True,
            )

        permissions = channel.permissions_for(bot_member)

        if not permissions.view_channel or not permissions.read_message_history:
            return await interaction.followup.send(
                'I need permission to view this channel and read its history.',
                ephemeral=True,
            )

        hour_counts = [0] * 24
        message_count = 0

        try:
            async for message in channel.history(
                limit=ACTIVE_PATTERN_SAMPLE_SIZE,
                oldest_first=False,
            ):
                if message.author.bot:
                    continue

                hour = message.created_at.astimezone(JST).hour

                hour_counts[hour] += 1
                message_count += 1

        except Exception:
            self.bot.logger.exception(
                'Failed to collect channel activity data for %s',
                channel.id,
            )

            return await interaction.followup.send(
                'Failed to retrieve channel activity.',
                ephemeral=True,
            )

        if message_count < MIN_ACTIVITY_SAMPLE_SIZE:
            return await interaction.followup.send(
                (
                    'Not enough activity to generate a useful chart. '
                    f'At least {MIN_ACTIVITY_SAMPLE_SIZE} human messages are required.'
                ),
                ephemeral=True,
            )

        hours = list(range(24))
        counts = hour_counts

        def generate_chart() -> BytesIO:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure

            figure = Figure(
                figsize=(8, 4.5),
                facecolor='#222222',
                constrained_layout=True,
            )
            FigureCanvasAgg(figure)

            ax = figure.subplots()
            ax.set_facecolor('#222222')
            ax.tick_params(colors='#b9bbbe')

            bars = ax.bar(
                hours,
                counts,
                color='#5865F2',
                edgecolor='#7289DA',
                alpha=0.8,
                width=0.7,
            )

            ax.set_title(
                'Chat Activity Pattern (24h)',
                fontsize=14,
                pad=15,
                color='white',
                fontweight='bold',
            )
            ax.set_xlabel('Hour of Day (JST)', fontsize=11, color='#b9bbbe')
            ax.set_ylabel('Message Count', fontsize=11, color='#b9bbbe')
            ax.set_xticks(range(0, 24, 2))
            ax.grid(axis='y', linestyle='--', alpha=0.3, color='#4f545c')

            for spine in ax.spines.values():
                spine.set_color('#4f545c')

            max_idx = counts.index(max(counts))

            bars[max_idx].set_color('#3ba55d')

            buffer = BytesIO()
            figure.savefig(buffer, format='png', dpi=150)
            buffer.seek(0)
            figure.clear()

            return buffer

        try:
            img_buffer = await asyncio.to_thread(generate_chart)

            embed = Embed(
                title='Channel Activity Pattern',
                description=(
                    f'Based on {message_count:,} human-authored messages '
                    f'from the latest {ACTIVE_PATTERN_SAMPLE_SIZE:,} messages.\n'
                    'All timestamps are displayed in JST.'
                ),
                color=Color.blurple(),
            )

            embed.set_image(url='attachment://active_pattern.png')

            await interaction.followup.send(
                embed=embed,
                file=File(
                    fp=img_buffer,
                    filename='active_pattern.png',
                ),
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(f'error: `{e}`')

    @group.command(
        name='activity',
        description=app_commands.locale_str(
            'command.stats.activity.description',
        ),
    )
    @app_commands.describe(
        days=app_commands.locale_str(
            'command.stats.activity.parameters.days',
        ),
    )
    async def activity_command(
        self,
        interaction: Interaction,
        days: app_commands.Range[int, 7, 90] = 30,
    ):
        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer(thinking=True)

        if self.db is None:
            return await interaction.followup.send(
                embed=Embed(
                    title=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.title',
                        loc,
                    ),
                    description=self.bot.internal_translator.T(
                        'error.embeds.database_not_available.description',
                        loc,
                    ),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                ),
            )

        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)

        try:
            rows = await self.db.get_daily_activity(
                start_date=start_date,
                end_date=end_date,
                guild_id=interaction.guild_id or 0,
            )

            if not rows:
                return await interaction.followup.send(
                    embed=Embed(
                        title=self.bot.internal_translator.T(
                            'error.embeds.data_not_found.title',
                            loc,
                        ),
                        description=self.bot.internal_translator.T(
                            'error.embeds.data_not_found.description',
                            loc,
                        ),
                        color=Color.orange(),
                        timestamp=datetime.now(UTC),
                    ),
                )

            # Include days with no activity so the graph has a continuous timeline.
            dates = [start_date + timedelta(days=offset) for offset in range(days)]
            daily_by_date = {row['date']: row for row in rows}

            messages = [
                int(daily_by_date.get(day, {}).get('messages') or 0) for day in dates
            ]
            characters = [
                int(daily_by_date.get(day, {}).get('characters') or 0) for day in dates
            ]
            xp_gained = [
                int(daily_by_date.get(day, {}).get('xp') or 0) for day in dates
            ]

            message_label = self.bot.internal_translator.T(
                'command.stats.activity.chart.messages',
                loc,
            )
            character_label = self.bot.internal_translator.T(
                'command.stats.activity.chart.characters',
                loc,
            )
            xp_label = self.bot.internal_translator.T(
                'command.stats.activity.chart.xp',
                loc,
            )

            def generate_chart() -> BytesIO:
                from matplotlib.backends.backend_agg import FigureCanvasAgg
                from matplotlib.figure import Figure

                figure = Figure(figsize=(10, 7), constrained_layout=True)
                FigureCanvasAgg(figure)
                axes = figure.subplots(3, 1, sharex=True)

                series = (
                    (messages, message_label),
                    (characters, character_label),
                    (xp_gained, xp_label),
                )

                for axis, (values, label) in zip(axes, series, strict=True):
                    axis.plot(
                        dates,
                        values,
                        marker='o',
                        markersize=3,
                        linewidth=1.8,
                    )
                    axis.set_ylabel(label)
                    axis.grid(axis='y', linestyle='--', alpha=0.35)

                axes[0].set_title(
                    self.bot.internal_translator.T(
                        'command.stats.activity.chart.title',
                        loc,
                    ),
                )

                tick_step = max(1, days // 10)
                tick_dates = dates[::tick_step]

                axes[-1].set_xticks(tick_dates)
                axes[-1].set_xticklabels(
                    [day.strftime('%m-%d') for day in tick_dates],
                    rotation=35,
                    ha='right',
                )
                axes[-1].set_xlabel(
                    self.bot.internal_translator.T(
                        'command.stats.activity.chart.date',
                        loc,
                    ),
                )

                buffer = BytesIO()
                figure.savefig(buffer, format='png', dpi=150)
                buffer.seek(0)
                return buffer

            image_buffer = await asyncio.to_thread(generate_chart)

            embed = Embed(
                title=self.bot.internal_translator.T(
                    'command.stats.activity.embeds.default.title',
                    loc,
                ),
                description=self.bot.internal_translator.T(
                    'command.stats.activity.embeds.default.period',
                    loc,
                ).format(
                    days=days,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                ),
                color=Color.blurple(),
                timestamp=datetime.now(UTC),
            )
            embed.set_image(url='attachment://daily_activity.png')

            await interaction.followup.send(
                embed=embed,
                file=File(
                    fp=image_buffer,
                    filename='daily_activity.png',
                ),
            )

        except Exception:
            self.bot.logger.exception(
                'Failed to generate the daily activity graph',
            )
            await interaction.followup.send(
                self.bot.internal_translator.T(
                    'command.stats.activity.errors.failed',
                    loc,
                ),
            )


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
