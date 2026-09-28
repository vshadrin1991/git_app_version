import subprocess
from dataclasses import dataclass
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    """Run git in a test repository without GitRunner, so fixtures don't depend on the code under test."""
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@dataclass
class Repos:
    origin: Path  # bare "server" repository
    project: Path  # the user's clone the app works on
    other: Path  # a teammate's clone that pushes new commits and tags

    def remote_tags(self) -> list[str]:
        out = git(self.origin, "tag", "--list")
        return sorted(out.splitlines()) if out else []

    def commit_on(self, branch: str, message: str) -> str:
        """Push a new commit to origin/<branch> from the teammate clone and return its full sha."""
        git(self.other, "checkout", branch)
        git(self.other, "pull", "--ff-only")
        (self.other / "file.txt").write_text(message)
        git(self.other, "commit", "-am", message)
        git(self.other, "push", "origin", branch)
        return git(self.other, "rev-parse", "HEAD")


FAKE_GH_SCRIPT = r'''
"""Stand-in for the GitHub CLI. Appends its arguments to $FAKE_GH_LOG, then:
  auth status  waits $FAKE_GH_SECONDS, prints $FAKE_GH_STATUS (default: no accounts);
               with FAKE_GH_OLD=1, --json is an unknown flag (like old gh)
  auth login   prints the device-code prompt, then waits $FAKE_GH_SECONDS
  every call   prints $FAKE_GH_STDERR to stderr and exits with $FAKE_GH_EXIT (default 0)
"""
import os
import sys
import time

args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as calls:
    calls.write(" ".join(args) + "\n")
if args[:2] == ["auth", "status"]:
    if "--json" in args and os.environ.get("FAKE_GH_OLD"):
        print("unknown flag: --json", file=sys.stderr)
        sys.exit(1)
    time.sleep(float(os.environ.get("FAKE_GH_SECONDS", "0")))
    print(os.environ.get("FAKE_GH_STATUS", '{"hosts": {}}'))
if args[:2] == ["auth", "login"]:
    print("! First copy your one-time code: ABCD-1234", file=sys.stderr, flush=True)
    print("Open this URL to continue in your web browser: https://github.com/login/device", file=sys.stderr, flush=True)
    time.sleep(float(os.environ.get("FAKE_GH_SECONDS", "0")))
print(os.environ.get("FAKE_GH_STDERR", ""), file=sys.stderr, end="")
sys.exit(int(os.environ.get("FAKE_GH_EXIT", "0")))
'''


@dataclass
class FakeGh:
    path: Path  # the fake executable; its directory is first on PATH
    calls_file: Path

    def calls(self) -> list[str]:
        """Each gh invocation's arguments joined by spaces, oldest first."""
        return self.calls_file.read_text(encoding="utf-8").splitlines() if self.calls_file.exists() else []
