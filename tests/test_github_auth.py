import json
import shutil
import subprocess

import pytest

from git_version_tagger import github_auth
from git_version_tagger.git_runner import GitError, GitRunner
from git_version_tagger.github_auth import (
    LOGIN_HINT,
    AuthStatus,
    DevicePrompt,
    GhError,
    RemoteUrl,
    ascii_host,
    auth_status,
    explain_error,
    find_gh,
    git_uses_gh,
    is_device_page_of,
    login_arguments,
    parse_device_prompt,
    parse_remote_url,
    parse_status,
    parse_status_text,
    setup_git,
)
from git_version_tagger.tagger import TaggerError
from helpers import git

TWO_ACCOUNTS = {
    "hosts": {
        "github.com": [
            {"host": "github.com", "login": "work-bot", "active": False, "state": "success"},
            {"host": "github.com", "login": "octocat", "active": True, "state": "success"},
        ]
    }
}


def test_find_gh_uses_path(fake_gh):
    assert find_gh() == str(fake_gh.path)


def test_find_gh_checks_well_known_locations_when_path_is_minimal(tmp_path, monkeypatch):
    fake = tmp_path / "gh"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(github_auth, "GH_CANDIDATES", (str(tmp_path / "missing"), str(fake)))
    assert find_gh() == str(fake)


