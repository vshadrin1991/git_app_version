import os
import plistlib
import subprocess
import sys
import textwrap

import pytest

from git_version_tagger import platform_support
from git_version_tagger.platform_support import LAUNCH_AGENT_LABEL, launch_command, set_autostart


def test_linux_autostart_writes_and_removes_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(platform_support, "launch_command", lambda: ["/opt/git-version-tagger/git-version-tagger"])
    path = set_autostart(True, platform="linux", home=tmp_path)
    assert path == tmp_path / ".config" / "autostart" / "git-version-tagger.desktop"
    text = path.read_text()
    assert "Exec=/opt/git-version-tagger/git-version-tagger" in text
    assert "X-GNOME-Autostart-enabled=true" in text
    set_autostart(False, platform="linux", home=tmp_path)
    assert not path.exists()


def test_macos_autostart_writes_launch_agent(tmp_path, monkeypatch):
    command = ["/usr/bin/open", "-a", "/Applications/GitVersionTagger.app"]
    monkeypatch.setattr(platform_support, "launch_command", lambda: command)
    path = set_autostart(True, platform="darwin", home=tmp_path)
    assert path == tmp_path / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
    data = plistlib.loads(path.read_bytes())
    assert data == {"Label": LAUNCH_AGENT_LABEL, "ProgramArguments": command, "RunAtLoad": True}


def test_paths_with_spaces_are_quoted_in_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(platform_support, "launch_command", lambda: ["/opt/my apps/gvt"])
    path = set_autostart(True, platform="linux", home=tmp_path)
    assert 'Exec="/opt/my apps/gvt"' in path.read_text()


def test_disabling_when_nothing_is_installed_is_harmless(tmp_path):
    set_autostart(False, platform="linux", home=tmp_path)
    set_autostart(False, platform="darwin", home=tmp_path)


def test_launch_command_in_development_runs_the_module():
    assert launch_command()[-2:] == ["-m", "git_version_tagger"]


# Runs in a child process: it needs the real macOS platform plugin, and without the fix it aborts.
MENU_OPENS_AFTER_NON_MOUSE_EVENT = textwrap.dedent(
    """
    import objc
    from AppKit import NSApp, NSEvent, NSEventTypeApplicationDefined
    from PySide6.QtWidgets import QApplication
    from git_version_tagger.platform_support import disable_qt_tray_activation

    app = QApplication([])
    disable_qt_tray_activation()
    # After Show log, Refresh or Settings the app's current event is not a mouse event.
    NSApp.postEvent_atStart_(NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
        NSEventTypeApplicationDefined, (0, 0), 0, 0, 0, None, 0, 0, 0), True)
    app.processEvents()
    assert NSApp.currentEvent().type() == NSEventTypeApplicationDefined
    # macOS 27 sends this when the menu bar menu opens; Qt 6.11 then calls clickCount on that event.
    objc.lookUpClass("QStatusItemDelegate").alloc().init().statusItemMenuBeganTracking_(None)
    """
)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS menu bar only")
def test_opening_the_tray_menu_after_a_non_mouse_event_does_not_crash():
    result = subprocess.run(
        [sys.executable, "-c", MENU_OPENS_AFTER_NON_MOUSE_EVENT],
        env={**os.environ, "QT_QPA_PLATFORM": "cocoa"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-2000:]
