import json

import pytest

from git_version_tagger.config import (
    AppConfig,
    BranchVersion,
    load_config,
    next_version,
    save_config,
    validate_branch,
    validate_config,
    validate_marker,
    validate_remote,
    validate_template,
)


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "missing.json") == AppConfig()


PAIRS = [BranchVersion("trunk", "3.26"), BranchVersion("trunk-rc", "3.25")]


def test_save_then_load_round_trips(tmp_path):
    config = AppConfig(project_path="/Users/me/Projects/my_project", branch_versions=PAIRS, launch_at_login=True)
    path = tmp_path / "nested" / "config.json"
    save_config(config, path)
    assert load_config(path) == config
    saved = json.loads(path.read_text())
    assert saved["version"] == 2
    assert saved["branch_versions"] == [{"branch": "trunk", "marker": "3.26"}, {"branch": "trunk-rc", "marker": "3.25"}]
    assert "markers" not in saved and "branches" not in saved


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"version": 2, "branch_versions": [{"branch": "trunk", "marker": "3.26"}], "added_in_v3": 1}))
    assert load_config(path) == AppConfig(branch_versions=[BranchVersion("trunk", "3.26")])


def test_version_1_config_keeps_branches_and_asks_for_versions(tmp_path):
    v1 = {
        "version": 1,
        "project_path": "/p",
        "remote": "origin",
        "git_executable": "",
        "tag_template": "{marker}-#{hash}",
        "markers": ["3.24", "3.25", "3.0-react"],
        "branches": ["trunk", "trunk-rc", "trunk-react"],
        "launch_at_login": True,
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(v1))
    config = load_config(path)
    assert config == AppConfig(
        project_path="/p",
        branch_versions=[BranchVersion("trunk"), BranchVersion("trunk-rc"), BranchVersion("trunk-react")],
        launch_at_login=True,
    )
    assert path.exists() and not (tmp_path / "config.json.bak").exists()
    assert json.loads((tmp_path / "config.json.v1").read_text()) == v1
    assert "Choose the version for trunk in Settings" in validate_config(config)


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[1, 2]",
        '{"branch_versions": 5}',
        '{"branch_versions": ["trunk"]}',
        '{"branch_versions": [{"branch": 1}]}',
        '{"branch_versions": [{"branch": "trunk", "marker": 3}]}',
        '{"branches": [1]}',
        '{"launch_at_login": "yes"}',
    ],
)
def test_broken_file_is_backed_up_and_defaults_are_used(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    assert load_config(path) == AppConfig()
    assert (tmp_path / "config.json.bak").read_text() == content
    assert not path.exists()


def test_branches_markers_and_versions_of():
    config = AppConfig(
        branch_versions=[BranchVersion("trunk", "3.25"), BranchVersion("trunk", "alt-1.55"), BranchVersion("hotfix")]
    )
    assert config.branches == ["trunk", "trunk", "hotfix"]
    assert config.markers == ["3.25", "alt-1.55"]
    assert config.versions_of("trunk") == ["3.25", "alt-1.55"]
    assert config.versions_of("hotfix") == []
    assert config.versions_of("gone") == []


def test_label_names_the_record():
    assert BranchVersion("trunk", "alt-1.55").label == "trunk → alt-1.55"
    assert BranchVersion("trunk").label == "trunk (no version)"


def test_label_is_not_saved(tmp_path):
    path = tmp_path / "config.json"
    save_config(AppConfig(branch_versions=[BranchVersion("trunk", "3.25")]), path)
    assert json.loads(path.read_text())["branch_versions"] == [{"branch": "trunk", "marker": "3.25"}]


@pytest.mark.parametrize("marker", ["3.25", "3.24", "alt-1.55", "v10", "release_2"])
def test_valid_markers(marker):
    assert validate_marker(marker) is None


@pytest.mark.parametrize("marker", ["", "3 25", "-3.25", ".3", "3..25", "3.25/x", "3:25", "3.25~", "3.25#", "ё"])
def test_invalid_markers(marker):
    assert validate_marker(marker) is not None


@pytest.mark.parametrize("branch", ["trunk", "trunk-rc", "release/3.25", "feature_x"])
def test_valid_branches(branch):
    assert validate_branch(branch) is None


@pytest.mark.parametrize("branch", ["", "mk dev", "release/", "a//b", "-x", "a..b", "x.lock", "a/.b"])
def test_invalid_branches(branch):
    assert validate_branch(branch) is not None


def test_template_needs_both_placeholders():
    assert validate_template("{marker}-#{hash}") is None
    assert validate_template("{marker}") is not None
    assert validate_template("v{hash}") is not None


def test_validate_config_reports_everything_missing():
    problems = validate_config(AppConfig())
    assert "Choose the project folder in Settings" in problems
    assert "Add at least one branch in Settings" in problems


def test_validate_config_flags_duplicates_and_bad_template():
    config = AppConfig(
        project_path="/p",
        branch_versions=[
            BranchVersion("trunk", "3.25"),
            BranchVersion("trunk", "3.25"),
            BranchVersion("trunk-rc", "3.24"),
            BranchVersion("hotfix", "3.24"),
        ],
        tag_template="{marker}",
    )
    assert validate_config(config) == [
        "Tag template must contain {marker} and {hash}",
        "trunk → 3.25 is listed more than once",
        "Version '3.24' is set on more than one branch",
    ]


def test_one_branch_may_have_several_versions():
    config = AppConfig(
        project_path="/p", branch_versions=[BranchVersion("trunk", "3.25"), BranchVersion("trunk", "alt-1.55")]
    )
    assert validate_config(config) == []


def test_same_branch_twice_without_a_version_is_one_problem():
    config = AppConfig(project_path="/p", branch_versions=[BranchVersion("trunk"), BranchVersion("trunk")])
    assert validate_config(config) == [
        "Choose the version for trunk in Settings",
        "trunk (no version) is listed more than once",
    ]


def test_branch_without_version_is_a_problem():
    config = AppConfig(project_path="/p", branch_versions=[BranchVersion("trunk")])
    assert validate_config(config) == ["Choose the version for trunk in Settings"]


def test_valid_config_has_no_problems():
    assert validate_config(AppConfig(project_path="/p", branch_versions=[BranchVersion("trunk", "3.25")])) == []


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("3.25", "3.26"),
        ("3.9", "3.10"),
        ("alt-1.55", "alt-1.56"),
        ("3.0-react", "3.1-react"),
        ("1.09", "1.10"),
        ("v10", "v11"),
        ("beta", None),
    ],
)
def test_next_version(marker, expected):
    assert next_version(marker) == expected


def test_template_must_not_look_like_an_option():
    assert validate_template("-F/etc/passwd{marker}{hash}") == "Tag template must not start with '-'"
    assert validate_template("v{marker}-{hash}") is None


@pytest.mark.parametrize("remote", ["origin", "upstream", "my.fork", "team/origin"])
def test_valid_remotes(remote):
    assert validate_remote(remote) is None


@pytest.mark.parametrize("remote", ["-oProxyCommand=x", "--upload-pack=touch /tmp/x", "or igin", "a\tb"])
def test_invalid_remotes(remote):
    assert validate_remote(remote) == f"Invalid remote name {remote!r}"


def test_empty_remote_keeps_its_message():
    assert validate_remote("  ") == "Remote name is empty"
    assert "Remote name is empty" in validate_config(AppConfig(project_path="/p", remote=""))
