# ruff: file-ignore[import-outside-top-level]
from __future__ import annotations

import asyncio
import pathlib
import re
import threading
from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING, Any

from discord import Color, Embed, File, Interaction, Member, Message, app_commands
from discord.ext import commands
from pytz import UTC

if TYPE_CHECKING:
    from ....application import PoxBot
    from ....persistence.database.stats import StatisticsDatabase


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
        if message.author.bot or message.content.startswith(('!', '/')):
            return

        if not message.content.strip():
            return

        if self.bot.database.stats:
            await self.bot.database.stats.cache_message(
                message_id=message.id,
                channel_id=message.channel.id,
                guild_id=message.guild.id if message.guild else 0,
                author_id=message.author.id,
                content=message.content,
            )

            text_length = len(message.clean_content)

            xp_process_result = await self.bot.database.stats.add_xp(
                user_id=message.author.id,
                count=text_length,
                guild_id=message.guild.id if message.guild else 0,
            )

            if xp_process_result.get('leveled_up') and message.guild:
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
    async def wordcloud(self, interaction: Interaction, limit: int = 1000):
        limit = min(max(10, limit), 10000)

        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer()

        if not self.bot.database.stats:
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

        if not interaction.channel:
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
            )

        rows = await self.bot.database.stats.get_cached_messages(
            interaction.channel.id,
            limit,
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
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                ),
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

            for row in rows:
                # get_cached_messages() returns strings.
                content = (
                    row
                    if isinstance(row, str)
                    else (
                        row.get('content', '')
                        if isinstance(row, dict)
                        else getattr(row, 'content', '')
                    )
                )

                content = url_pattern.sub('', content)
                content = mention_pattern.sub('', content)

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
                content=f'Genarated word cloud from {len(rows)} of messages cached',
                file=discord_file,
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
    @app_commands.describe(
        target=app_commands.locale_str(
            'command.stats.active_pattern.parameters.target',
        ),
    )
    async def active_pattern_command(
        self,
        interaction: Interaction,
        target: Member | None = None,
    ):
        loc = await self.bot.get_locale(interaction)
        await interaction.response.defer(thinking=True)

        if not self.bot.database.stats:
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

        if not interaction.channel:
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
            )

        target_id = target.id if target else None
        rows = await self.bot.database.stats.get_active_pattern(
            interaction.channel.id,
            target_id,
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
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                ),
            )

        hour_counts = dict.fromkeys(range(24), 0)
        for row in rows:
            hour_counts[row['hour']] = row['count']

        hours = list(hour_counts.keys())
        counts = list(hour_counts.values())

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

            max_idx = counts.index(max(counts)) if max(counts) > 0 else 0
            if counts[max_idx] > 0:
                bars[max_idx].set_color('#3ba55d')

            buffer = BytesIO()
            figure.savefig(buffer, format='png', dpi=150)
            buffer.seek(0)
            figure.clear()
            return buffer

        try:
            img_buffer = await self.bot.loop.run_in_executor(None, generate_chart)

            if target:
                title_name = target.display_name
            else:
                chan = interaction.channel
                if hasattr(chan, 'name') and chan.name:  # pyright: ignore[reportAttributeAccessIssue]
                    title_name = f'#{chan.name}'  # pyright: ignore[reportAttributeAccessIssue]
                else:
                    recipient = getattr(chan, 'recipient', None) or getattr(
                        chan,
                        'recipients',
                        None,
                    )
                    if recipient:
                        if isinstance(recipient, (list, tuple)):
                            title_name = ', '.join(
                                getattr(r, 'display_name', str(r)) for r in recipient
                            )
                        else:
                            title_name = getattr(
                                recipient,
                                'display_name',
                                str(recipient),
                            )
                    else:
                        title_name = 'Direct Message'
            content_text = f'idk **{title_name}**'

            discord_file = File(fp=img_buffer, filename='active_pattern.png')
            await interaction.followup.send(content=content_text, file=discord_file)

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
