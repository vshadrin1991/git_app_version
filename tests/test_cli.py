import builtins

import pytest

from git_version_tagger import cli
from git_version_tagger.cli import main
from git_version_tagger.config import AppConfig, BranchVersion, save_config
from git_version_tagger.git_runner import GitError


@pytest.fixture
def config_file(tmp_path, config):
    path = tmp_path / "config.json"
    save_config(config, path)
    return path


@pytest.fixture
def two_versions_file(tmp_path, config):
    """trunk → 3.25 and trunk → alt-1.55, trunk-rc → 3.24."""
    config.branch_versions.append(BranchVersion("trunk", "alt-1.55"))
    path = tmp_path / "config.json"
    save_config(config, path)
    return path


def test_tag_creates_and_pushes_the_tag_without_asking(config_file, repos, capsys, monkeypatch):
    def no_prompt(prompt=""):
        raise AssertionError("tag must not ask for confirmation")

    monkeypatch.setattr(builtins, "input", no_prompt)
    assert main(["--config", str(config_file), "tag", "trunk", "3.25"]) == 0
    [tag] = repos.remote_tags()
    assert tag.startswith("3.25-#")
    assert f"Created {tag}" in capsys.readouterr().out


def test_dry_run_changes_nothing(config_file, repos, capsys):
    assert main(["--config", str(config_file), "tag", "trunk", "3.25", "--dry-run"]) == 0
    assert repos.remote_tags() == []
    assert "create 3.25-#" in capsys.readouterr().out


def test_tag_uses_the_branch_version_from_settings(config_file, repos, capsys):
    assert main(["--config", str(config_file), "tag", "trunk"]) == 0
    [tag] = repos.remote_tags()
    assert tag.startswith("3.25-#")


def test_tag_refuses_another_version_for_a_configured_branch(config_file, repos, capsys):
    assert main(["--config", str(config_file), "tag", "trunk", "3.24"]) == 2
    assert "trunk is tagged with 3.25 (Settings); change it there to tag 3.24" in capsys.readouterr().err
    assert repos.remote_tags() == []


def test_unconfigured_branch_needs_a_version(config_file, capsys):
    assert main(["--config", str(config_file), "tag", "feature-x"]) == 2
    assert "feature-x has no version in Settings" in capsys.readouterr().err


def test_list_prints_every_branch_with_its_version_and_tag(config_file, repos, capsys):
    main(["--config", str(config_file), "tag", "trunk"])
    capsys.readouterr()
    assert main(["--config", str(config_file), "list"]) == 0
    out = capsys.readouterr().out
    assert f"trunk -> 3.25: {repos.remote_tags()[0]}" in out
    assert "trunk-rc -> 3.24: -" in out


def test_invalid_marker_is_rejected(config_file, repos, capsys):
    assert main(["--config", str(config_file), "tag", "trunk", "3 25"]) == 2
    assert "Invalid marker" in capsys.readouterr().err


def test_errors_are_reported_without_traceback(tmp_path, capsys):
    path = tmp_path / "config.json"
    save_config(
        AppConfig(project_path=str(tmp_path / "missing"), branch_versions=[BranchVersion("trunk", "3.25")]), path
    )
    assert main(["--config", str(path), "tag", "trunk", "3.25"]) == 1
    assert "error:" in capsys.readouterr().err


def test_cli_output_has_no_terminal_escapes(config_file, repos, capsys):
    repos.commit_on("trunk", "Fix \x1b[2J")
    assert main(["--config", str(config_file), "tag", "trunk", "--dry-run"]) == 0
    captured = capsys.readouterr()
    assert "\x1b" not in captured.out + captured.err


def test_cli_errors_have_no_terminal_escapes(config_file, capsys, monkeypatch):
    class Broken:
        def plan(self, branch, marker):
            raise GitError(["fetch"], 128, "remote: \x1b]0;PWNED\x07 denied\nfatal: nope")

    monkeypatch.setattr(cli, "make_tagger", lambda config: Broken())
    assert main(["--config", str(config_file), "tag", "trunk"]) == 1
    err = capsys.readouterr().err
    assert "\x1b" not in err
    assert "?]0;PWNED? denied\nfatal: nope" in err


def test_tag_each_version_of_a_branch(two_versions_file, repos):
    assert main(["--config", str(two_versions_file), "tag", "trunk", "3.25"]) == 0
    assert main(["--config", str(two_versions_file), "tag", "trunk", "alt-1.55"]) == 0
    tags = repos.remote_tags()
    assert [tag.split("-#")[0] for tag in tags] == ["3.25", "alt-1.55"]  # the second did not delete the first
    assert len({tag.split("-#")[1] for tag in tags}) == 1  # both mark the head of trunk


def test_tag_without_a_version_refuses_a_branch_with_several(two_versions_file, repos, capsys):
    assert main(["--config", str(two_versions_file), "tag", "trunk"]) == 2
    assert "trunk has versions 3.25, alt-1.55 in Settings; give one: tag trunk 3.25" in capsys.readouterr().err
    assert repos.remote_tags() == []


def test_tag_refuses_a_version_the_branch_does_not_have(two_versions_file, repos, capsys):
    assert main(["--config", str(two_versions_file), "tag", "trunk", "3.24"]) == 2
    assert "trunk is tagged with 3.25, alt-1.55 (Settings); change it there to tag 3.24" in capsys.readouterr().err
    assert repos.remote_tags() == []


def test_list_prints_every_version_of_a_branch(two_versions_file, repos, capsys):
    assert main(["--config", str(two_versions_file), "list"]) == 0
    out = capsys.readouterr().out
    assert "trunk -> 3.25: -" in out
    assert "trunk -> alt-1.55: -" in out
