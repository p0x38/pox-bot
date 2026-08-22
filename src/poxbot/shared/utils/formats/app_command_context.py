
from discord import app_commands

from ...enums import AppCommandContextFlag, AppInstallationFlag


def context_to_intflag(
    context: app_commands.AppCommandContext,
) -> AppCommandContextFlag:
    flags = AppCommandContextFlag(0)

    if context.guild:
        flags |= AppCommandContextFlag.GUILDS
    if context.dm_channel:
        flags |= AppCommandContextFlag.DM
    if context.private_channel:
        flags |= AppCommandContextFlag.PRIVATE

    return flags


def installation_type_to_intflag(
    installation_type: app_commands.AppInstallationType,
) -> AppInstallationFlag:
    flags = AppInstallationFlag(0)
    
    if installation_type.guild:
        flags |= AppInstallationFlag.GUILD
    if installation_type.user:
        flags |= AppInstallationFlag.USER
    
    return flags
