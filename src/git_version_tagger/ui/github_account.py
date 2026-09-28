"""Settings → General → GitHub account: the gh login that git uses for HTTPS remotes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import shiboken6
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..config import AppConfig
from ..git_runner import GitError, GitRunner, find_git
from ..github_auth import (
    DEFAULT_HOST,
    INSTALL_HINT,
    AuthStatus,
    GhError,
    ascii_host,
    auth_status,
    find_gh,
    git_uses_gh,
    parse_remote_url,
    setup_git,
)
from ..tagger import TaggerError, make_tagger
from . import messages
from .github_login import GitHubLoginDialog
from .style import SPACING, plain, secondary
from .worker import run_in_background

NOT_GITHUB_COM = (
    "The project's remote is on {host}, not github.com. The login page will open on {host}. "
    "Continue only if {host} is your company's GitHub Enterprise server."
)


@dataclass(frozen=True)
class GitHubState:
    host: str  # from the project's remote URL; github.com when there is none
    ssh_remote: bool = False
    gh: str | None = None  # None: the GitHub CLI is not installed
    status: AuthStatus | None = None  # None when gh is missing or `gh auth status` failed
    error: str | None = None
    git_uses_gh: bool = False


def load_github_state(config: AppConfig) -> GitHubState:
    """Everything the GitHub account box shows. Runs gh and git, so call it on a worker thread."""
    runner = GitRunner(Path.home(), find_git(config.git_executable))
    remote = None
    if config.project_path.strip():
        try:
            tagger = make_tagger(config)
            remote = parse_remote_url(tagger.remote_url())
            runner = tagger.git
        except (TaggerError, GitError):
            pass  # no usable project yet: offer github.com
    host = remote.host if remote else DEFAULT_HOST
    ssh_remote = remote is not None and remote.ssh
    gh = find_gh()
    if gh is None:
        return GitHubState(host, ssh_remote)
    try:
        status = auth_status(gh, host)
    except GhError as exc:
        return GitHubState(host, ssh_remote, gh, error=str(exc))
    return GitHubState(host, ssh_remote, gh, status, git_uses_gh=git_uses_gh(runner, host))


class GitHubAccountBox(QWidget):
    """The GitHub row on the General tab: login status, a hint, and the login buttons."""

    def __init__(self, current_config: Callable[[], AppConfig], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_config = current_config
        self.state: GitHubState | None = None
        self.status = plain(QLabel())
        self.status.setWordWrap(True)
        self.hint = secondary(QLabel())
        self.login_button = self._button("Log in with GitHub…", self.log_in)
        self.setup_git_button = self._button("Use this login for git", self.use_for_git)
        self.setup_git_button.setVisible(False)
        self.check_button = self._button("Check again", self.refresh)
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING)
        for button in (self.login_button, self.setup_git_button, self.check_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.status)
        layout.addWidget(self.hint)
        layout.addLayout(buttons)
        self._set_hint("")
        self._show_busy("Checking the GitHub login…")

    @staticmethod
    def _button(text: str, slot: Callable[[], object]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    def refresh(self) -> None:
        config = self._current_config()
        self._show_busy("Checking the GitHub login…")
        run_in_background(lambda: load_github_state(config), self._on_state, self._on_failed)

    def log_in(self) -> None:
        if self.state is None or self.state.gh is None:
            return
        host = self.state.host
        if host != DEFAULT_HOST:
            shown = ascii_host(host)  # a lookalike host shows as xn--…
            if not messages.confirm(self, f"Log in to {shown}?", NOT_GITHUB_COM.format(host=shown)):
                return
        GitHubLoginDialog(self.state.gh, host, self).exec()
        self.refresh()

    def use_for_git(self) -> None:
        if self.state is None or self.state.gh is None:
            return
        gh, host = self.state.gh, self.state.host
        self._show_busy("Setting up git to use this login…")
        run_in_background(lambda: setup_git(gh, host), lambda _result: self._after_setup(), self._on_failed)

    def _after_setup(self) -> None:
        if shiboken6.isValid(self):
            self.refresh()

    def _on_state(self, state: GitHubState) -> None:
        if not shiboken6.isValid(self):
            return  # Settings was closed while gh was still running
        self.state = state
        self.check_button.setEnabled(True)
        self.login_button.setEnabled(state.gh is not None)
        self.setup_git_button.setEnabled(state.gh is not None)
        self.setup_git_button.setVisible(False)
        if state.gh is None:
            self.status.setText("The GitHub CLI (gh) is not installed.")
            self._set_hint(INSTALL_HINT)
            return
        if state.status is None:
            self.status.setText(f"Could not check the GitHub login: {state.error}")
            self._set_hint("")
            return
        status = state.status
        self.status.setText(status.describe())
        self.login_button.setText("Log in again…" if status.login else "Log in with GitHub…")
        self.setup_git_button.setVisible(status.logged_in and not state.git_uses_gh)
        if state.ssh_remote:
            self._set_hint("The remote uses SSH, so git uses your SSH key and does not need this login.")
        elif status.logged_in and not state.git_uses_gh:
            self._set_hint("git does not use this login yet.")
        elif status.logged_in:
            self._set_hint(f"git fetch and push to https://{ascii_host(state.host)} use this login.")
        else:
            self._set_hint("Log in so git can fetch and push tags over HTTPS without a password prompt (gh auth login).")

    def _set_hint(self, text: str) -> None:
        self.hint.setText(text)
        self.hint.setVisible(bool(text))  # an empty label would still take a line

    def _on_failed(self, exc: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self.status.setText(f"Could not check the GitHub login: {exc}")
        self.check_button.setEnabled(True)
        self.login_button.setEnabled(self.state is not None and self.state.gh is not None)

    def _show_busy(self, message: str) -> None:
        self.status.setText(message)
        for button in (self.login_button, self.setup_git_button, self.check_button):
            button.setEnabled(False)
