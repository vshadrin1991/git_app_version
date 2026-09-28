"""Settings: project, remote, tag format, GitHub login, and the versions of every branch."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, BranchVersion, validate_config, validate_template
from ..git_runner import GitError, find_git
from ..github_auth import explain_error
from ..tagger import Tagger, TaggerError, make_tagger, tag_name
from . import messages
from .branch_table import BranchTable
from .github_account import GitHubAccountBox
from .next_release import NextReleaseDialog
from .style import MARGINS, SPACING, column, form_layout, line_edit, row, secondary
from .worker import run_in_background

BRANCHES_HELP = (
    "One row per version: a branch can have several (trunk → 3.25, trunk → alt-1.55), a version belongs to "
    "one branch. After a release, click Next release… to move the versions on (trunk 3.26 → 3.27)."
)


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Git Version Tagger — Settings")
        self.resize(620, 480)

        # General tab
        self.project_path = line_edit(config.project_path)
        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda _checked=False: self._browse())
        self.remote = line_edit(config.remote)
        self.git_executable = line_edit(config.git_executable, f"auto: {find_git('')}")
        self.tag_template = line_edit(config.tag_template)
        self.template_preview = secondary(QLabel())
        self.tag_template.textChanged.connect(lambda _text: self._update_preview())
        self.launch_at_login = QCheckBox("Start Git Version Tagger when I log in")
        self.launch_at_login.setChecked(config.launch_at_login)
        self.github = GitHubAccountBox(self.current_config)

        general = QWidget()
        self.general_form = form = form_layout(general)
        form.addRow("Project folder:", row(self.project_path, browse))
        form.addRow("Remote:", self.remote)
        form.addRow("Git executable:", self.git_executable)
        form.addRow("Tag format:", column(self.tag_template, self.template_preview))
        form.addRow("", self.launch_at_login)
        form.addRow("GitHub:", self.github)

        # Branches tab
        self.branch_table = BranchTable()
        self.branch_table.set_values(config.branch_versions)
        self.import_branch_button = self._button("Import branch…", self._import_branch)
        self.import_branch_button.setToolTip("Add a row for a branch on the remote (again, for another version)")
        self.version_from_remote_button = self._button("Version from remote…", self._version_from_remote)
        self.version_from_remote_button.setToolTip("Set the selected branch's version from the remote's tags")
        self.branch_actions = QHBoxLayout()
        self.branch_actions.setSpacing(SPACING)
        self.branch_actions.addWidget(self.import_branch_button)
        self.branch_actions.addWidget(self.version_from_remote_button)
        self.branch_actions.addStretch()
        self.next_release_button = self._button("Next release…", self._next_release)
        self.branch_actions.addWidget(self.next_release_button)
        self.branches_help = secondary(QLabel(BRANCHES_HELP))
        branches_tab = QWidget()
        branches_layout = QVBoxLayout(branches_tab)
        branches_layout.setContentsMargins(*MARGINS)
        branches_layout.setSpacing(10)
        branches_layout.addWidget(self.branch_table)
        branches_layout.addLayout(self.branch_actions)
        branches_layout.addWidget(self.branches_help)

        self.tabs = QTabWidget()
        self.tabs.addTab(general, "General")
        self.tabs.addTab(branches_tab, "Branches")
        if any(not item.marker for item in config.branch_versions):
            self.tabs.setCurrentWidget(branches_tab)  # e.g. right after the upgrade from config version 1
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
        self._update_preview()
        self.github.refresh()  # after every field exists: the check reads the project folder and remote

    def current_config(self) -> AppConfig:
        path = self.project_path.text().strip()
        return AppConfig(
            project_path=str(Path(path).expanduser()) if path else "",
            remote=self.remote.text().strip(),
            git_executable=self.git_executable.text().strip(),
            tag_template=self.tag_template.text().strip(),
            branch_versions=self.branch_table.values(),
            launch_at_login=self.launch_at_login.isChecked(),
        )

    def accept(self) -> None:
        config = self.current_config()
        problems = validate_config(config)
        if not problems:
            try:
                make_tagger(config).check_repo()  # local only, fast: safe on the UI thread
            except (TaggerError, GitError) as exc:
                problems.append(str(exc))
        if problems:
            messages.warning(self, "Settings", "\n".join(problems))
            return
        super().accept()

    @staticmethod
    def _button(text: str, slot: Callable[[], object]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    def _browse(self) -> None:
        start = self.project_path.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose the project folder", start)
        if folder:
            self.project_path.setText(folder)
            self.github.refresh()  # the new project's remote may be on another host

    def _update_preview(self) -> None:
        template = self.tag_template.text().strip()
        error = validate_template(template)
        self.template_preview.setText(error or f"Example: {tag_name(template, '3.25', 'a1b2c3d')}")

    def _next_release(self) -> None:
        dialog = NextReleaseDialog(self.branch_table.values(), self)
        if dialog.exec():
            self.branch_table.set_values(dialog.result_values())  # kept when the user clicks Save

    # ---- values from the remote --------------------------------------------
    def _import_branch(self) -> None:
        self._load_from_remote(self.import_branch_button, Tagger.remote_branches, self._on_branches_loaded)

    def _on_branches_loaded(self, branches: list[str]) -> None:
        waiting = [item.branch for item in self.branch_table.values() if not item.marker]  # one such row per branch
        branch = self._pick("branch", "branches", branches, waiting)
        if branch:
            self.branch_table.add(branch)  # without a version: the user picks it next

    def _version_from_remote(self) -> None:
        selected = self.branch_table.selected()
        if selected is None:
            messages.information(self, "Version from remote", "Select a branch first.")
            return
        self._load_from_remote(
            self.version_from_remote_button,
            Tagger.remote_markers,
            lambda markers: self._on_versions_loaded(selected, markers),
        )

    def _on_versions_loaded(self, selected: BranchVersion, markers: list[str]) -> None:
        marker = self._pick("version", "versions", markers, self.branch_table.versions())
        if marker:
            self.branch_table.set_version(selected, marker)  # by branch and version: rows may have changed meanwhile

    def _load_from_remote(
        self, button: QPushButton, load: Callable[[Tagger], list[str]], on_loaded: Callable[[list[str]], None]
    ) -> None:
        config = self.current_config()  # includes unsaved edits, e.g. a new tag format
        text = button.text()
        button.setEnabled(False)
        button.setText("Loading…")

        def finish() -> None:
            button.setEnabled(True)
            button.setText(text)

        def done(values: list[str]) -> None:
            finish()
            on_loaded(values)

        def failed(exc: Exception) -> None:
            finish()
            messages.warning(self, "Git Version Tagger", explain_error(exc))

        run_in_background(lambda: load(make_tagger(config)), done, failed)

    def _pick(self, noun: str, nouns: str, values: list[str], taken: list[str]) -> str | None:
        candidates = [value for value in values if value not in taken]
        if not candidates:
            message = f"Every {noun} on the remote is already in the list." if values else f"No {nouns} found on the remote."
            messages.information(self, f"Import {nouns}", message)
            return None
        value, ok = QInputDialog.getItem(self, f"Import {noun}", f"{noun.capitalize()} on the remote:", candidates, 0, False)
        return value if ok and value else None
