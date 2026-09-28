"""Port of tag.sh: move a version marker tag (e.g. 3.25-#a1b2c3d) to the head of a remote branch."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .config import MARKER_PATTERN, AppConfig, validate_marker, validate_remote, validate_template
from .git_runner import GitError, GitRunner, find_git

log = logging.getLogger("git_version_tagger.tagger")

HASH_PATTERN = "[0-9a-f]{4,64}"

# C0/C1 control characters except "\n", plus bidi marks and overrides: text from the repository (commit
# subjects, git's stderr) must not rewrite the terminal or reorder what the user reads.
_UNPRINTABLE = re.compile("[\x00-\x09\x0b-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]")


def printable(text: str, keep_newlines: bool = False) -> str:
    """`text` with control characters and bidi overrides replaced by "?"; newlines too unless kept."""
    cleaned = _UNPRINTABLE.sub("?", text)
    return cleaned if keep_newlines else cleaned.replace("\n", "?")


class TaggerError(RuntimeError):
    """A problem the user can fix (wrong folder, unknown branch, ...). The message is shown as-is."""


def tag_name(template: str, marker: str, short_hash: str) -> str:
    return template.replace("{marker}", marker).replace("{hash}", short_hash)


def marker_pattern(template: str, marker: str) -> re.Pattern[str]:
    """Regex for tags built from `template` for exactly this marker and any commit hash."""
    parts = re.split(r"(\{marker\}|\{hash\})", template)
    regex = "".join(
        re.escape(marker) if part == "{marker}" else HASH_PATTERN if part == "{hash}" else re.escape(part)
        for part in parts
    )
    return re.compile(regex)


def find_marker_tags(tags: list[str], template: str, marker: str) -> list[str]:
    pattern = marker_pattern(template, marker)
    return sorted(tag for tag in tags if pattern.fullmatch(tag))


def marker_capture_pattern(template: str) -> re.Pattern[str]:
    """Regex for tags built from `template` for any marker; the "marker" group holds the marker."""
    regex, seen_marker = "", False
    for part in re.split(r"(\{marker\}|\{hash\})", template):
        if part == "{marker}":  # a second {marker} must repeat the first one
            regex += "(?P=marker)" if seen_marker else f"(?P<marker>{MARKER_PATTERN})"
            seen_marker = True
        elif part == "{hash}":
            regex += HASH_PATTERN
        else:
            regex += re.escape(part)
    return re.compile(regex)


def markers_in_tags(tags: list[str], template: str) -> list[str]:
    """Distinct markers that have a tag in the `template` format, highest version first (3.25 before 3.9)."""
    pattern = marker_capture_pattern(template)
    found = {match.group("marker") for tag in tags if (match := pattern.fullmatch(tag))}
    return sorted((marker for marker in found if validate_marker(marker) is None), key=_version_key, reverse=True)


def _version_key(marker: str) -> list[str | int]:
    """'3.25' -> ['', 3, '.', 25, '']: numbers compare as numbers, so 3.25 sorts above 3.9."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", marker)]


@dataclass(frozen=True)
class TagPlan:
    """What Tagger.apply() will do; describe() is printed by the CLI and written to the log."""

    branch: str
    marker: str
    commit: str  # full sha of the remote branch head
    short_hash: str
    subject: str  # commit subject line, shown to the user
    new_tag: str
    old_tags: tuple[str, ...]  # tags of this marker to delete; never contains new_tag
    already_tagged: bool  # new_tag already exists on the remote

    @property
    def up_to_date(self) -> bool:
        return self.already_tagged and not self.old_tags

    def describe(self) -> str:
        lines = [f"{self.branch} is at {self.short_hash}: {self.subject}", ""]
        lines += [f"• delete {tag} (remote and local)" for tag in self.old_tags]
        if not self.already_tagged:
            lines.append(f"• create {self.new_tag} and push it to the remote")
        return "\n".join(lines)


