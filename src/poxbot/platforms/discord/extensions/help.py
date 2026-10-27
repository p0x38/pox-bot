from __future__ import annotations

import math
from collections import defaultdict

from discord import (
    AppCommandType,
    ButtonStyle,
    Color,
    GroupChannel,
    Interaction,
    SelectOption,
    app_commands,
    ui,
)
from discord.ext import commands

from ....application import PoxBot

COMMANDS_PER_PAGE = 5
CATEGORY_OPTIONS_PER_PAGE = 23
GENERAL_CATEGORY = "__general__"

CATEGORY_TRANSLATION_KEYS = {
    "admin": "command.help.categories.admin",
    "channel": "command.help.categories.channel",
    "chatbot": "command.help.categories.chatbot",
    "contributors": "command.help.categories.contributors",
    "conversion": "command.help.categories.conversion",
    "economy": "command.help.categories.economy",
    "eew": "command.help.categories.eew",
    "globalchat": "command.help.categories.globalchat",
    "guild": "command.help.categories.guild",
    "image": "command.help.categories.image",
    "info": "command.help.categories.info",
    "logs": "command.help.categories.logs",
    "message": "command.help.categories.message",
    "midi": "command.help.categories.midi",
    "minecraft": "command.help.categories.minecraft",
    "moderation": "command.help.categories.moderation",
    "roblox": "command.help.categories.roblox",
    "role": "command.help.categories.role",
    "stats": "command.help.categories.stats",
    "user": "command.help.categories.user",
    "user_global": "command.help.categories.user_global",
    "welcome": "command.help.categories.welcome",
}

SUBGROUP_TRANSLATION_KEYS = {
    ("moderation", "blacklist"): "command.help.subgroups.moderation.blacklist",
    ("moderation", "word"): "command.help.subgroups.moderation.word",
    ("moderation", "user"): "command.help.subgroups.moderation.user",
}


class HelpCategorySelect(ui.Select):
    _PREVIOUS_PAGE = "__help_category_previous__"
    _NEXT_PAGE = "__help_category_next__"

    def __init__(self, help_view: HelpLayoutView) -> None:
        self.help_view = help_view

        category_items = list(help_view.categories.items())
        start = help_view.category_page * CATEGORY_OPTIONS_PER_PAGE
        end = start + CATEGORY_OPTIONS_PER_PAGE
        visible_categories = category_items[start:end]

        options: list[SelectOption] = []
        if help_view.category_page > 0:
            options.append(
                SelectOption(
                    label=help_view.translate(
                        "command.help.previous_categories",
                        "Previous categories...",
                    )[:100],
                    value=self._PREVIOUS_PAGE,
                    emoji="⬅️",
                ),
            )

        options.extend(
            SelectOption(
                label=help_view.category_label(category)[:100],
                value=category,
                description=help_view.translate(
                    "command.help.category_option_description",
                    "{count} command(s)",
                    count=len(items),
                )[:100],
                default=category == help_view.selected_category,
            )
            for category, items in visible_categories
        )

        if end < len(category_items):
            options.append(
                SelectOption(
                    label=help_view.translate(
                        "command.help.next_categories",
                        "More categories...",
                    )[:100],
                    value=self._NEXT_PAGE,
                    emoji="➡️",
                ),
            )

        super().__init__(
            placeholder=help_view.translate(
                "command.help.select_placeholder",
                "Select a command category...",
            )[:150],
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: Interaction) -> None:
        value = self.values[0]
        category_page = self.help_view.category_page

        if value == self._PREVIOUS_PAGE:
            category_page -= 1
            category = None
            page = 0
        elif value == self._NEXT_PAGE:
            category_page += 1
            category = None
            page = 0
        else:
            category = value
            page = 0

        await self.help_view.show_state(
            interaction,
            category=category,
            page=page,
            category_page=category_page,
        )


