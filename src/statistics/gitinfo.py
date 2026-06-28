import asyncio

from src.logger_factory.logger import setup_logger

logger = setup_logger(__name__)


class GitInfo:
    def __init__(self):
        self.loaded: bool = False
        self.commit_message: str | None = None
        self.commit_hash: str | None = None
        self.short_hash: str | None = None
        self.branch_name: str | None = None

    async def _run_git(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip())

        return stdout.decode("utf-8", "replace").strip()

    async def load(self):
        if self.loaded:
            return

        try:
            log_data, branch_name = await asyncio.gather(
                self._run_git("log", "-1", "--pretty=%H%n%h%n%s"),
                self._run_git("rev-parse", "--abbrev-ref", "HEAD"),
            )

            self.commit_hash, self.short_hash, self.commit_message = (
                log_data.split("\n", 2)
            )
            self.branch_name = branch_name
            self.loaded = True
        except FileNotFoundError:
            logger.error("Git command not found")