def test_find_gh_returns_none_when_gh_is_not_installed(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(github_auth, "GH_CANDIDATES", ())
    assert find_gh() is None


def test_parse_status_reports_the_active_account():
    status = parse_status(json.dumps(TWO_ACCOUNTS), "github.com")
    assert status == AuthStatus("github.com", login="octocat")
    assert status.logged_in
    assert status.describe() == "Logged in to github.com as octocat"


def test_parse_status_without_an_account_on_the_host():
    status = parse_status(json.dumps(TWO_ACCOUNTS), "github.acme.io")
    assert not status.logged_in
    assert status.describe() == "Not logged in to github.acme.io"


def test_parse_status_with_a_token_that_no_longer_works():
    data = {"hosts": {"github.com": [{"login": "octocat", "active": True, "state": "error"}]}}
    status = parse_status(json.dumps(data), "github.com")
    assert not status.logged_in
    assert status.describe() == "The login to github.com as octocat does not work (error) - log in again"


@pytest.mark.parametrize("output", ["", "not json", "[]", '{"hosts": []}', '{"hosts": {"github.com": ["x"]}}'])
def test_parse_status_rejects_unexpected_output(output):
    with pytest.raises(GhError, match="Unexpected output"):
        parse_status(output, "github.com")


@pytest.mark.parametrize(
    "output",
    [
        "github.com\n  ✓ Logged in to github.com as octocat (/home/me/.config/gh/hosts.yml)\n",
        "github.com\n  ✓ Logged in to github.com account octocat (keyring)\n",
    ],
)
def test_parse_status_text_of_older_gh(output):
    assert parse_status_text(output, "github.com", 0) == AuthStatus("github.com", login="octocat")
    assert parse_status_text(output, "github.com", 1).problem == "error"
    assert parse_status_text(output, "github.acme.io", 0) == AuthStatus("github.acme.io")


def test_parse_status_text_when_logged_out():
    output = "You are not logged into any GitHub hosts. Run gh auth login to authenticate."
    assert parse_status_text(output, "github.com", 1) == AuthStatus("github.com")


def test_auth_status_asks_gh_about_one_host(fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_STATUS", json.dumps(TWO_ACCOUNTS))
    assert auth_status(str(fake_gh.path), "github.com").login == "octocat"
    assert fake_gh.calls() == ["auth status --hostname github.com --json hosts"]


def test_auth_status_falls_back_to_text_on_gh_without_json(fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_OLD", "1")
    monkeypatch.setenv("FAKE_GH_STATUS", "github.com\n  Logged in to github.com as octocat (oauth_token)")
    assert auth_status(str(fake_gh.path), "github.com") == AuthStatus("github.com", login="octocat")
    assert fake_gh.calls() == ["auth status --hostname github.com --json hosts", "auth status --hostname github.com"]


def test_auth_status_reports_gh_failures(fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_EXIT", "2")
    monkeypatch.setenv("FAKE_GH_STDERR", "could not read config")
    with pytest.raises(GhError, match="gh auth status failed: could not read config"):
        auth_status(str(fake_gh.path), "github.com")


def test_missing_gh_binary_raises_gh_error(tmp_path):
    with pytest.raises(GhError, match="cannot run"):
        auth_status(str(tmp_path / "gh"), "github.com")


def test_gh_never_waits_for_a_terminal(fake_gh, monkeypatch):
    seen = {}
    real_run = subprocess.run

    def spy(command, **kwargs):
        seen.update(kwargs)
        return real_run(command, **kwargs)

    monkeypatch.setattr(github_auth.subprocess, "run", spy)
    auth_status(str(fake_gh.path), "github.com")
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["env"]["GH_PROMPT_DISABLED"] == "1"
    assert seen["timeout"] == github_auth.GH_TIMEOUT


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/acme/app.git", RemoteUrl("github.com", ssh=False)),
        ("https://token@GitHub.com/acme/app", RemoteUrl("github.com", ssh=False)),
        ("https://github.acme.io:8443/acme/app.git", RemoteUrl("github.acme.io", ssh=False)),
        ("git@github.com:acme/app.git", RemoteUrl("github.com", ssh=True)),
        ("ssh://git@github.com/acme/app.git", RemoteUrl("github.com", ssh=True)),
        ("/srv/git/app.git", None),
        ("../app.git", None),
        ("app.git", None),
        ("file:///srv/git/app.git", None),
    ],
)
def test_parse_remote_url(url, expected):
    assert parse_remote_url(url) == expected


DEVICE_OUTPUT = (
    "! First copy your one-time code: ABCD-1234\n"
    "Open this URL to continue in your web browser: https://github.com/login/device\n"
)


def test_login_arguments_use_the_browser_flow_for_the_host():
    assert login_arguments("github.acme.io") == ["auth", "login", "--hostname", "github.acme.io", "--web"]


def test_parse_device_prompt_finds_the_code_and_the_url():
    assert parse_device_prompt(DEVICE_OUTPUT, "github.com") == DevicePrompt("ABCD-1234", "https://github.com/login/device")


def test_parse_device_prompt_is_none_until_the_code_arrives():
    assert parse_device_prompt("", "github.com") is None
    assert parse_device_prompt("! First copy your one-time", "github.com") is None


def test_parse_device_prompt_uses_the_host_device_page_until_the_url_is_complete():
    partial = "! First copy your one-time code: WXYZ-9876\nOpen this URL to continue in your web browser: https://git"
    assert parse_device_prompt(partial, "github.acme.io") == DevicePrompt(
        "WXYZ-9876", "https://github.acme.io/login/device"
    )


def test_setup_git_runs_gh_for_the_host(fake_gh):
    setup_git(str(fake_gh.path), "github.com")
    assert fake_gh.calls() == ["auth setup-git --hostname github.com"]


def test_setup_git_failure_raises_with_the_gh_message(fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_EXIT", "1")
    monkeypatch.setenv("FAKE_GH_STDERR", "You are not logged into github.com")
    with pytest.raises(GhError, match="not logged into github.com"):
        setup_git(str(fake_gh.path), "github.com")


def test_git_uses_gh_only_after_setup_git_for_that_host(tmp_path):
    runner = GitRunner(tmp_path)  # not a repository: reads the (isolated) global config
    assert not git_uses_gh(runner, "github.com")
    git(tmp_path, "config", "--global", "--add", "credential.https://github.com.helper", "")
    git(tmp_path, "config", "--global", "--add", "credential.https://github.com.helper", "!/opt/homebrew/bin/gh auth git-credential")
    assert git_uses_gh(runner, "github.com")
    assert not git_uses_gh(runner, "github.acme.io")


@pytest.mark.parametrize(
    "stderr",
    [
        "fatal: could not read Username for 'https://github.com': terminal prompts disabled",
        "remote: Invalid username or token. Password authentication is not supported for Git operations.",
        "fatal: Authentication failed for 'https://github.com/acme/app.git/'",
        "fatal: unable to access 'https://github.com/acme/app.git/': The requested URL returned error: 403",
    ],
)
def test_explain_error_points_to_the_login_when_the_remote_wants_credentials(stderr):
    assert explain_error(GitError(["fetch", "origin"], 128, stderr)).endswith(LOGIN_HINT)


def test_explain_error_leaves_other_errors_alone():
    exc = TaggerError("Branch 'gone' not found on remote 'origin'")
    assert explain_error(exc) == "Branch 'gone' not found on remote 'origin'"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("github.com", "github.com"),
        ("GitHub.acme.io", "github.acme.io"),
        ("gіthub.com", "xn--gthub-n2e.com"),  # Cyrillic і
        ("a..b", "a..b"),  # not a valid IDNA name: shown as it is
    ],
)
def test_ascii_host(host, expected):
    assert ascii_host(host) == expected


def test_status_names_a_lookalike_host_in_punycode():
    assert AuthStatus("gіthub.com").describe() == "Not logged in to xn--gthub-n2e.com"


@pytest.mark.parametrize(
    ("url", "host", "ok"),
    [
        ("https://github.com/login/device", "github.com", True),
        ("https://github.acme.io/login/device", "github.acme.io", True),
        ("https://xn--gthub-n2e.com/login/device", "gіthub.com", True),
        ("http://github.com/login/device", "github.com", False),
        ("https://github.com.evil.io/login/device", "github.com", False),
        ("https://github.com@evil.io/login/device", "github.com", False),
        ("https://evil.io/github.com/login/device", "github.com", False),
        ("not a url", "github.com", False),
    ],
)
def test_is_device_page_of(url, host, ok):
    assert is_device_page_of(url, host) is ok