class HelpNavigationButton(ui.Button):
    def __init__(
        self,
        help_view: HelpLayoutView,
        *,
        action: str,
        label: str,
        disabled: bool = False,
        style: ButtonStyle = ButtonStyle.secondary,
    ) -> None:
        super().__init__(label=label, style=style, disabled=disabled)
        self.help_view = help_view
        self.action = action

    async def callback(self, interaction: Interaction) -> None:
        category = self.help_view.selected_category
        page = self.help_view.page
        category_page = self.help_view.category_page

        if self.action == "home":
            category = None
            page = 0
            category_page = 0
        elif self.action == "previous":
            page -= 1
        elif self.action == "next":
            page += 1

        await self.help_view.show_state(
            interaction,
            category=category,
            page=page,
            category_page=category_page,
        )


class HelpLayoutView(ui.LayoutView):
    def __init__(
        self,
        bot: PoxBot,
        *,
        owner_id: int,
        locale: str,
        categories: dict[str, list[app_commands.Command]],
        selected_category: str | None = None,
        page: int = 0,
        category_page: int = 0,
    ) -> None:
        super().__init__(timeout=180)

        self.bot = bot
        self.owner_id = owner_id
        self.locale = locale
        self.categories = categories
        self.selected_category = (
            selected_category if selected_category in categories else None
        )
        self.category_page = min(
            max(category_page, 0),
            self.category_page_count - 1,
        )
        self.page = (
            min(max(page, 0), self.page_count - 1)
            if self.selected_category is not None
            else 0
        )

        self._build_layout()

    @property
    def page_count(self) -> int:
        if self.selected_category is None:
            return 1

        count = len(self.categories[self.selected_category])
        return max(1, math.ceil(count / COMMANDS_PER_PAGE))

    @property
    def category_page_count(self) -> int:
        count = max(len(self.categories), 1)
        return max(1, math.ceil(count / CATEGORY_OPTIONS_PER_PAGE))

    def translate(self, key: str, fallback: str, **kwargs) -> str:
        translator = getattr(self.bot, "internal_translator", None)
        if translator is not None:
            translated = translator.T(key, self.locale, **kwargs)
            if translated != key:
                return str(translated)

        try:
            return fallback.format(**kwargs)
        except (KeyError, ValueError):
            return fallback

    def category_label(self, category: str) -> str:
        if category == GENERAL_CATEGORY:
            return self.translate("command.help.categories.general", "General")

        normalized = category.casefold().replace(" ", "_")
        key = CATEGORY_TRANSLATION_KEYS.get(normalized)
        fallback = category.replace("_", " ").title()

        if key is None:
            return fallback

        return self.translate(key, fallback)

    def _build_layout(self) -> None:
        navigation = ui.ActionRow(
            HelpNavigationButton(
                self,
                action="previous",
                label=self.translate("command.help.previous", "Previous"),
                disabled=self.selected_category is None or self.page == 0,
            ),
            HelpNavigationButton(
                self,
                action="home",
                label=self.translate("command.help.home", "Home"),
                style=ButtonStyle.primary,
                disabled=self.selected_category is None,
            ),
            HelpNavigationButton(
                self,
                action="next",
                label=self.translate("command.help.next", "Next"),
                disabled=(
                    self.selected_category is None
                    or self.page >= self.page_count - 1
                ),
            ),
        )

        self.add_item(
            ui.Container(
                ui.TextDisplay(
                    "# "
                    + self.translate(
                        "command.help.title",
                        "pox-bot Help Center",
                    )
                    + "\n"
                    + self.translate(
                        "command.help.subtitle",
                        "Browse available slash commands by category.",
                    ),
                ),
                ui.Separator(),
                ui.ActionRow(HelpCategorySelect(self)),
                ui.Separator(),
                ui.TextDisplay(self._render_content()),
                ui.Separator(),
                navigation,
                accent_color=Color.blurple(),
            ),
        )

    @staticmethod
    def _subgroup_for(
        command: app_commands.Command,
    ) -> app_commands.Group | None:
        parent = command.parent
        if isinstance(parent, app_commands.Group) and parent.parent is not None:
            return parent
        return None

    def _subgroup_label(
        self,
        category: str,
        subgroup: app_commands.Group,
    ) -> str:
        key = SUBGROUP_TRANSLATION_KEYS.get((category, subgroup.name))
        fallback = subgroup.name.replace("_", " ").title()
        if key is None:
            return fallback
        return self.translate(key, fallback)

    def _description(
        self,
        value: object,
        *,
        fallback: str | None = None,
    ) -> str:
        raw = str(value or "").strip()
        if not raw:
            return fallback or self.translate(
                "command.help.no_description",
                "No description provided.",
            )

        # Command and group descriptions are often locale keys in pox-bot.
        if raw.startswith("command.") and raw.endswith(".description"):
            default = fallback or self.translate(
                "command.help.no_description",
                "No description provided.",
            )
            return self.translate(raw, default)

        return raw

    @staticmethod
    def _signature(command: app_commands.Command) -> str:
        parameters = getattr(command, "parameters", ())
        parts = [
            f"<{parameter.display_name}>"
            if parameter.required
            else f"[{parameter.display_name}]"
            for parameter in parameters
        ]
        return f" {' '.join(parts)}" if parts else ""

    @staticmethod
    def _truncate(text: str, limit: int = 3500) -> str:
        if len(text) <= limit:
            return text
        marker = "\n\n-# ..."
        return text[: limit - len(marker)].rstrip() + marker

    def _render_overview(self) -> str:
        total = sum(len(items) for items in self.categories.values())
        summary = self.translate(
            "command.help.overview_stats",
            "{total} commands across {categories} categories.",
            total=total,
            categories=len(self.categories),
        )
        category_lines = "\n".join(
            f"- **{self.category_label(category)}**: "
            + self.translate(
                "command.help.category_command_count",
                "{count} command(s)",
                count=len(items),
            )
            for category, items in self.categories.items()
        )

        overview = self.translate(
            "command.help.overview",
            "Welcome! Choose a category to explore its commands.",
        )
        return self._truncate(f"## {overview}\n\n{summary}\n\n{category_lines}")

    def _render_content(self) -> str:
        if self.selected_category is None:
            return self._render_overview()

        category = self.selected_category
        commands_in_category = self.categories[category]
        start = self.page * COMMANDS_PER_PAGE
        page_commands = commands_in_category[start : start + COMMANDS_PER_PAGE]
        entries: list[str] = []
        current_subgroup: str | None = None

        for command in page_commands:
            subgroup = self._subgroup_for(command)
            subgroup_id = subgroup.qualified_name if subgroup is not None else None

            if subgroup_id != current_subgroup:
                current_subgroup = subgroup_id
                if subgroup is not None:
                    subgroup_title = self._subgroup_label(category, subgroup)
                    entries.append(f"### {subgroup_title}")

            description = self._description(command.description)
            signature = self._signature(command)
            entries.append(
                f"**`/{command.qualified_name}{signature}`**\n{description}",
            )

        body = "\n\n".join(entries) or self.translate(
            "command.help.empty_category",
            "No commands are available in this category.",
        )
        pagination = self.translate(
            "command.help.pagination",
            "Page {current} of {total}",
            current=self.page + 1,
            total=self.page_count,
        )
        content = (
            f"## {self.category_label(category)}\n\n"
            f"{body}\n\n-# {pagination}"
        )
        return self._truncate(content)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            self.translate(
                "command.help.not_yours",
                "This help menu belongs to another user.",
            ),
            ephemeral=True,
        )
        return False

    async def show_state(
        self,
        interaction: Interaction,
        *,
        category: str | None,
        page: int,
        category_page: int,
    ) -> None:
        view = HelpLayoutView(
            self.bot,
            owner_id=self.owner_id,
            locale=self.locale,
            categories=self.categories,
            selected_category=category,
            page=page,
            category_page=category_page,
        )
        await interaction.response.edit_message(view=view)


class HelpCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot

    @staticmethod
    def _explicit_context_value(
        contexts: app_commands.AppCommandContext | None,
        context_name: str,
    ) -> bool | None:
        if contexts is None:
            return None

        private_name = f"_{context_name}"
        if hasattr(contexts, private_name):
            return getattr(contexts, private_name)

        return getattr(contexts, context_name, None)

    def _supports_context(
        self,
        command: app_commands.Command,
        context_name: str,
    ) -> bool:
        current: app_commands.Command | app_commands.Group | None = command
        explicitly_allowed = False

        while current is not None:
            contexts = current.allowed_contexts
            value = self._explicit_context_value(contexts, context_name)

            if value is False:
                return False
            if value is True:
                explicitly_allowed = True
            elif contexts is not None and self._has_explicit_contexts(contexts):
                default_value = self._explicit_context_value(
                    self.bot.tree.allowed_contexts,
                    context_name,
                )
                if default_value is not True:
                    return False

            if (
                current.guild_only
                and context_name != "guild"
                and value is not True
            ):
                return False

            current = current.parent

        if explicitly_allowed:
            return True

        default_contexts = self.bot.tree.allowed_contexts
        default_value = self._explicit_context_value(
            default_contexts,
            context_name,
        )
        if default_value is not None:
            return default_value

        return not self._has_explicit_contexts(default_contexts)

    @classmethod
    def _has_explicit_contexts(
        cls,
        contexts: app_commands.AppCommandContext,
    ) -> bool:
        return any(
            cls._explicit_context_value(contexts, name) is not None
            for name in ("guild", "dm_channel", "private_channel")
        )

    @staticmethod
    def _interaction_context_name(interaction: Interaction) -> str:
        if interaction.guild is not None:
            return "guild"

        context = interaction.context
        if context.dm_channel:
            return "dm_channel"
        if context.private_channel:
            return "private_channel"
        
        if isinstance(interaction.channel, GroupChannel):
            return "private_channel"
        return "dm_channel"

    def _build_categories(
        self,
        interaction: Interaction,
    ) -> dict[str, list[app_commands.Command]]:
        context_name = self._interaction_context_name(interaction)

        roots = {
            command.name: command
            for command in self.bot.tree.get_commands(
                type=AppCommandType.chat_input,
            )
        }

        if interaction.guild is not None:
            roots.update(
                {
                    command.name: command
                    for command in self.bot.tree.get_commands(
                        guild=interaction.guild,
                        type=AppCommandType.chat_input,
                    )
                },
            )

        categories: dict[str, list[app_commands.Command]] = defaultdict(list)
        general: list[app_commands.Command] = []

        for root in roots.values():
            if root.name == "help":
                continue

            if isinstance(root, app_commands.Group):
                visible_commands = [
                    command
                    for command in root.walk_commands()
                    if isinstance(command, app_commands.Command)
                    and self._supports_context(command, context_name)
                ]
                if visible_commands:
                    categories[root.name].extend(visible_commands)
            elif (
                isinstance(root, app_commands.Command)
                and self._supports_context(root, context_name)
            ):
                general.append(root)

        if general:
            categories[GENERAL_CATEGORY].extend(general)

        if not categories:
            categories[GENERAL_CATEGORY] = []

        return {
            category: sorted(
                items,
                key=lambda command: command.qualified_name.casefold(),
            )
            for category, items in sorted(
                categories.items(),
                key=lambda item: item[0].casefold(),
            )
        }

    @app_commands.command(
        name="help",
        description=app_commands.locale_str("command.help.description"),
    )
    @app_commands.allowed_contexts(
        guilds=True,
        dms=True,
        private_channels=True,
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def show_help(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        locale = str(await self.bot.get_locale(interaction))
        view = HelpLayoutView(
            self.bot,
            owner_id=interaction.user.id,
            locale=locale,
            categories=self._build_categories(interaction),
        )
        await interaction.edit_original_response(view=view)


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(HelpCog(bot))
