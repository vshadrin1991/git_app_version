"""GitHub login through the GitHub CLI (gh). Like git_runner: gh never prompts here and every call is logged."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit

from .git_runner import GitError, GitRunner

log = logging.getLogger("git_version_tagger.github")

DEFAULT_HOST = "github.com"
GH_TIMEOUT = 30.0
# Same reason as git_runner.GIT_CANDIDATES: GUI apps on macOS start with PATH=/usr/bin:/bin:/usr/sbin:/sbin.
GH_CANDIDATES = ("/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh", "/snap/bin/gh")
INSTALL_HINT = "Install the GitHub CLI (macOS: brew install gh; Ubuntu: see https://cli.github.com), then click Check again."

_LOGGED_IN_TEXT = re.compile(r"Logged in to (?P<host>\S+) (?:account|as) (?P<login>[A-Za-z0-9-]+)")
_SCP_LIKE_URL = re.compile(r"(?:[^@/]+@)?(?P<host>[^:/]+):(?!//)")  # git@github.com:acme/app.git
_DEVICE_CODE = re.compile(r"one-time code: (?P<code>[A-Z0-9]{4}-[A-Z0-9]{4})")
_URL = re.compile(r"https?://\S+(?=\s)")  # only a complete URL: output arrives in chunks


class GhError(RuntimeError):
    """gh could not be run or answered something unexpected. The message is shown as-is."""


@dataclass(frozen=True)
class AuthStatus:
    host: str
    login: str | None = None  # the active account; None when nobody is logged in to host
    problem: str | None = None  # set when gh knows the account but its token does not work

    @property
    def logged_in(self) -> bool:
        return self.login is not None and self.problem is None

    def describe(self) -> str:
        if self.login is None:
            return f"Not logged in to {ascii_host(self.host)}"
        if self.problem:
            return (
                f"The login to {ascii_host(self.host)} as {self.login} does not work ({self.problem})"
                " - log in again"
            )
        return f"Logged in to {ascii_host(self.host)} as {self.login}"


@dataclass(frozen=True)
class RemoteUrl:
    host: str
    ssh: bool  # git talks SSH to this remote, so it uses SSH keys, not the gh login


@dataclass(frozen=True)
class DevicePrompt:
    code: str  # the one-time code the user enters on the device page, e.g. ABCD-1234
    url: str  # the device page, e.g. https://github.com/login/device


def find_gh() -> str | None:
    found = shutil.which("gh")
    if found:
        return found
    for candidate in GH_CANDIDATES:
        if os.access(candidate, os.X_OK):
            return candidate
    return None


def ascii_host(host: str) -> str:
    """The host as it really is: a lookalike such as gіthub.com (Cyrillic і) becomes xn--gthub-n2e.com."""
    try:
        return host.lower().encode("idna").decode("ascii")
    except UnicodeError:
        return host.lower()


def is_device_page_of(url: str, host: str) -> bool:
    """True only for an https page on `host` itself: the one kind of page the login window may open.

    gh prints the device page the server gave it, so for any host but github.com the server picks it.
    """
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.hostname) and ascii_host(parts.hostname) == ascii_host(host)


def gh_environment() -> dict[str, str]:
    """gh runs without a terminal: no prompts, no colors, no update notices."""
    return {**os.environ, "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1", "GH_NO_UPDATE_NOTIFIER": "1"}


def run_gh(gh: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run `gh <args>`; the caller checks returncode. Raises GhError when gh cannot run or hangs."""
    log.info("$ gh %s", " ".join(args))
    try:
        return subprocess.run(
            [gh, *args],
            env=gh_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT,
        )
    except OSError as exc:
        raise GhError(f"cannot run {gh!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GhError(f"gh {' '.join(args)} timed out after {GH_TIMEOUT:g}s") from exc


def auth_status(gh: str, host: str) -> AuthStatus:
    proc = run_gh(gh, "auth", "status", "--hostname", host, "--json", "hosts")
    if proc.returncode == 0:  # with --json gh exits 0 even when the login is broken
        return parse_status(proc.stdout, host)
    if "unknown flag: --json" in proc.stderr:  # older gh, e.g. the one packaged by Ubuntu
        proc = run_gh(gh, "auth", "status", "--hostname", host)
        return parse_status_text(proc.stdout + proc.stderr, host, proc.returncode)
    raise GhError(f"gh auth status failed: {proc.stderr.strip() or f'exit code {proc.returncode}'}")


def parse_status(output: str, host: str) -> AuthStatus:
    """Read `gh auth status --json hosts`: {"hosts": {"github.com": [{"login", "active", "state"}, ...]}}."""
    try:
        accounts = json.loads(output)["hosts"].get(host, [])
        active = next((account for account in accounts if account["active"]), None)
        if active is None:
            return AuthStatus(host)
        state = active["state"]
        return AuthStatus(host, login=active["login"], problem=None if state == "success" else state)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise GhError(f"Unexpected output from gh auth status: {output.strip()[:200]!r}") from exc


def parse_status_text(output: str, host: str, returncode: int) -> AuthStatus:
    """Read the text of `gh auth status` from gh without --json: '✓ Logged in to github.com as octocat (...)'."""
    match = next((m for m in _LOGGED_IN_TEXT.finditer(output) if m.group("host") == host), None)
    if match is None:
        return AuthStatus(host)
    return AuthStatus(host, login=match.group("login"), problem=None if returncode == 0 else "error")


def parse_remote_url(url: str) -> RemoteUrl | None:
    """Host of a git remote URL; None for local paths and file:// remotes (then the app offers github.com)."""
    url = url.strip()
    if "://" in url:
        parts = urlsplit(url)
        if parts.scheme in ("http", "https", "ssh", "git+ssh") and parts.hostname:
            return RemoteUrl(parts.hostname, ssh=parts.scheme in ("ssh", "git+ssh"))
        return None
    if match := _SCP_LIKE_URL.match(url):
        return RemoteUrl(match.group("host").lower(), ssh=True)
    return None


def login_arguments(host: str) -> list[str]:
    """`gh auth login` without a terminal: the browser (device code) flow, where gh prints the code and URL.

    No --git-protocol: it would change the protocol gh uses for every repository on this host.
    """
    return ["auth", "login", "--hostname", host, "--web"]


def parse_device_prompt(output: str, host: str) -> DevicePrompt | None:
    """The one-time code (and URL) from `gh auth login --web` output; None until gh has printed the code."""
    code = _DEVICE_CODE.search(output)
    if code is None:
        return None
    url = _URL.search(output, code.end())
    return DevicePrompt(code.group("code"), url.group(0) if url else f"https://{host}/login/device")


def setup_git(gh: str, host: str) -> None:
    """Make git ask gh for https://<host> credentials (gh writes credential.https://<host>.helper to ~/.gitconfig)."""
    proc = run_gh(gh, "auth", "setup-git", "--hostname", host)
    if proc.returncode != 0:
        raise GhError(f"gh auth setup-git failed: {proc.stderr.strip() or f'exit code {proc.returncode}'}")


def git_uses_gh(runner: GitRunner, host: str) -> bool:
    """True when `gh auth setup-git` has run for host, so git fetch/push use the gh login."""
    try:
        helpers = runner.run("config", "--get-all", f"credential.https://{host}.helper")
    except GitError:
        return False  # exit code 1: no credential helper for this host
    return "auth git-credential" in helpers


# What git prints when an HTTPS remote wants credentials it cannot get without a prompt (lowercase).
_CREDENTIAL_FAILURES = (
    "terminal prompts disabled",
    "could not read username",
    "authentication failed",
    "invalid username or password",
    "invalid username or token",
    "the requested url returned error: 403",
)
LOGIN_HINT = "The remote wants a GitHub login: open Settings → General → GitHub account and log in."


def explain_error(exc: Exception) -> str:
    """The error text, plus where to log in when git failed because the remote asked for credentials."""
    message = str(exc)
    if any(failure in message.lower() for failure in _CREDENTIAL_FAILURES):
        return f"{message}\n\n{LOGIN_HINT}"
    return message
