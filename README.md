# pox-bot

[![Crowdin Sync](https://github.com/p0x38/pox-bot/actions/workflows/crowdin.yml/badge.svg)](https://github.com/p0x38/pox-bot/actions/workflows/crowdin.yml)

> [!CAUTION]
> There is large files that may consume your disk space.

source for my bot called stupid bot

## System Requirements

### All platforms

- `Python 3.12`
- `uv`.
- [`dependencies.`](pyproject.toml)
- `PostgreSQL` (You can change it by manually modifying)
- `ffmpeg`

### ffmpeg

- Debian/Ubuntu/Linux Mint: use `sudo apt install ffmpeg`
- AlmaLinux/Rocky Linux: `sudo dnf install epel-release && sudo dnf install ffmpeg`
- Fedora: `sudo dnf install ffmpeg`
- Arch Linux: `sudo pacman -S ffmpeg`
- Windows: Download ffmpeg from [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/) and add it to PATH
- Source code: Download source code from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and compile it

### Linux

- `build-essential`, `python3-dev`, `pkg-config` and `libicu-dev` (tested on Ubuntu 22.04 LTS)

## Usage

Make sure to activate virtualenv first.

Make sure to add `TOKEN` on environment file (.env).

More `.env` related info: [here](.env-sample)

Run this command: `uv run main.py`

If you want to update the packages (dependencies, not my bot): `uv sync --upgrade`

> [!warning]
> I'm not responsive for messing the project up.

## Disclaimer

I do not own the images & contents which is in `resources` directory.

## Contribute

You can contribute to my project, but you do not need to contribute to my project.

## Copyright attribution

You can attribute my project into your other projects:

```plain
the bot uses pox-bot by NoteSwiper
```
