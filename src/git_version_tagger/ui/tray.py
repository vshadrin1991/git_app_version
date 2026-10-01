"""The menu bar (macOS) / top bar (Ubuntu) icon, its menu and the tagging flow."""
from __future__ import annotations

import dataclasses
import logging
from functools import partial
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..config import AppConfig, load_config, save_config, validate_config
from ..github_auth import explain_error
from ..platform_support import bring_to_front, set_autostart
from ..tagger import TagPlan, make_tagger
from . import messages
from .icons import app_icon, tray_icon
from .log_window import LogWindow, QtLogHandler
from .settings_dialog import SettingsDialog
from .worker import run_in_background

log = logging.getLogger("git_version_tagger.ui")


def move_tag(config: AppConfig, branch: str, marker: str) -> TagPlan:
    """Fetch, then move the tag right away, with no confirmation (like tag.sh). Runs on a worker thread."""
    tagger = make_tagger(config)
    plan = tagger.plan(branch, marker)
    log.info("%s", plan.describe())
    tagger.apply(plan)
    return plan


def show_error(message: str) -> None:
    bring_to_front()
    messages.warning(None, "Git Version Tagger", message)


ERROR_LIMIT = 48  # a menu is as wide as its longest item
ERROR_TOOLTIP = "Last error (click for the log):"


def short_error(message: str, limit: int = ERROR_LIMIT) -> str:
    """A menu-sized summary: the first line without the git command and "remote:"/"fatal:" prefixes.

    "git fetch … failed: remote: Repository not found." → "Repository not found". The full text goes in
    the item's tooltip and the log.
    """
    line = next((text.strip() for text in message.splitlines() if text.strip()), "Unknown error")
    for prefix in ("failed: ", "remote: ", "fatal: ", "error: "):
        if prefix in line:
            line = line.split(prefix, 1)[1]
    line = line.strip().rstrip(".")
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


