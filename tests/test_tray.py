import pytest
from PySide6.QtGui import Qt as GuiQt
from PySide6.QtGui import QGuiApplication

from git_version_tagger.config import AppConfig, BranchVersion, save_config
from git_version_tagger.git_runner import GitError
from git_version_tagger.github_auth import LOGIN_HINT
from git_version_tagger.ui import tray as tray_module
from git_version_tagger.ui.log_window import QtLogHandler
from git_version_tagger.ui.messages import plain_tooltip
from git_version_tagger.ui.tray import ERROR_TOOLTIP, TrayController, short_error


@pytest.fixture
def make_controller(qtbot, tmp_path):
    created = []

    def factory(config: AppConfig) -> TrayController:
        path = tmp_path / "config.json"
        save_config(config, path)
        controller = TrayController(path, QtLogHandler())
        created.append(controller)
        qtbot.waitUntil(lambda: not controller.busy, timeout=15000)
        return controller

    yield factory
    for controller in created:
        controller.tray.hide()


def texts(menu) -> list[str]:
    return [action.text() for action in menu.actions()]


def test_menu_has_one_tag_item_per_branch(make_controller, config):
    controller = make_controller(config)
    items = texts(controller.menu)
    assert items[0] == config.project_path.rsplit("/", 1)[-1]
    assert "Tag trunk → 3.25" in items and "Tag trunk-rc → 3.24" in items
    assert "Copy tag" in items and "Current versions" not in items


def test_unconfigured_app_points_to_settings(make_controller):
    controller = make_controller(AppConfig())
    assert "⚠ Choose the project folder in Settings" in texts(controller.menu)
    assert controller.tag_actions == {}


def test_clicking_a_branch_moves_its_version_tag_immediately(make_controller, config, repos, qtbot):
    controller = make_controller(config)
    controller.tag_actions[("trunk", "3.25")].trigger()
    qtbot.waitUntil(lambda: bool(controller.versions.get("3.25")) and not controller.busy, timeout=15000)
    [tag] = repos.remote_tags()
    assert QGuiApplication.clipboard().text() == tag
    assert controller.tag_actions[("trunk", "3.25")].toolTip() == f"Now: {tag}"
    copy_menu = next(a.menu() for a in controller.menu.actions() if a.text() == "Copy tag")
    assert texts(copy_menu) == [tag]


def test_a_branch_with_two_versions_gets_two_items_and_keeps_both_tags(make_controller, config, repos, qtbot):
    config.branch_versions.append(BranchVersion("trunk", "alt-1.55"))
    controller = make_controller(config)
    items = texts(controller.menu)
    assert "Tag trunk → 3.25" in items and "Tag trunk → alt-1.55" in items
    controller.tag_actions[("trunk", "3.25")].trigger()
    qtbot.waitUntil(lambda: bool(controller.versions.get("3.25")) and not controller.busy, timeout=15000)
    controller.tag_actions[("trunk", "alt-1.55")].trigger()
    qtbot.waitUntil(lambda: bool(controller.versions.get("alt-1.55")) and not controller.busy, timeout=15000)
    tags = repos.remote_tags()
    assert [tag.split("-#")[0] for tag in tags] == ["3.25", "alt-1.55"]  # tagging alt-1.55 kept 3.25
    assert controller.tag_actions[("trunk", "3.25")].toolTip() == f"Now: {tags[0]}"
    assert controller.tag_actions[("trunk", "alt-1.55")].toolTip() == f"Now: {tags[1]}"


def test_failed_tagging_reports_error_and_unlocks_menu(make_controller, config, monkeypatch, qtbot):
    errors = []
    monkeypatch.setattr(tray_module, "show_error", errors.append)
    config.branch_versions.append(BranchVersion("gone", "3.23"))
    controller = make_controller(config)
    controller.tag_actions[("gone", "3.23")].trigger()
    qtbot.waitUntil(lambda: bool(errors) and not controller.busy, timeout=15000)
    assert "'gone' not found on remote 'origin'" in errors[0]
    assert controller.tag_actions[("trunk", "3.25")].isEnabled()


def test_auth_failure_points_to_the_github_login(make_controller, config, monkeypatch, qtbot):
    errors = []
    monkeypatch.setattr(tray_module, "show_error", errors.append)

    def fail(*args):
        raise GitError(["push"], 128, "fatal: Authentication failed for 'https://github.com/acme/app.git/'")

    monkeypatch.setattr(tray_module, "move_tag", fail)
    controller = make_controller(config)
    controller.tag_actions[("trunk", "3.25")].trigger()
    qtbot.waitUntil(lambda: bool(errors), timeout=15000)
    assert errors[0].endswith(LOGIN_HINT)


GIT_ERROR = (
    "git fetch --prune --prune-tags --force origin failed: remote: Repository not found.\n"
    "fatal: repository 'https://github.com/acme/app.git/' not found"
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (GIT_ERROR, "Repository not found"),
        ("git push --atomic origin x failed: fatal: Authentication failed for 'https://github.com/acme/app.git/'",
         "Authentication failed for 'https://github.com/a…"),
        ("Branch 'gone' not found on remote 'origin'", "Branch 'gone' not found on remote 'origin'"),
        ("Choose the version for trunk-react in Settings", "Choose the version for trunk-react in Settings"),
        ("", "Unknown error"),
    ],
)
def test_short_error(message, expected):
    assert short_error(message) == expected
    assert len(short_error(message)) <= 48


def test_long_errors_are_shortened_in_the_menu(make_controller, config):
    controller = make_controller(config)
    controller.last_error = GIT_ERROR
    controller.rebuild_menu()
    [error] = [action for action in controller.menu.actions() if action.text().startswith("⚠")]
    assert error.text() == "⚠ Repository not found"
    assert error.toolTip() == plain_tooltip(ERROR_TOOLTIP, GIT_ERROR)


def test_menu_items_stay_short(make_controller, config):
    config.branch_versions.append(BranchVersion("trunk-react", "3.0-react"))
    controller = make_controller(config)
    controller.last_error = "git fetch failed: " + "x" * 300
    controller.rebuild_menu()
    assert max(len(text) for text in texts(controller.menu)) <= 50


EVIL_ERROR = "git push failed: remote: <a href='https://evil.example/login'>Session expired - sign in again</a>"


def test_error_tooltip_shows_html_literally(make_controller, config):
    controller = make_controller(config)
    controller.last_error = EVIL_ERROR
    controller.rebuild_menu()
    [error] = [action for action in controller.menu.actions() if action.text().startswith("⚠")]
    assert not GuiQt.mightBeRichText(error.toolTip())
    assert error.toolTip().endswith(EVIL_ERROR)
    assert not GuiQt.mightBeRichText(controller.tray.toolTip())


def test_notifications_carry_no_markup(make_controller, config, monkeypatch):
    shown = []
    controller = make_controller(config)
    monkeypatch.setattr(tray_module.QSystemTrayIcon, "supportsMessages", lambda: True)
    monkeypatch.setattr(controller.tray, "showMessage", lambda title, message, *rest: shown.append((title, message)))
    controller.notify("Could not refresh tags", "remote: <a href='x'>y</a>", error=True)
    assert shown == [("Could not refresh tags", "remote: ‹a href='x'›y‹/a›")]
