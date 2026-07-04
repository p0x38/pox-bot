from importlib.metadata import version

from platformdirs import PlatformDirs

app_dir = PlatformDirs('pox-bot', 'p0x38', version('pox-bot'), ensure_exists=True)
