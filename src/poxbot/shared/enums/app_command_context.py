from enum import IntFlag


class AppCommandContextFlag(IntFlag):
    GUILDS = 0b001
    DM = 0b010
    PRIVATE = 0b100


class AppInstallationFlag(IntFlag):
    GUILD = 0b01
    USER = 0b10
