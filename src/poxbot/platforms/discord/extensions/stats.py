import pathlib
import re
from datetime import datetime
from io import BytesIO

import matplotlib.pyplot as plt
from discord import Color, Embed, File, Interaction, Member, Message, app_commands
from discord.ext import commands
from janome.tokenizer import Tokenizer
from matplotlib import use
from nltk.stem.snowball import stopwords
from nltk.tokenize import word_tokenize
from pytz import UTC
from wordcloud import WordCloud

from ....application import PoxBot
from ....persistence.database.stats import StatisticsDatabase

use('Agg')


class StatsCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot
        self.db: StatisticsDatabase | None = bot.database.stats
        self.tokenizer = Tokenizer()

        self.eng_stopwords = set(stopwords.words('english'))
        self.spa_stopwords = set(stopwords.words('spanish'))
        self.rus_stopwords = set(stopwords.words('russian'))

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

        valid_words = []
        url_pattern = re.compile(r'https?://\S+|www\.\S+')

        for row in rows:
            content = (
                row.get('content', '')
                if isinstance(row, dict)
                else getattr(row, 'content', '')
            )
            content = url_pattern.sub('', content)
            content = re.sub(r'<@!?\d+>|<#\d+>|<@&\d+>|:\w+:|\d+', '', content)

            if not content.strip():
                continue

            if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', content):
                for token in self.tokenizer.tokenize(content):
                    pos_str: str = getattr(token, 'part_of_speech', '')
                    surface: str = getattr(token, 'surface', '')

                    if pos_str and surface:
                        main_pos = pos_str.split(',', maxsplit=1)[0]

                        if (
                            main_pos == '名詞'
                            and len(surface) > 1
                            and not surface.isspace()
                            and not surface.isdigit()
                        ):
                            valid_words.append(surface)

            words_tokens = word_tokenize(content.lower())
            valid_words.extend(
                word
                for word in words_tokens
                if len(word) > 1
                and word.isalnum()
                and word not in self.eng_stopwords
                and word not in self.spa_stopwords
                and word not in self.rus_stopwords
                and not re.search(
                    r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]',
                    word,
                )
            )

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
        description='Generates a graph of messages per hour',
    )
    @app_commands.describe(
        target='Specify if you want to specify member (Use empty for whole channel)',
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

        def generate_chart():
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(8, 4.5))

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

            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            plt.close(fig)
            return buf

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


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