class TrayController(QObject):
    def __init__(self, config_path: Path, log_handler: QtLogHandler) -> None:
        super().__init__()
        self.config_path = config_path
        self.config = load_config(config_path)
        self.versions: dict[str, list[str]] = {}
        self.busy = False
        self.last_error: str | None = None
        self.tag_actions: dict[tuple[str, str], QAction] = {}  # (branch, version) -> "Tag <branch> → <version>"
        self._submenus: list[QMenu] = []

        self.log_window = LogWindow()
        log_handler.emitter.message.connect(self.log_window.append_line)

        self.menu = QMenu()
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.setContextMenu(self.menu)
        self.rebuild_menu()
        self.tray.show()
        self.refresh()

    # ---- menu --------------------------------------------------------------
    def rebuild_menu(self) -> None:
        for submenu in self._submenus:
            submenu.deleteLater()
        self._submenus.clear()
        self.menu.clear()
        self.tag_actions.clear()
        self.menu.setToolTipsVisible(True)

        project = Path(self.config.project_path).name if self.config.project_path else "No project"
        self._add(self.menu, project, None, enabled=False)
        if self.last_error:
            error = self._add(self.menu, f"⚠ {short_error(self.last_error)}", self.log_window.show_and_raise)
            error.setToolTip(messages.plain_tooltip(ERROR_TOOLTIP, self.last_error))
        self.menu.addSeparator()

        problems = validate_config(self.config)
        if problems:
            self._add(self.menu, f"⚠ {short_error(problems[0])}", self.open_settings).setToolTip(
                messages.plain_tooltip("Open Settings to fix:", problems[0])
            )
        else:
            for item in self.config.branch_versions:
                action = self._add(
                    self.menu,
                    f"Tag {item.branch} → {item.marker}",
                    partial(self.start_tagging, item.branch, item.marker),
                    enabled=not self.busy,
                )
                current = self.versions.get(item.marker) or []
                action.setToolTip(f"Now: {', '.join(current)}" if current else f"No {item.marker} tag yet")
                self.tag_actions[(item.branch, item.marker)] = action
            copy_menu = self._submenu("Copy tag")
            tags = [tag for marker in self.config.markers for tag in self.versions.get(marker) or []]
            for tag in tags:
                self._add(copy_menu, tag, partial(self.copy_to_clipboard, tag))
            if not tags:
                self._add(copy_menu, "No tags yet", None, enabled=False)
            self.menu.addSeparator()
            self._add(self.menu, "Refresh", self.refresh, enabled=not self.busy)

        self._add(self.menu, "Show log…", self.log_window.show_and_raise)
        self._add(self.menu, "Settings…", self.open_settings, enabled=not self.busy)
        self.menu.addSeparator()
        self._add(self.menu, "Quit", QApplication.quit)
        status = "working…" if self.busy else (short_error(self.last_error) if self.last_error else "ready")
        self.tray.setToolTip(messages.plain_tooltip("Git Version Tagger", status))

    def _submenu(self, title: str) -> QMenu:
        submenu = self.menu.addMenu(title)
        self._submenus.append(submenu)
        return submenu

    @staticmethod
    def _add(menu: QMenu, text: str, slot: Callable[[], object] | None, enabled: bool = True) -> QAction:
        action = menu.addAction(text)
        action.setEnabled(enabled)
        if slot is not None:
            # Run the slot after triggered() returns: slots rebuild the menu, and deleting
            # an action inside its own triggered() handler crashes Qt.
            action.triggered.connect(lambda _checked=False: QTimer.singleShot(0, slot))
        return action

    # ---- tagging -----------------------------------------------------------
    def start_tagging(self, branch: str, marker: str) -> None:
        if self.busy:
            return
        config = dataclasses.replace(self.config)
        self._set_busy(True)
        log.info("Moving %s to the head of %s", marker, branch)
        run_in_background(lambda: move_tag(config, branch, marker), self._on_tag_done, self._on_tag_failed)

    def _on_tag_done(self, plan: TagPlan) -> None:
        if plan.up_to_date:
            self.notify("Nothing to do", f"{plan.new_tag} already marks the head of {plan.branch}")
        else:
            self.copy_to_clipboard(plan.new_tag)
            self.notify("Version tag moved", f"{plan.new_tag} was pushed (copied to the clipboard)")
        self._set_busy(False)
        self.refresh()

    def _on_tag_failed(self, exc: Exception) -> None:
        self.last_error = str(exc)
        log.error("%s", exc)
        self._set_busy(False)
        show_error(explain_error(exc))

    # ---- refresh -----------------------------------------------------------
    def refresh(self) -> None:
        if self.busy or validate_config(self.config):
            return
        config = dataclasses.replace(self.config)
        self._set_busy(True)
        run_in_background(lambda: make_tagger(config).refresh(), self._on_refreshed, self._on_refresh_failed)

    def _on_refreshed(self, versions: dict[str, list[str]]) -> None:
        self.versions = versions
        self.last_error = None
        self._set_busy(False)

    def _on_refresh_failed(self, exc: Exception) -> None:
        self.last_error = str(exc)
        log.error("Refresh failed: %s", exc)
        self._set_busy(False)
        self.notify("Could not refresh tags", explain_error(exc), error=True)

    # ---- settings ----------------------------------------------------------
    def open_settings(self) -> None:
        if self.busy:
            return
        bring_to_front()
        dialog = SettingsDialog(self.config)
        if not dialog.exec():
            return
        new_config = dialog.current_config()
        save_config(new_config, self.config_path)
        if new_config.launch_at_login != self.config.launch_at_login:
            try:
                set_autostart(new_config.launch_at_login)
            except OSError as exc:
                log.error("Could not change start at login: %s", exc)
        self.config = new_config
        self.versions = {}
        self.last_error = None
        self.rebuild_menu()
        self.refresh()

    # ---- helpers -----------------------------------------------------------
    def copy_to_clipboard(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    def notify(self, title: str, message: str, error: bool = False) -> None:
        log.info("%s: %s", title, message)
        if QSystemTrayIcon.supportsMessages():
            icon = QSystemTrayIcon.MessageIcon.Critical if error else app_icon()
            self.tray.showMessage(messages.no_markup(title), messages.no_markup(message), icon, 8000)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.tray.setIcon(tray_icon(busy))
        self.rebuild_menu()
