import json
import shutil

import pytest
import shiboken6

from git_version_tagger import github_auth
from git_version_tagger.github_auth import INSTALL_HINT
from git_version_tagger.ui import github_account, messages
from git_version_tagger.ui.github_account import GitHubAccountBox
from helpers import git

LOGGED_IN = json.dumps({"hosts": {"github.com": [{"login": "octocat", "active": True, "state": "success"}]}})
STATUS_CALL = "auth status --hostname github.com --json hosts"


@pytest.fixture
def no_gh(monkeypatch):
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **kw: None if name == "gh" else real_which(name, *a, **kw))
    monkeypatch.setattr(github_auth, "GH_CANDIDATES", ())


def make_box(qtbot, config) -> GitHubAccountBox:
    box = GitHubAccountBox(lambda: config)
    qtbot.addWidget(box)
    box.refresh()
    qtbot.waitUntil(box.check_button.isEnabled, timeout=15000)
    return box


def test_without_gh_the_box_explains_how_to_install_it(qtbot, config, no_gh):
    box = make_box(qtbot, config)
    assert box.status.text() == "The GitHub CLI (gh) is not installed."
    assert box.hint.text() == INSTALL_HINT
    assert not box.login_button.isEnabled()


def test_logged_out(qtbot, config, fake_gh):
    box = make_box(qtbot, config)
    assert box.status.text() == "Not logged in to github.com"
    assert box.login_button.isEnabled()
    assert box.login_button.text() == "Log in with GitHub…"
    assert not box.setup_git_button.isVisibleTo(box)
    assert fake_gh.calls() == [STATUS_CALL]


def test_logged_in_but_git_does_not_use_the_login_yet(qtbot, config, fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_STATUS", LOGGED_IN)
    box = make_box(qtbot, config)
    assert box.status.text() == "Logged in to github.com as octocat"
    assert box.setup_git_button.isVisibleTo(box)
    box.setup_git_button.click()
    qtbot.waitUntil(lambda: "auth setup-git --hostname github.com" in fake_gh.calls(), timeout=15000)
    qtbot.waitUntil(box.check_button.isEnabled, timeout=15000)
    assert fake_gh.calls()[-1] == STATUS_CALL  # checked again after the setup


def test_logged_in_and_git_uses_gh(qtbot, config, fake_gh, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_GH_STATUS", LOGGED_IN)
    git(tmp_path, "config", "--global", "--add", "credential.https://github.com.helper", "!gh auth git-credential")
    box = make_box(qtbot, config)
    assert not box.setup_git_button.isVisibleTo(box)
    assert box.login_button.text() == "Log in again…"
    assert box.hint.text() == "git fetch and push to https://github.com use this login."


def test_ssh_remote_uses_its_host_and_says_the_login_is_not_needed(qtbot, config, repos, fake_gh):
    git(repos.project, "remote", "set-url", "origin", "git@github.acme.io:acme/app.git")
    box = make_box(qtbot, config)
    assert box.status.text() == "Not logged in to github.acme.io"
    assert "SSH" in box.hint.text()
    assert fake_gh.calls() == ["auth status --hostname github.acme.io --json hosts"]


def test_log_in_opens_the_login_window_and_checks_again(qtbot, config, fake_gh, monkeypatch):
    monkeypatch.setattr(messages, "confirm", lambda *args: pytest.fail("github.com must not ask"))
    opened = []

    class FakeLoginDialog:
        def __init__(self, gh, host, parent=None):
            opened.append((gh, host))

        def exec(self):
            return 1

    monkeypatch.setattr(github_account, "GitHubLoginDialog", FakeLoginDialog)
    box = make_box(qtbot, config)
    box.login_button.click()
    assert opened == [(str(fake_gh.path), "github.com")]
    qtbot.waitUntil(box.check_button.isEnabled, timeout=15000)
    assert fake_gh.calls() == [STATUS_CALL, STATUS_CALL]


def test_gh_failure_is_shown_and_login_stays_possible(qtbot, config, fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_EXIT", "2")
    monkeypatch.setenv("FAKE_GH_STDERR", "could not read config")
    box = make_box(qtbot, config)
    assert box.status.text() == "Could not check the GitHub login: gh auth status failed: could not read config"
    assert box.login_button.isEnabled()


def test_closing_settings_while_gh_runs_is_safe(qtbot, config, fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_SECONDS", "1")
    finished = []
    real_load = github_account.load_github_state

    def load_and_record(cfg):
        state = real_load(cfg)
        finished.append(state)
        return state

    monkeypatch.setattr(github_account, "load_github_state", load_and_record)
    box = GitHubAccountBox(lambda: config)
    box.refresh()
    shiboken6.delete(box)  # Settings closed while gh is still running
    qtbot.waitUntil(lambda: bool(finished), timeout=15000)
    qtbot.wait(200)  # the queued result reaches the deleted box; pytest-qt fails the test on an exception


def test_logging_in_to_another_host_asks_first(qtbot, config, repos, fake_gh, monkeypatch):
    git(repos.project, "remote", "set-url", "origin", "https://gіthub.com/acme/app.git")  # Cyrillic і
    asked, opened, answer = [], [], [False]

    class FakeLoginDialog:
        def __init__(self, gh, host, parent=None):
            opened.append(host)

        def exec(self):
            return 1

    monkeypatch.setattr(github_account, "GitHubLoginDialog", FakeLoginDialog)
    monkeypatch.setattr(messages, "confirm", lambda parent, title, text: asked.append((title, text)) or answer[0])
    box = make_box(qtbot, config)
    assert box.status.text() == "Not logged in to xn--gthub-n2e.com"
    box.login_button.click()
    assert asked[0][0] == "Log in to xn--gthub-n2e.com?"
    assert "not github.com" in asked[0][1]
    assert opened == []
    answer[0] = True
    qtbot.waitUntil(box.check_button.isEnabled, timeout=15000)
    box.login_button.click()
    assert opened == ["gіthub.com"]
    qtbot.waitUntil(box.check_button.isEnabled, timeout=15000)  # let the post-login refresh finish
