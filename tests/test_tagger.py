from pathlib import Path

import pytest

from git_version_tagger.config import AppConfig
from git_version_tagger.git_runner import GitError, GitRunner
from git_version_tagger.tagger import TagPlan, Tagger, TaggerError
from helpers import git


def test_first_release_creates_and_pushes_tag(repos, tagger):
    head = repos.commit_on("mkdev", "feature A")
    plan = tagger.plan("mkdev", "3.25")
    assert plan.commit == head
    assert plan.old_tags == ()
    assert tagger.apply(plan) == f"3.25-#{plan.short_hash}"
    assert repos.remote_tags() == [f"3.25-#{plan.short_hash}"]


def test_release_replaces_previous_marker_tag_only(repos, tagger):
    old = tagger.apply(tagger.plan("mkdev", "3.25"))
    other_marker = tagger.apply(tagger.plan("mkdev", "3.24"))
    repos.commit_on("mkdev", "feature B")
    plan = tagger.plan("mkdev", "3.25")
    assert plan.old_tags == (old,)
    new = tagger.apply(plan)
    assert new != old
    assert repos.remote_tags() == sorted([new, other_marker])
    assert old not in tagger.local_tags()


def test_marker_that_is_prefix_of_another_leaves_it_alone(repos, tagger):
    long_marker_tag = tagger.apply(tagger.plan("mkdev", "3.25"))
    repos.commit_on("mkdev", "next")
    tagger.apply(tagger.plan("mkdev", "3.2"))
    assert long_marker_tag in repos.remote_tags()


def test_plan_uses_remote_branch_head_not_local_checkout(repos, tagger):
    head = repos.commit_on("mkdev-rc", "rc fix")  # the project clone has not pulled this
    assert tagger.plan("mkdev-rc", "scp-1.55").commit == head


def test_working_copy_is_untouched(repos, tagger):
    (repos.project / "file.txt").write_text("uncommitted change")
    tagger.apply(tagger.plan("mkdev", "3.25"))
    assert git(repos.project, "branch", "--show-current") == "main"
    assert (repos.project / "file.txt").read_text() == "uncommitted change"


def test_sync_drops_stale_local_tags_and_picks_up_remote_ones(repos, tagger):
    git(repos.project, "tag", "local-only")
    git(repos.other, "tag", "3.24-#abcdef1")
    git(repos.other, "push", "origin", "3.24-#abcdef1")
    tagger.sync_tags()
    assert "local-only" not in tagger.local_tags()
    assert "3.24-#abcdef1" in tagger.local_tags()


def test_up_to_date_plan_is_a_no_op(repos, tagger):
    tag = tagger.apply(tagger.plan("mkdev", "3.25"))
    plan = tagger.plan("mkdev", "3.25")
    assert plan.up_to_date
    assert tagger.apply(plan) == tag
    assert repos.remote_tags() == [tag]


def test_duplicate_marker_tags_are_all_replaced(repos, tagger):
    git(repos.other, "tag", "3.25-#0000001")
    git(repos.other, "tag", "3.25-#0000002")
    git(repos.other, "push", "origin", "--tags")
    repos.commit_on("mkdev", "new")
    plan = tagger.plan("mkdev", "3.25")
    assert plan.old_tags == ("3.25-#0000001", "3.25-#0000002")
    new = tagger.apply(plan)
    assert repos.remote_tags() == [new]


def test_refresh_reports_current_tag_per_marker(repos, tagger):
    tag = tagger.apply(tagger.plan("mkdev", "3.25"))
    assert tagger.refresh() == {"3.25": [tag], "3.24": []}


def test_remote_branches(repos, tagger):
    assert tagger.remote_branches() == ["main", "mkdev", "mkdev-rc"]


def test_unknown_branch_raises_clear_error(repos, tagger):
    with pytest.raises(TaggerError, match="Branch 'release-9' not found on remote 'origin'"):
        tagger.plan("release-9", "3.25")
    assert repos.remote_tags() == []


def test_empty_project_path_is_rejected(config):
    config.project_path = ""
    with pytest.raises(TaggerError, match="Project folder is not set"):
        Tagger(GitRunner("."), config).plan("mkdev", "3.25")


