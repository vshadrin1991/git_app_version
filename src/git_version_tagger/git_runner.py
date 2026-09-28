"""The only place that runs git. Every call is logged, never prompts, and times out."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("git_version_tagger.git")

DEFAULT_TIMEOUT = 120.0
# GUI apps on macOS start with PATH=/usr/bin:/bin:/usr/sbin:/sbin, so Homebrew git is not on it.
GIT_CANDIDATES = ("/opt/homebrew/bin/git", "/usr/local/bin/git", "/usr/bin/git")


class GitError(RuntimeError):
    def __init__(self, command: list[str], returncode: int | None, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(f"git {' '.join(command)} failed: {self.stderr or f'exit code {returncode}'}")


class GitRunner:
    def __init__(self, repo: str | Path, git: str = "git", timeout: float = DEFAULT_TIMEOUT) -> None:
        self.repo = Path(repo)
        self.git = git
        self.timeout = timeout

    def run(self, *args: str) -> str:
        """Run `git <args>` in the repository; return stripped stdout or raise GitError."""
        command = list(args)
        log.info("$ git %s", " ".join(command))
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
        try:
            proc = subprocess.run(
                [self.git, *command],
                cwd=self.repo,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except OSError as exc:
            raise GitError(command, None, f"cannot run {self.git!r} in {self.repo}: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(command, None, f"timed out after {self.timeout:g}s") from exc
        if proc.returncode != 0:
            raise GitError(command, proc.returncode, proc.stderr)
        return proc.stdout.strip()


def find_git(configured: str = "") -> str:
    if configured:
        return configured
    found = shutil.which("git")
    if found:
        return found
    for candidate in GIT_CANDIDATES:
        if os.access(candidate, os.X_OK):
            return candidate
    return "git"
