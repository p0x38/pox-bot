import asyncio
import contextlib
import re

from discord import Forbidden, Message
from discord.ext import commands

from ....application import PoxBot


class ScaryModeCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

        self.scary_duration: float = 60 * 10
        self.cooldown_time: float = self.scary_duration + (60 * 2)

        self._cooldown = commands.CooldownMapping.from_cooldown(
            1,
            self.cooldown_time,
            commands.BucketType.default,
        )

        self.scary_pattern = re.compile(r"^aren'?t you died$", re.IGNORECASE)

    async def _reset_scary_mode_after_delay(self, delay: float) -> None:
        await asyncio.sleep(delay)

        if hasattr(self.bot, 'constants'):
            self.bot.constants.scary_mode = False
            self.bot.logger.info('scary_mode toggled off')

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not self.bot.user:
            return

        if self.bot.user in message.mentions:
            cleaned_content = message.content.replace(self.bot.user.mention, '').strip()

            if self.scary_pattern.match(cleaned_content):
                bucket = self._cooldown.get_bucket(message)

                if not bucket:
                    return

                retry_after = bucket.update_rate_limit()
                if retry_after:
                    return

                with contextlib.suppress(Forbidden):
                    await message.delete()

                if hasattr(self.bot, 'constants'):
                    self.bot.constants.scary_mode = True
                    self.bot.logger.warning(
                        'Scary mode toggled on by %s',
                        message.author.display_name,
                    )

                task = asyncio.create_task(
                    self._reset_scary_mode_after_delay(self.scary_duration),
                )

                self.bot.tasks.add(task)
                task.add_done_callback(self.bot.tasks.discard)


async def setup(bot: PoxBot):
    await bot.add_cog(ScaryModeCog(bot))
