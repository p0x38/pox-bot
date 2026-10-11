from platformdirs import PlatformDirs

app_dir = PlatformDirs(
    'pox-bot',
    'p0x38',
    ensure_exists=True,
)
