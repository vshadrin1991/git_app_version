"""GUI entry point: one instance, tray icon, logging to the log window and to a file."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .config import default_config_path, validate_config
from .platform_support import disable_qt_tray_activation, hide_dock_icon
from .ui.icons import app_icon
from .ui.log_window import QtLogHandler
from .ui.tray import TrayController

APP_NAME = "Git Version Tagger"
TRAY_UNAVAILABLE = (
    "No menu bar / top bar area for status icons was found.\n\n"
    "On Ubuntu (GNOME) install and enable the AppIndicator extension:\n"
    "  sudo apt install gnome-shell-extension-appindicator\n"
    "  gnome-extensions enable ubuntu-appindicators@ubuntu.com\n"
    "then log out and back in."
)


def setup_logging() -> QtLogHandler:
    logger = logging.getLogger("git_version_tagger")
    logger.setLevel(logging.INFO)
    handler = QtLogHandler()
    logger.addHandler(handler)
    log_dir = Path(user_log_dir("git-version-tagger"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_dir.chmod(0o700)  # the log names repositories, hosts and GitHub accounts: keep it to this user
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    return handler


def run_gui(config_path: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())  # title bar and taskbar of Settings and the log on Ubuntu
    app.setQuitOnLastWindowClosed(False)  # closing Settings or the log must not quit the app
    config_path = config_path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lock = QLockFile(str(config_path.parent / "app.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, f"{APP_NAME} is already running - look for its icon in the menu bar.")
        return 0
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, TRAY_UNAVAILABLE)
        return 1

    hide_dock_icon()
    log_handler = setup_logging()
    disable_qt_tray_activation()  # before the tray icon exists; see the docstring for the crash
    controller = TrayController(config_path, log_handler)
    if validate_config(controller.config):
        QTimer.singleShot(0, controller.open_settings)  # first launch: ask for the project
    return app.exec()
