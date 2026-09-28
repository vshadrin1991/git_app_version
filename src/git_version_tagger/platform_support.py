"""OS integration: start at login (macOS LaunchAgent / Linux XDG autostart) and macOS menu-bar-only mode."""
from __future__ import annotations

import logging
import plistlib
import sys
from pathlib import Path

log = logging.getLogger("git_version_tagger.platform")

LAUNCH_AGENT_LABEL = "com.vshadrin.git-version-tagger"
DESKTOP_FILE = "git-version-tagger.desktop"


def launch_command() -> list[str]:
    if getattr(sys, "frozen", False):  # PyInstaller build
        exe = Path(sys.executable)
        if sys.platform == "darwin" and exe.parent.name == "MacOS":
            return ["/usr/bin/open", "-a", str(exe.parents[2])]  # .../GitVersionTagger.app
        return [str(exe)]
    return [sys.executable, "-m", "git_version_tagger"]


def autostart_path(platform: str = sys.platform, home: Path | None = None) -> Path:
    home = home or Path.home()
    if platform == "darwin":
        return home / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
    return home / ".config" / "autostart" / DESKTOP_FILE


def autostart_contents(command: list[str], platform: str = sys.platform) -> bytes:
    if platform == "darwin":
        return plistlib.dumps({"Label": LAUNCH_AGENT_LABEL, "ProgramArguments": command, "RunAtLoad": True})
    exec_line = " ".join(f'"{part}"' if " " in part else part for part in command)
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Git Version Tagger\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    ).encode()


def set_autostart(enabled: bool, platform: str = sys.platform, home: Path | None = None) -> Path:
    path = autostart_path(platform, home)
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(autostart_contents(launch_command(), platform))
    else:
        path.unlink(missing_ok=True)
    return path


def hide_dock_icon() -> None:
    """Run as a menu-bar-only app on macOS (packaged builds also set LSUIElement)."""
    app = _ns_app()
    if app is not None:
        app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory


def bring_to_front() -> None:
    """Menu-bar-only apps are never frontmost by themselves; activate before showing a window."""
    app = _ns_app()
    if app is not None:
        app.activateIgnoringOtherApps_(True)


def disable_qt_tray_activation() -> None:
    """Stop Qt 6.11 from crashing the app on macOS 27 whenever the menu bar menu opens.

    When the menu opens, Qt's QStatusItemDelegate emits QSystemTrayIcon.activated and reads
    NSApp.currentEvent.clickCount to tell a click from a double click. macOS 27 opens the menu
    without a mouse event, so after any other event (closing the log, a finished refresh) that
    call raises and AppKit aborts. The app never uses `activated`, so the handler does nothing.
    Call it once the QApplication exists: that is when Qt registers the delegate class.
    """
    if sys.platform != "darwin":
        return
    try:
        import objc
    except ImportError:
        return
    try:
        delegate = objc.lookUpClass("QStatusItemDelegate")
    except objc.nosuchclass_error:
        log.warning("Qt's QStatusItemDelegate was not found; the menu bar crash workaround is not active")
        return
    objc.classAddMethods(
        delegate,
        [objc.selector(_ignore_menu_tracking, selector=b"statusItemMenuBeganTracking:", signature=b"v@:@")],
    )


def _ignore_menu_tracking(self, notification) -> None:
    pass


def _ns_app():
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSApplication
    except ImportError:
        return None
    return NSApplication.sharedApplication()
