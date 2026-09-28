"""Command line: `git-version-tagger tag trunk 3.25` does what `tag.sh trunk 3.25` did."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .config import AppConfig, default_config_path, load_config, validate_branch, validate_marker
from .git_runner import GitError
from .tagger import TaggerError, make_tagger, printable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-version-tagger",
        description="Move version tags like 3.25-#<hash> to the head of a remote branch.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, default=None, help="config file (default: the app's config)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="start the menu bar app (the default)")
    tag = sub.add_parser("tag", help="move BRANCH's version tag to the head of BRANCH")
    tag.add_argument("branch")
    tag.add_argument("marker", nargs="?", help="the version; may be left out when the branch has one version in Settings")
    tag.add_argument("--dry-run", action="store_true", help="show what would change and stop")
    sub.add_parser("list", help="print every branch with its version and current tag")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in (None, "gui"):
        from .app import run_gui  # Qt is only loaded for the GUI

        return run_gui(args.config)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("git_version_tagger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        config = load_config(args.config or default_config_path())
        if args.command == "tag":
            return _tag(config, args)
        return _list(config)
    except (TaggerError, GitError) as exc:
        print(f"error: {printable(str(exc), keep_newlines=True)}", file=sys.stderr)
        return 1
    finally:
        logger.removeHandler(handler)


def _tag(config: AppConfig, args: argparse.Namespace) -> int:
    configured = config.versions_of(args.branch)
    if not args.marker and len(configured) > 1:
        print(
            f"error: {args.branch} has versions {', '.join(configured)} in Settings; "
            f"give one: tag {args.branch} {configured[0]}",
            file=sys.stderr,
        )
        return 2
    marker = args.marker or next(iter(configured), "")
    if not marker:
        print(f"error: {args.branch} has no version in Settings; give one: tag {args.branch} 3.26", file=sys.stderr)
        return 2
    for problem in (validate_branch(args.branch), validate_marker(marker)):
        if problem:
            print(f"error: {problem}", file=sys.stderr)
            return 2
    if configured and marker not in configured:
        print(
            f"error: {args.branch} is tagged with {', '.join(configured)} (Settings); change it there to tag {marker}",
            file=sys.stderr,
        )
        return 2
    tagger = make_tagger(config)
    plan = tagger.plan(args.branch, marker)
    print(plan.describe())
    if plan.up_to_date:
        print(f"{plan.new_tag} already marks the head of {plan.branch}; nothing to do.")
        return 0
    if args.dry_run:
        print("Dry run: nothing was changed.")
        return 0
    print(f"Created {tagger.apply(plan)}")
    return 0


def _list(config: AppConfig) -> int:
    versions = make_tagger(config).refresh()
    for item in config.branch_versions:
        tags = versions.get(item.marker) or []
        print(f"{item.branch} -> {item.marker or '(no version)'}: {', '.join(tags) or '-'}")
    return 0
