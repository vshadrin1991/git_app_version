from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication

from git_version_tagger.ui.github_login import GitHubLoginDialog


def make_dialog(qtbot, gh: str, host: str = "github.com") -> GitHubLoginDialog:
    dialog = GitHubLoginDialog(gh, host)
    qtbot.addWidget(dialog)
    return dialog


def test_login_shows_and_copies_the_code_then_sets_up_git(qtbot, fake_gh):
    dialog = make_dialog(qtbot, str(fake_gh.path))
    with qtbot.waitSignal(dialog.accepted, timeout=15000):
        pass
    assert dialog.code.text() == "ABCD-1234"
    assert QGuiApplication.clipboard().text() == "ABCD-1234"
    assert dialog.prompt.url == "https://github.com/login/device"
    assert fake_gh.calls() == ["auth login --hostname github.com --web", "auth setup-git --hostname github.com"]


def test_failed_login_keeps_the_output_and_skips_git_setup(qtbot, fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_EXIT", "1")
    monkeypatch.setenv("FAKE_GH_STDERR", "error: the device code has expired")
    dialog = make_dialog(qtbot, str(fake_gh.path))
    qtbot.waitUntil(lambda: "failed" in dialog.status.text(), timeout=15000)
    assert "device code has expired" in dialog.log.toPlainText()
    assert fake_gh.calls() == ["auth login --hostname github.com --web"]


def test_cancel_stops_gh(qtbot, fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_SECONDS", "60")
    dialog = make_dialog(qtbot, str(fake_gh.path))
    qtbot.waitUntil(lambda: dialog.code.text() == "ABCD-1234", timeout=15000)
    dialog.reject()
    assert dialog.process.state() == QProcess.ProcessState.NotRunning
    assert "auth setup-git --hostname github.com" not in fake_gh.calls()


def test_missing_gh_is_reported(qtbot, tmp_path):
    dialog = make_dialog(qtbot, str(tmp_path / "gh"))
    qtbot.waitUntil(lambda: dialog.status.text().startswith("Cannot run"), timeout=15000)


def test_status_shows_gh_output_literally(qtbot, tmp_path):
    dialog = make_dialog(qtbot, str(tmp_path / "gh"))
    assert dialog.status.textFormat() == Qt.TextFormat.PlainText


def test_device_page_on_another_host_is_not_opened(qtbot, fake_gh, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    monkeypatch.setenv("FAKE_GH_SECONDS", "60")
    dialog = make_dialog(qtbot, str(fake_gh.path), host="github.acme.io")  # the fake prints a github.com URL
    qtbot.waitUntil(lambda: dialog.code.text() == "ABCD-1234", timeout=15000)
    assert not dialog.open_button.isEnabled()
    assert "not on github.acme.io" in dialog.status.text()
    dialog._open_device_page()  # even if called directly
    assert opened == []
    dialog.reject()


def test_device_page_on_the_login_host_is_opened(qtbot, fake_gh, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    monkeypatch.setenv("FAKE_GH_SECONDS", "60")
    dialog = make_dialog(qtbot, str(fake_gh.path))
    qtbot.waitUntil(dialog.open_button.isEnabled, timeout=15000)
    dialog.open_button.click()
    assert opened == ["https://github.com/login/device"]
    dialog.reject()


def test_window_title_shows_the_real_host(qtbot, fake_gh, monkeypatch):
    monkeypatch.setenv("FAKE_GH_SECONDS", "60")
    dialog = make_dialog(qtbot, str(fake_gh.path), host="gіthub.com")
    assert dialog.windowTitle() == "Log in to xn--gthub-n2e.com"
    dialog.reject()
