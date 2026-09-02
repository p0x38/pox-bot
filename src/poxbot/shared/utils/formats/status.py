from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ClientStatus, Locale, Status

if TYPE_CHECKING:
    from ....application.bot import PoxBot


def format_status(bot: PoxBot, client_status: ClientStatus, locale: Locale | str):
    result = ''
    if isinstance(client_status.status, Status):
        status = client_status.status

        if status == Status.do_not_disturb:
            result = bot.internal_translator.T('text.status.dnd', locale)
        else:
            result = bot.internal_translator.T(f'text.status.{status.name}', locale)
    elif isinstance(client_status.status, str):
        result = client_status.status
    elif client_status.raw_status.strip() is not None:
        result = client_status.raw_status

    platforms = []

    if client_status.mobile is str:
        platforms.append(bot.internal_translator.T('text.device.mobile', locale))
    if client_status.desktop is str:
        platforms.append(bot.internal_translator.T('text.device.desktop', locale))
    if client_status.web is str:
        platforms.append(bot.internal_translator.T('text.device.website', locale))

    if platforms:
        result = result + f' ({", ".join(platforms)})'

    return result
