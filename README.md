# pox-bot

source for my bot called stupid bot

## READ THIS before installing

Please note that depending on the following optional dependencies, this program—or the libraries it uses—may consume a significant amount of disk space:

- "cpu" and "gpu" ([PyTorch])
- "piper" ([Piper TTS])
- "ai" ([Ollama], [LM Studio], etc.)

Also, the project usually uses AI since around July 2026, so do NOT scrape the project for training an AI model.

## System Requirements

### All platforms

- [Python] (>=3.12,<3.14)
- [uv]
- [ffmpeg] (Optional now)
- SQL engines that [SQLAlchemy] supports (currently [PostgreSQL] is most compatible with the project)

All of the dependencies listed in [this file](pyproject.toml).

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

It is heavily RECOMMENDED to use venv for the project.

1. Install [Git] and [uv] if you don't have them
2. Clone this repository: `git clone https://github.com/p0x38/pox-bot.git`
3. Install dependencies: `uv sync --extra cpu --extra piper --extra ai --extra minecraft --extra audio` (You must not to exclude the `--extra` stuffs unless you don't really need, I haven't not yet fix the code to make the program work without them)
4. Copy [.sample.env](.sample.env) into any file that contains `.env` and edit it with any program (Recommended: `.env`)
5. Run the program using: `uv run poxbot run` or `poxbot run` if you have activated the venv stuff
6. Maybe that's it

If you want to update the packages (dependencies, not my bot): `uv sync --upgrade`

I'm not really responsive for messing the code up badly.

## Copyright

I do not own the images & contents which are in `/src/poxbot/assets` directory, and their copyrights belong to the original creator, or the subject.

You can add a copyright into your own project:

```plain
"pox-bot" by @p0x38
```

You can use Markdown version too:

```markdown
[pox-bot](https://github.com/p0x38/pox-bot) by [@p0x38](https://github.com/p0x38)
```

## Contributing to the project

You can check the guide for contributing to the project from [/docs/contributing/](/docs/contributing/) or [CONTRIBUTING.md](CONTRIBUTING.md).

[PyTorch]: https://pytorch.org/
[Piper TTS]: https://github.com/OHF-Voice/piper1-gpl
[Ollama]: https://ollama.com/
[LM Studio]: https://lmstudio.ai/
[Python]: https://www.python.org/
[uv]: https://docs.astral.sh/uv/
[ffmpeg]: https://www.ffmpeg.org/
[SQLAlchemy]: https://www.sqlalchemy.org/
[PostgreSQL]: https://www.postgresql.org/
[Git]: https://git-scm.com/