class Tagger:
    """Runs the tag.sh workflow against one repository. Never touches the working tree."""

    def __init__(self, runner: GitRunner, config: AppConfig) -> None:
        self.git = runner
        self.cfg = config

    def check_repo(self) -> None:
        """Fail early with a message the user understands, before anything else runs."""
        path = self.cfg.project_path.strip()
        if not path:
            raise TaggerError("Project folder is not set - open Settings")
        if error := validate_remote(self.cfg.remote):
            raise TaggerError(error)
        try:
            inside = self.git.run("rev-parse", "--is-inside-work-tree")
        except GitError as exc:
            raise TaggerError(f"{path} is not a git repository: {exc.stderr}") from exc
        if inside != "true":
            raise TaggerError(f"{path} is not a git repository with a working tree")
        if self.cfg.remote not in self.git.run("remote").split():
            raise TaggerError(f"Remote {self.cfg.remote!r} is not configured in {path}")

    def sync_tags(self) -> None:
        """Make local tags an exact copy of the remote's (tag.sh deleted every local tag, then fetched)."""
        self.git.run("fetch", "--prune", "--prune-tags", "--force", self.cfg.remote)

    def local_tags(self) -> list[str]:
        return self.git.run("tag", "--list").splitlines()

    def current_versions(self) -> dict[str, list[str]]:
        tags = self.local_tags()
        return {marker: find_marker_tags(tags, self.cfg.tag_template, marker) for marker in self.cfg.markers}

    def refresh(self) -> dict[str, list[str]]:
        self.check_repo()
        self.sync_tags()
        return self.current_versions()

    def remote_branches(self) -> list[str]:
        self.check_repo()
        self.sync_tags()
        out = self.git.run("for-each-ref", "--format=%(refname:lstrip=3)", f"refs/remotes/{self.cfg.remote}")
        return sorted(name for name in out.splitlines() if name != "HEAD")

    def remote_markers(self) -> list[str]:
        """Markers of the remote's tags in the configured tag format (Settings → Import from remote)."""
        if error := validate_template(self.cfg.tag_template):
            raise TaggerError(error)
        self.check_repo()
        self.sync_tags()
        return markers_in_tags(self.local_tags(), self.cfg.tag_template)

    def remote_url(self) -> str:
        self.check_repo()
        return self.git.run("remote", "get-url", self.cfg.remote)

    def plan(self, branch: str, marker: str) -> TagPlan:
        if error := validate_template(self.cfg.tag_template):  # the CLI does not run validate_config
            raise TaggerError(error)
        self.check_repo()
        self.sync_tags()
        ref = f"refs/remotes/{self.cfg.remote}/{branch}"
        try:
            commit = self.git.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except GitError as exc:
            raise TaggerError(f"Branch {branch!r} not found on remote {self.cfg.remote!r}") from exc
        short_hash = self.git.run("rev-parse", "--short", commit)
        new_tag = tag_name(self.cfg.tag_template, marker, short_hash)
        try:
            self.git.run("check-ref-format", f"refs/tags/{new_tag}")
        except GitError as exc:
            raise TaggerError(f"{new_tag!r} is not a valid tag name - check the tag format in Settings") from exc
        existing = find_marker_tags(self.local_tags(), self.cfg.tag_template, marker)
        return TagPlan(
            branch=branch,
            marker=marker,
            commit=commit,
            short_hash=short_hash,
            subject=printable(self.git.run("log", "-1", "--format=%s", commit)),
            new_tag=new_tag,
            old_tags=tuple(tag for tag in existing if tag != new_tag),
            already_tagged=new_tag in existing,
        )

    def apply(self, plan: TagPlan) -> str:
        """Create plan.new_tag and delete plan.old_tags on the remote in one atomic push."""
        if plan.up_to_date:
            return plan.new_tag
        refspecs = [f":refs/tags/{tag}" for tag in plan.old_tags]
        if not plan.already_tagged:
            # A full ref name is never read as an option; "" = the tag must not exist yet (like `git tag`).
            self.git.run("update-ref", f"refs/tags/{plan.new_tag}", plan.commit, "")
            refspecs.insert(0, f"refs/tags/{plan.new_tag}")
        try:
            self._push(refspecs)
        except GitError:
            if not plan.already_tagged:
                self.git.run("update-ref", "-d", f"refs/tags/{plan.new_tag}")  # keep local tags equal to the remote
            raise
        for tag in plan.old_tags:
            self.git.run("update-ref", "-d", f"refs/tags/{tag}")
        log.info("Moved %s on %s to %s", plan.marker, plan.branch, plan.new_tag)
        return plan.new_tag

    def _push(self, refspecs: list[str]) -> None:
        try:
            self.git.run("push", "--atomic", self.cfg.remote, *refspecs)
        except GitError as exc:
            if "does not support --atomic" not in exc.stderr:
                raise
            log.warning("The remote does not support atomic push; pushing without it")
            self.git.run("push", self.cfg.remote, *refspecs)


def make_tagger(config: AppConfig) -> Tagger:
    return Tagger(GitRunner(config.project_path, find_git(config.git_executable)), config)
