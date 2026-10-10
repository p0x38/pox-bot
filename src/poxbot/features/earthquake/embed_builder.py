
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from discord import Color, Embed, Locale

from ..i18n.translator import I18nTranslator
from .p2pquake import (
    EEW,
    JMAQuake,
    JMATsunami,
    P2PEvent,
)


class P2PQuakeEmbedBuilder:
    BASE_KEY = "earthquake_reports.jma"

    MAX_ROWS_PER_EMBED = 20
    MAX_ROW_VALUE_LENGTH = 220

    def __init__(
        self,
        translator: I18nTranslator,
        locale: str | Locale,
    ) -> None:
        self.translator = translator
        self.locale = locale

    def _t(self, key: str, **kwargs: object) -> str:
        return self.translator.T(
            f"{self.BASE_KEY}.{key}",
            self.locale,
            kwargs,
        )

    def _lookup(
        self,
        key: str,
        value: str | int | float | None,
        *,
        fallback: str | None = None,
    ) -> str:
        if value is None:
            return fallback or self._t("text.embed.unknown")

        raw = f"{value:g}" if isinstance(value, float) else str(value)

        translation_key = f"text.{self.BASE_KEY}.{key}.{raw}"
        translated = self.translator.T(translation_key, self.locale)

        if translated == translation_key:
            return fallback if fallback is not None else raw

        return translated

    def _scale(self, value: int | float | None) -> str:
        if value is None or value < 0:
            return self._t("embed.unknown")

        return self._lookup("point_intensity_scale", value)

    def _number(self, value: int | float | None) -> str:
        if value is None or value < 0:
            return self._t("embed.unknown")

        return f"{value:g}"

    def _time(self, value: datetime | None) -> str:
        if value is None:
            return self._t("embed.unknown")

        return value.strftime("%Y/%m/%d %H:%M:%S %Z")

    def _field(
        self,
        embed: Embed,
        label_key: str,
        value: str,
        *,
        inline: bool = False,
    ) -> None:
        value = value.strip() or self._t("embed.unknown")

        if len(value) > 1024:
            value = value[:1021] + "..."

        embed.add_field(
            name=self._t(label_key)[:256],
            value=value,
            inline=inline,
        )

    def _base(
        self,
        event: P2PEvent,
        *,
        title_key: str,
        color: Color,
        description_key: str | None = None,
    ) -> Embed:
        embed = Embed(
            title=self._t(title_key),
            description=(
                self._t(description_key)
                if description_key is not None
                else None
            ),
            color=color,
            timestamp=event.time,
        )
        embed.set_footer(text=f"P2P地震情報 API • ID: {event.id}")
        return embed

    def build(self, event: P2PEvent) -> Embed:
        if isinstance(event, JMAQuake):
            return self._build_quake(event)

        if isinstance(event, JMATsunami):
            return self._build_tsunami(event)

        if isinstance(event, EEW):
            return self._build_eew(event)

        raise TypeError(f"Unsupported event: {type(event).__name__}")

    def _build_quake(self, event: JMAQuake) -> Embed:
        earthquake = event.earthquake
        hypocenter = earthquake.hypocenter

        max_scale = earthquake.max_scale
        color = (
            Color.red()
            if max_scale is not None and max_scale >= 55
            else Color.orange()
        )

        embed = self._base(
            event,
            title_key="embed.earthquake.title",
            color=color,
        )

        embed.description = self._lookup("issue_type", event.issue.type)

        self._field(
            embed,
            "embed.earthquake.max_intensity",
            self._lookup(
                "earthquake_max_scale",
                max_scale,
                fallback=self._t("embed.unknown"),
            ),
            inline=True,
        )

        self._field(
            embed,
            "embed.earthquake.magnitude",
            self._number(hypocenter.magnitude if hypocenter else None),
            inline=True,
        )

        depth = hypocenter.depth if hypocenter else None
        self._field(
            embed,
            "embed.earthquake.depth",
            f"{depth:g} km" if depth is not None and depth >= 0
            else self._t("embed.unknown"),
            inline=True,
        )

        self._field(
            embed,
            "embed.earthquake.epicenter",
            (
                hypocenter.name
                if hypocenter and hypocenter.name
                else self._t("embed.unknown")
            ),
        )

        self._field(
            embed,
            "embed.earthquake.origin_time",
            self._time(earthquake.time),
            inline=True,
        )

        self._field(
            embed,
            "embed.earthquake.issue_time",
            self._time(event.issue.time),
            inline=True,
        )

        self._field(
            embed,
            "embed.earthquake.correction",
            self._lookup(
                "issue_correction",
                event.issue.correct or "None",
            ),
        )

        for field_key, value in (
            ("domestic_tsunami", earthquake.domestic_tsunami),
            ("foreign_tsunami", earthquake.foreign_tsunami),
        ):
            if value:
                self._field(
                    embed,
                    f"embed.earthquake.{field_key}",
                    self._lookup(field_key, value),
                )

        if event.points:
            lines = [
                f"**{point.pref} {point.addr}** — {self._scale(point.scale)}"
                for point in event.points[:10]
            ]

            if len(event.points) > 10:
                lines.append(
                    self._t(
                        "embed.earthquake.more_points",
                        count=len(event.points) - 10,
                    )
                )

            self._field(
                embed,
                "embed.earthquake.observed_points",
                "\n".join(lines),
            )

        comment = event.comments.free_form_comment
        if comment:
            self._field(
                embed,
                "embed.earthquake.comments",
                comment,
            )

        return embed

    def _build_tsunami(self, event: JMATsunami) -> Embed:
        priority = {
            "MajorWarning": 3,
            "Warning": 2,
            "Watch": 1,
            "Unknown": 0,
        }

        grade = max(
            (area.grade or "Unknown" for area in event.areas),
            key=lambda value: priority.get(value, 0),
            default="Unknown",
        )

        color = {
            "MajorWarning": Color.dark_red(),
            "Warning": Color.red(),
            "Watch": Color.gold(),
        }.get(grade, Color.blue())

        if event.cancelled:
            embed = self._base(
                event,
                title_key="embed.tsunami.cancelled_title",
                description_key="embed.tsunami.cancelled_description",
                color=Color.light_grey(),
            )
        else:
            embed = self._base(
                event,
                title_key="embed.tsunami.title",
                color=color,
            )

        self._field(
            embed,
            "embed.tsunami.source",
            event.issue.source,
            inline=True,
        )

        self._field(
            embed,
            "embed.tsunami.issue_time",
            self._time(event.issue.time),
            inline=True,
        )

        if event.cancelled:
            return embed

        for area in event.areas[:10]:
            lines = [
                self._lookup(
                    "tsunami_grade",
                    area.grade or "Unknown",
                )
            ]

            if area.max_height:
                height = area.max_height.description
                if not height and area.max_height.value is not None:
                    height = str(area.max_height.value)

                if height:
                    lines.append(
                        f"{self._t('embed.tsunami.max_height')}: {height}"
                    )

            if area.first_height:
                first = area.first_height

                if first.arrival_time:
                    lines.append(
                        f"{self._t('embed.tsunami.arrival_time')}: "
                        f"{self._time(first.arrival_time)}"
                    )

                if first.condition:
                    lines.append(
                        self._lookup(
                            "tsunami_first_height_conditions",
                            first.condition,
                        )
                    )

            if area.immediate is True:
                lines.append(self._t("embed.tsunami.immediate"))

            embed.add_field(
                name=area.name[:256],
                value="\n".join(lines)[:1024],
                inline=False,
            )

        if len(event.areas) > 10:
            self._field(
                embed,
                "embed.tsunami.other_areas",
                self._t(
                    "embed.tsunami.more_areas",
                    count=len(event.areas) - 10,
                ),
            )

        if not event.areas:
            self._field(
                embed,
                "embed.tsunami.forecast_areas",
                self._t("embed.no_data"),
            )

        return embed

    def _build_eew(self, event: EEW) -> Embed:
        if event.cancelled:
            title_key = "embed.eew.cancelled_title"
            description_key = "embed.eew.cancelled_description"
            color = Color.light_grey()
        elif event.test:
            title_key = "embed.eew.test_title"
            description_key = "embed.eew.test_description"
            color = Color.purple()
        else:
            title_key = "embed.eew.title"
            description_key = "embed.eew.description"
            color = Color.red()

        embed = self._base(
            event,
            title_key=title_key,
            description_key=description_key,
            color=color,
        )

        self._field(
            embed,
            "embed.eew.report_number",
            event.issue.serial,
            inline=True,
        )

        self._field(
            embed,
            "embed.eew.issue_time",
            self._time(event.issue.time),
            inline=True,
        )

        earthquake = event.earthquake

        if earthquake is not None:
            hypocenter = earthquake.hypocenter

            self._field(
                embed,
                "embed.eew.epicenter",
                hypocenter.reduce_name or hypocenter.name
                or self._t("embed.unknown"),
            )

            self._field(
                embed,
                "embed.eew.magnitude",
                self._number(hypocenter.magnitude),
                inline=True,
            )

            depth = hypocenter.depth
            self._field(
                embed,
                "embed.eew.depth",
                f"{depth:g} km" if depth is not None and depth >= 0
                else self._t("embed.unknown"),
                inline=True,
            )

            self._field(
                embed,
                "embed.eew.origin_time",
                self._time(earthquake.origin_time),
                inline=True,
            )

            self._field(
                embed,
                "embed.eew.arrival_time",
                self._time(earthquake.arrival_time),
                inline=True,
            )

        if event.cancelled:
            return embed

        for area in event.areas[:10]:
            start = self._scale(area.scale_from)
            end = self._scale(area.scale_to)

            intensity = (
                start if area.scale_from == area.scale_to
                else f"{start} - {end}"
            )

            lines = [
                f"{self._t('embed.eew.predicted_intensity')}: {intensity}"
            ]

            if area.kind_code:
                lines.append(
                    f"{self._t('embed.eew.kind')}: "
                    + self._lookup(
                        "embed.eew.kind_codes",
                        area.kind_code,
                    )
                )

            if area.arrival_time:
                lines.append(
                    f"{self._t('embed.eew.estimated_arrival')}: "
                    f"{self._time(area.arrival_time)}"
                )

            embed.add_field(
                name=f"{area.pref} / {area.name}"[:256],
                value="\n".join(lines)[:1024],
                inline=False,
            )

        if len(event.areas) > 10:
            self._field(
                embed,
                "embed.eew.other_areas",
                self._t(
                    "embed.eew.more_areas",
                    count=len(event.areas) - 10,
                ),
            )

        return embed

    def _build_row(self, event: P2PEvent) -> tuple[str, str]:
        timestamp = event.time.strftime("%m/%d %H:%M:%S")
        parts: list[str] = []

        if isinstance(event, JMAQuake):
            kind = self._lookup("issue_type", event.issue.type)
            hypocenter = event.earthquake.hypocenter

            if hypocenter and hypocenter.name:
                parts.append(hypocenter.name)

            parts.append(
                f"{self._t('embed.rows.intensity')}: "
                f"{self._lookup('earthquake_max_scale', event.earthquake.max_scale)}"
            )

            if hypocenter and hypocenter.magnitude is not None:
                parts.append(
                    f"M{self._number(hypocenter.magnitude)}"
                )

        elif isinstance(event, JMATsunami):
            kind = self._t("embed.rows.tsunami")

            if event.cancelled:
                parts.append(self._t("embed.rows.cancelled"))
            else:
                names = [area.name for area in event.areas[:3]]

                if names:
                    parts.append("、".join(names))

                if len(event.areas) > 3:
                    parts.append(f"+{len(event.areas) - 3}")

        elif isinstance(event, EEW):
            kind = self._t("embed.rows.eew")

            if event.cancelled:
                parts.append(self._t("embed.rows.cancelled"))
            elif event.test:
                parts.append(self._t("embed.rows.test"))

            if event.earthquake is not None:
                hypocenter = event.earthquake.hypocenter

                if name := (hypocenter.reduce_name or hypocenter.name):
                    parts.append(name)

                if hypocenter.magnitude is not None:
                    parts.append(
                        f"M{self._number(hypocenter.magnitude)}"
                    )

            parts.append(
                f"{self._t('embed.rows.report_number')}: "
                f"{event.issue.serial}"
            )

        else:
            raise TypeError(
                f"Unsupported event type: {type(event).__name__}"
            )

        name = f"{timestamp} · {kind}"
        value = " | ".join(parts) or self._t("embed.unknown")

        if len(value) > self.MAX_ROW_VALUE_LENGTH:
            value = value[:self.MAX_ROW_VALUE_LENGTH - 3] + "..."

        return name, value

    def build_rows(
        self,
        events: Sequence[P2PEvent],
        *,
        rows_per_embed: int = MAX_ROWS_PER_EMBED,
    ) -> list[Embed]:
        if not 1 <= rows_per_embed <= self.MAX_ROWS_PER_EMBED:
            raise ValueError(
                f"rows_per_embed must be between 1 and "
                f"{self.MAX_ROWS_PER_EMBED}"
            )

        ordered = sorted(
            events,
            key=lambda event: event.time,
            reverse=True,
        )

        if not ordered:
            return [
                Embed(
                    title=self._t("embed.rows.title"),
                    description=self._t("embed.rows.empty"),
                    color=Color.blurple(),
                )
            ]

        pages: list[Embed] = []

        for start in range(0, len(ordered), rows_per_embed):
            chunk = ordered[start : start + rows_per_embed]
            page_number = len(pages) + 1
            page_count = (
                len(ordered) + rows_per_embed - 1
            ) // rows_per_embed

            embed = Embed(
                title=self._t("embed.rows.title"),
                color=Color.blurple(),
                timestamp=chunk[0].time,
            )

            for event in chunk:
                name, value = self._build_row(event)
                embed.add_field(
                    name=name[:256],
                    value=value,
                    inline=False,
                )

            embed.set_footer(
                text=self._t(
                    "embed.rows.page",
                    page=page_number,
                    pages=page_count,
                    count=len(ordered),
                )
            )

            pages.append(embed)

        return pages
