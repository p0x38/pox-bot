from enum import Enum


class PlatformType(Enum):
    DISCORD = 'discord'
    MATRIX = 'matrix'


class ObjectType(Enum):
    USER = 'user'
    CHANNEL = 'channel'
    DM = 'dm'
    GROUP = 'private'
    GUILD = 'guild'
    UNKNOWN = 'unknown'
