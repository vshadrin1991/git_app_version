"""Settings: which repository, and the one version every branch is tagged with."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from platformdirs import user_config_dir

log = logging.getLogger("git_version_tagger.config")

CONFIG_VERSION = 2
DEFAULT_TEMPLATE = "{marker}-#{hash}"

MARKER_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]*"  # also used by tagger.markers_in_tags
_MARKER_RE = re.compile(MARKER_PATTERN)
_BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


@dataclass
class BranchVersion:
    """A branch and the one version it is tagged with (mkdev → 3.26)."""

    branch: str
    marker: str = ""  # "" until chosen in Settings


@dataclass
class AppConfig:
    project_path: str = ""
    remote: str = "origin"
    git_executable: str = ""  # empty = auto-detect (git_runner.find_git)
    tag_template: str = DEFAULT_TEMPLATE
    branch_versions: list[BranchVersion] = field(default_factory=list)
    launch_at_login: bool = False

    @property
    def branches(self) -> list[str]:
        return [item.branch for item in self.branch_versions]

    @property
    def markers(self) -> list[str]:
        """The versions in use, in branch order; each belongs to exactly one branch."""
        return [item.marker for item in self.branch_versions if item.marker]

    def version_of(self, branch: str) -> str | None:
        """The branch's version; "" when it has none yet, None when the branch is not configured."""
        return next((item.marker for item in self.branch_versions if item.branch == branch), None)


def default_config_path() -> Path:
    return Path(user_config_dir("git-version-tagger")) / "config.json"


def load_config(path: Path) -> AppConfig:
    """Read the config. A missing file gives defaults; a broken one is moved aside to *.bak.

    A version 1 file (separate marker and branch lists) is upgraded in memory and kept as *.v1.
    """
    if not path.exists():
        return AppConfig()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("top level must be a JSON object")
        if "branch_versions" not in data and "branches" in data:
            data = _upgrade_v1(data)
            backup = path.with_name(path.name + ".v1")
            if not backup.exists():
                backup.write_text(text, encoding="utf-8")
        known = {f.name for f in fields(AppConfig)}
        values = {key: value for key, value in data.items() if key in known}
        pairs = values.get("branch_versions", [])
        if not isinstance(pairs, list):
            raise ValueError("branch_versions must be a list")
        values["branch_versions"] = [_branch_version(item) for item in pairs]
        config = AppConfig(**values)
        _check_types(config)
        return config
    except ValueError as exc:
        backup = path.with_name(path.name + ".bak")
        path.replace(backup)
        log.warning("Config %s is invalid (%s); moved it to %s and started with defaults", path, exc, backup)
        return AppConfig()


def _upgrade_v1(data: dict) -> dict:
    """Version 1 kept two unrelated lists, markers and branches. Their order does not say which version
    belongs to which branch, so every branch starts without one and Settings asks for it."""
    branches = data["branches"]
    if not isinstance(branches, list) or not all(isinstance(branch, str) for branch in branches):
        raise ValueError("branches must be a list of strings")
    log.warning("Upgraded the config from version 1: choose the version of each branch in Settings")
    return {**data, "branch_versions": [{"branch": branch, "marker": ""} for branch in branches]}


def _branch_version(item: object) -> BranchVersion:
    if (
        not isinstance(item, dict)
        or not isinstance(item.get("branch"), str)
        or not isinstance(item.get("marker", ""), str)
    ):
        raise ValueError('branch_versions must be a list of {"branch": "...", "marker": "..."}')
    return BranchVersion(item["branch"], item.get("marker", ""))


def _check_types(config: AppConfig) -> None:
    for name in ("project_path", "remote", "git_executable", "tag_template"):
        if not isinstance(getattr(config, name), str):
            raise ValueError(f"{name} must be a string")
    if not isinstance(config.launch_at_login, bool):
        raise ValueError("launch_at_login must be true or false")


def save_config(config: AppConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"version": CONFIG_VERSION, **asdict(config)}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)  # atomic: a crash never leaves a half-written config


def validate_marker(value: str) -> str | None:
    """Return an error message, or None when the marker can be part of a tag name."""
    if not _MARKER_RE.fullmatch(value) or ".." in value:
        return f"Invalid marker {value!r}: use letters, digits, '.', '_' or '-' (e.g. 3.25, scp-1.55)"
    return None


def validate_branch(value: str) -> str | None:
    if (
        not _BRANCH_RE.fullmatch(value)
        or ".." in value
        or "//" in value
        or "/." in value
        or value.endswith(("/", ".", ".lock"))
    ):
        return f"Invalid branch name {value!r}"
    return None


def validate_template(value: str) -> str | None:
    if "{marker}" not in value or "{hash}" not in value:
        return "Tag template must contain {marker} and {hash}"
    if value.startswith("-"):  # git would read the tag name as an option (e.g. -F<file>)
        return "Tag template must not start with '-'"
    return None


def validate_remote(value: str) -> str | None:
    """A remote name git cannot mistake for an option (it is passed to fetch and push as is)."""
    if not value.strip():
        return "Remote name is empty"
    if value.startswith("-") or any(char.isspace() or not char.isprintable() for char in value):
        return f"Invalid remote name {value!r}"
    return None


def validate_config(config: AppConfig) -> list[str]:
    problems: list[str] = []
    if not config.project_path.strip():
        problems.append("Choose the project folder in Settings")
    if error := validate_remote(config.remote):
        problems.append(error)
    if error := validate_template(config.tag_template):
        problems.append(error)
    if not config.branch_versions:
        problems.append("Add at least one branch in Settings")
    for item in config.branch_versions:
        if error := validate_branch(item.branch):
            problems.append(error)
        if not item.marker:
            problems.append(f"Choose the version for {item.branch} in Settings")
        elif error := validate_marker(item.marker):
            problems.append(error)
    problems += [f"Duplicate branch {branch!r}" for branch in _duplicates(config.branches)]
    problems += [f"Version {marker!r} is set on more than one branch" for marker in _duplicates(config.markers)]
    return problems


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def next_version(marker: str) -> str | None:
    """The version after `marker`: its last number plus one, zero padding kept.

    3.25 → 3.26, 3.9 → 3.10, scp-1.55 → scp-1.56, 3.0-react → 3.1-react, 1.09 → 1.10; None without a number.
    """
    numbers = list(re.finditer(r"\d+", marker))
    if not numbers:
        return None
    last = numbers[-1]
    bumped = str(int(last.group()) + 1).zfill(len(last.group()))
    return marker[: last.start()] + bumped + marker[last.end() :]
