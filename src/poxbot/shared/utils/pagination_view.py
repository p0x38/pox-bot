from __future__ import annotations

import contextlib
from collections.abc import Sequence

import discord

PaginationPage = str


class PaginationView(discord.ui.LayoutView):
    def __init__(
        self,
        pages: Sequence[PaginationPage] = (),
        *,
        owner_id: int | None = None,
        initial_page: int = 0,
        timeout: float | None = 180.0,
        wrap: bool = False,
        empty_message: str = "No pages to display.",
        unauthorized_message: str = (
            "Only the user who invoked this command can use these buttons."
        ),
    ) -> None:
        super().__init__(timeout=timeout)

        self.pages = list(pages)
        self.owner_id = owner_id
        self.wrap = wrap
        self.empty_message = empty_message
        self.unauthorized_message = unauthorized_message
        self.message: discord.Message | None = None

        if self.pages:
            if not 0 <= initial_page < len(self.pages):
                raise ValueError("initial_page is outside the page range.")
            self.current_page = initial_page
        else:
            if initial_page != 0:
                raise ValueError(
                    "initial_page must be 0 when there are no pages."
                )
            self.current_page = 0

        self._build_layout()

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def current(self) -> str | None:
        if not self.pages:
            return None
        return self.pages[self.current_page]

    def _build_layout(self) -> None:
        self.clear_items()

        content = self.current or self.empty_message
        page_label = (
            f"-# Page {self.current_page + 1} / {self.page_count}"
            if self.pages
            else "-# Page 0 / 0"
        )

        if len(content) + len(page_label) > 4000:
            raise ValueError(
                "The page content and pagination label exceed "
                "the 4000-character Components V2 limit."
            )

        at_first = self.current_page == 0
        at_last = self.current_page >= self.page_count - 1
        disabled = self.is_finished() or self.page_count <= 1

        self.first_button = discord.ui.Button(
            emoji="⏮️",
            style=discord.ButtonStyle.secondary,
            disabled=disabled or (not self.wrap and at_first),
        )
        self.previous_button = discord.ui.Button(
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=disabled or (not self.wrap and at_first),
        )
        self.next_button = discord.ui.Button(
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=disabled or (not self.wrap and at_last),
        )
        self.last_button = discord.ui.Button(
            emoji="⏭️",
            style=discord.ButtonStyle.secondary,
            disabled=disabled or (not self.wrap and at_last),
        )

        self.first_button.callback = self._go_first
        self.previous_button.callback = self._go_previous
        self.next_button.callback = self._go_next
        self.last_button.callback = self._go_last

        navigation = discord.ui.ActionRow(
            self.first_button,
            self.previous_button,
            discord.ui.Button(
                label=(
                    f"{self.current_page + 1} / {self.page_count}"
                    if self.pages
                    else "0 / 0"
                ),
                style=discord.ButtonStyle.secondary,
                disabled=True,
            ),
            self.next_button,
            self.last_button,
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(content),
            discord.ui.Separator(),
            discord.ui.TextDisplay(page_label),
            navigation,
            accent_color=discord.Color.blurple(),
        )

        self.add_item(container)

    async def _refresh_message(
        self,
        interaction: discord.Interaction | None = None,
    ) -> None:
        """Refresh the existing message after changing the pages."""
        self._build_layout()

        if (
            interaction is not None
            and interaction.type is discord.InteractionType.component
            and not interaction.response.is_done()
        ):
            await interaction.response.edit_message(view=self)

            if interaction.message is not None:
                self.message = interaction.message

            return

        if self.message is None:
            return

        try:
            self.message = await self.message.edit(view=self)
        except discord.NotFound:
            self.message = None

    async def add_page(
        self,
        page: PaginationPage,
        *,
        interaction: discord.Interaction | None = None,
    ) -> int:
        return await self.insert_page(
            self.page_count,
            page,
            interaction=interaction,
        )

    async def insert_page(
        self,
        index: int,
        page: PaginationPage,
        *,
        interaction: discord.Interaction | None = None,
    ) -> int:
        if not 0 <= index <= self.page_count:
            raise IndexError("Page insertion index is out of range.")

        was_empty = not self.pages
        self.pages.insert(index, page)

        if was_empty:
            self.current_page = 0
        elif index <= self.current_page:
            self.current_page += 1

        await self._refresh_message(interaction)
        return index

    async def remove_page(
        self,
        index: int | None = None,
        *,
        interaction: discord.Interaction | None = None,
    ) -> PaginationPage:
        if not self.pages:
            raise IndexError("Cannot remove a page from an empty paginator.")

        if index is None:
            index = self.current_page

        if not 0 <= index < self.page_count:
            raise IndexError("Page removal index is out of range.")

        removed = self.pages.pop(index)

        if not self.pages:
            self.current_page = 0
        elif index < self.current_page:
            self.current_page -= 1
        elif self.current_page >= self.page_count:
            self.current_page = self.page_count - 1

        await self._refresh_message(interaction)
        return removed

    async def replace_page(
        self,
        index: int,
        page: PaginationPage,
        *,
        interaction: discord.Interaction | None = None,
    ) -> None:
        if not 0 <= index < self.page_count:
            raise IndexError("Page replacement index is out of range.")

        self.pages[index] = page
        await self._refresh_message(interaction)

    async def set_pages(
        self,
        pages: Sequence[PaginationPage],
        *,
        interaction: discord.Interaction | None = None,
    ) -> None:
        self.pages = list(pages)
        self.current_page = min(
            self.current_page,
            max(0, self.page_count - 1),
        )
        await self._refresh_message(interaction)

    async def clear_pages(
        self,
        *,
        interaction: discord.Interaction | None = None,
    ) -> None:
        self.pages.clear()
        self.current_page = 0
        await self._refresh_message(interaction)

    async def goto(
        self,
        interaction: discord.Interaction,
        index: int,
    ) -> None:
        if not 0 <= index < self.page_count:
            raise IndexError("Page index is out of range.")

        await self._set_page(interaction, index)

    async def _set_page(
        self,
        interaction: discord.Interaction,
        index: int,
    ) -> None:
        if not self.pages:
            return

        self.current_page = (
            index % self.page_count
            if self.wrap
            else max(0, min(index, self.page_count - 1))
        )

        await self._refresh_message(interaction)

    async def _go_first(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await self._set_page(interaction, 0)

    async def _go_previous(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await self._set_page(interaction, self.current_page - 1)

    async def _go_next(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await self._set_page(interaction, self.current_page + 1)

    async def _go_last(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await self._set_page(interaction, self.page_count - 1)

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if self.owner_id is None or interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            self.unauthorized_message,
            ephemeral=True,
        )
        return False

    async def send(
        self,
        interaction: discord.Interaction,
        *,
        ephemeral: bool = False,
    ) -> discord.Message:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                view=self,
                ephemeral=ephemeral,
            )
            message = await interaction.original_response()

        elif (
            interaction.response.type
            is discord.InteractionResponseType.deferred_channel_message
        ):
            message = await interaction.edit_original_response(
                content=None,
                embeds=[],
                attachments=[],
                view=self,
            )

        else:
            message = await interaction.followup.send(
                view=self,
                ephemeral=ephemeral,
                wait=True,
            )

        self.message = message
        return message

    async def on_timeout(self) -> None:
        for button in (
            self.first_button,
            self.previous_button,
            self.next_button,
            self.last_button,
        ):
            button.disabled = True

        if self.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)