def test_not_a_git_repository(tmp_path, config):
    plain = tmp_path / "plain"
    plain.mkdir()
    config.project_path = str(plain)
    with pytest.raises(TaggerError, match="not a git repository"):
        Tagger(GitRunner(plain), config).plan("mkdev", "3.25")


def test_missing_remote(config, tagger):
    config.remote = "upstream"
    with pytest.raises(TaggerError, match="Remote 'upstream' is not configured"):
        tagger.plan("mkdev", "3.25")


def test_push_failure_rolls_back_local_tag_and_keeps_remote_intact(repos, tagger):
    old = tagger.apply(tagger.plan("mkdev", "3.25"))
    repos.commit_on("mkdev", "next")
    plan = tagger.plan("mkdev", "3.25")
    git(repos.project, "remote", "set-url", "origin", str(repos.origin.parent / "gone.git"))
    with pytest.raises(GitError):
        tagger.apply(plan)
    assert tagger.local_tags() == [old]
    assert repos.remote_tags() == [old]


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> str:
        self.calls.append(args)
        if args[:2] == ("push", "--atomic"):
            raise GitError(list(args), 1, "fatal: the receiving end does not support --atomic push")
        return ""


def test_falls_back_to_plain_push_when_remote_lacks_atomic_support():
    runner = FakeRunner()
    plan = TagPlan(
        branch="mkdev",
        marker="3.25",
        commit="a1b2c3d" + "0" * 33,
        short_hash="a1b2c3d",
        subject="x",
        new_tag="3.25-#a1b2c3d",
        old_tags=("3.25-#0000fff",),
        already_tagged=False,
    )
    Tagger(runner, AppConfig(project_path="/p")).apply(plan)
    assert ("push", "origin", "refs/tags/3.25-#a1b2c3d", ":refs/tags/3.25-#0000fff") in runner.calls
    assert runner.calls[-1] == ("update-ref", "-d", "refs/tags/3.25-#0000fff")


def test_remote_markers_lists_markers_of_remote_tags_only(repos, tagger):
    for tag in ("3.25-#abcdef1", "scp-1.55-#abcdef2", "release-candidate"):
        git(repos.other, "tag", tag)
        git(repos.other, "push", "origin", tag)
    git(repos.project, "tag", "9.9-#abcdef3")  # local only: the fetch drops it
    assert tagger.remote_markers() == ["scp-1.55", "3.25"]


def test_remote_markers_rejects_a_template_without_placeholders(tagger):
    tagger.cfg.tag_template = "v{marker}"
    with pytest.raises(TaggerError, match="must contain"):
        tagger.remote_markers()


def test_remote_url_is_the_url_of_the_configured_remote(repos, tagger):
    assert Path(tagger.remote_url()).resolve() == repos.origin.resolve()


def test_commit_subject_cannot_carry_terminal_escapes(repos, tagger):
    repos.commit_on("mkdev", "Fix \x1b]0;PWNED\x07\x1b[2J")
    assert tagger.plan("mkdev", "3.25").subject == "Fix ?]0;PWNED??[2J"


def test_plan_refuses_a_template_that_looks_like_an_option(repos, tagger):
    tagger.cfg.tag_template = "-F/etc/passwd{marker}{hash}"
    with pytest.raises(TaggerError, match="must not start with '-'"):
        tagger.plan("mkdev", "3.25")
    assert repos.remote_tags() == []


def test_remote_that_looks_like_an_option_is_refused(tagger):
    tagger.cfg.remote = "--upload-pack=touch /tmp/pwned"
    with pytest.raises(TaggerError, match="Invalid remote name"):
        tagger.check_repo()


def test_existing_local_tag_with_the_new_name_is_kept(repos, tagger):
    plan = tagger.plan("mkdev", "3.25")
    git(repos.project, "tag", plan.new_tag, plan.commit)  # appears between plan and apply
    with pytest.raises(GitError, match="already exists"):
        tagger.apply(plan)
    assert plan.new_tag in tagger.local_tags()  # not deleted by a rollback
    assert repos.remote_tags() == []  # nothing was pushed
