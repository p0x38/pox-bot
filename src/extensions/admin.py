import asyncio
import contextlib
from time import monotonic, perf_counter

from discord import Color, Embed, HTTPException, Interaction, RateLimited, app_commands
from discord.ext import commands

from src.core.bot import PoxBot
from src.groups import AdminGroup
from src.managers.extension import ExtensionOperation, ExtensionProgress
from src.utils.number_format import format_duration


class AdminOnlyCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot

    group = AdminGroup(
        name="admin",
        description=app_commands.locale_str("command.admin.description"),
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    )

    def bar(self, current: int, total: int, size: int = 12) -> str:
        if total == 0:
            return "█" * size

        filled = int(size * current / total)
        return "█" * filled + "░" * (size - filled)

    def make_reload_embed(self, title: str, data: ExtensionProgress):
        percent = (data.current / data.total * 100) if data.total else 100

        embed = Embed(
            description=(
                f"{title}\n\n"
                f"`[{self.bar(data.current, data.total)}]` {percent:.1f}%\n"
                f"Progress: {data.current}/{data.total}\n"
                f"Loaded: {data.loaded} | Failed: {data.failed}"
            )
            or "Processing...",
            color=Color.yellow(),
        )

        return embed

    async def safe_edit_message(self, message, embed: Embed, retries: int = 3):
        for _i in range(retries):
            try:
                await message.edit(embed=embed)
                return True
            except (HTTPException, RateLimited) as e:
                has_ratelimited = isinstance(e, RateLimited) or (isinstance(e, HTTPException) and e.status == 429)
                if has_ratelimited:
                    retry_after = getattr(e, "retry_after", 2.0)
                    self.bot.logger.warning(f"Rate limited, retrying in {retry_after}s...")
                    await asyncio.sleep(retry_after)
                else:
                    raise e
        return False

    @group.command(
        name="reload_cogs",
        description=app_commands.locale_str("command.admin.reload_cogs.description"),
    )
    async def reload_cogs(
        self,
        interaction: Interaction,
    ):
        manager = self.bot.extension_manager

        await interaction.response.defer(thinking=True)

        msg = await interaction.followup.send(
            embed=Embed(description="Starting process..."),
            wait=True,
        )

        all_exts = list(self.bot.extensions.keys())
        targets = [e.replace("src.extensions.", "") for e in all_exts if not e.endswith(".admin")]

        if not targets:
            return await interaction.followup.send(
                embed=Embed(
                    description=self.bot.internal_translator.T(
                        "error.embeds.no_reloadable_extensions.description",
                    )
                )
            )

        await asyncio.sleep(1.0)

        last = None
        last_edit = 0.0
        reload_start_ms = perf_counter()

        async for progress in manager.stream_operation(
            self.bot,
            ExtensionOperation.RELOAD,
            targets,
            concurrency=5,
            exclusions=["admin"],
        ):
            now = monotonic()

            if now - last_edit < 0.5 and not progress.finished:
                continue

            last_edit = now
            last = progress

            embed = self.make_reload_embed("Reloading cogs...", progress)

            with contextlib.suppress(Exception):
                await self.safe_edit_message(msg, embed)

        if last and last.result:
            failed = [r.extension for r in last.result.children if r.failed]
            elapsed = perf_counter() - reload_start_ms

            result_desc = (
                f"Reloading completed in {format_duration(elapsed)}\n\n{last.loaded} successful\n{last.failed} failed\n"
            )

            if failed:
                result_desc += "\n**Failed Extensions:**\n" + "\n".join(f"`{f}`" for f in failed)

            final = Embed(description=result_desc, color=Color.green() if last.failed == 0 else Color.red())

            try:
                await self.safe_edit_message(msg, final)
            except Exception:
                await interaction.followup.send(embed=final)

    @group.command(name="reboot", description=app_commands.locale_str("command.admin.reboot.description"))
    async def reboot(self, interaction: Interaction):
        await interaction.response.send_message("The bot gonna reboot itself soon.")
        self.bot.should_restart = True

        await self.bot.close()


async def setup(bot):
    await bot.add_cog(AdminOnlyCog(bot))
