"""Next release: move the checked branches to the version after their current one (mkdev 3.26 → 3.27)."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from ..config import BranchVersion, next_version
from .style import error_label, secondary


class NextReleaseDialog(QDialog):
    def __init__(self, values: list[BranchVersion], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Next release")
        self._values = list(values)
        self.checks: list[QCheckBox] = []
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Move these branches to their next version:"))
        for item in self._values:
            new = next_version(item.marker) if item.marker else None
            if not item.marker:
                check = QCheckBox(f"{item.branch}: no version yet")
            elif new is None:
                check = QCheckBox(f"{item.branch}: {item.marker} (no number to increase)")
            else:
                check = QCheckBox(f"{item.branch}: {item.marker} → {new}")
                check.setChecked(True)
            check.setEnabled(new is not None)
            check.toggled.connect(lambda _checked: self._check_clashes())
            self.checks.append(check)
            layout.addWidget(check)
        self.error = error_label()
        layout.addWidget(self.error)
        layout.addWidget(
            secondary(QLabel("Tags do not move now: tag each branch from the menu when it is ready. Save keeps the new versions."))
        )
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Move versions")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._check_clashes()

    def result_values(self) -> list[BranchVersion]:
        return [
            BranchVersion(item.branch, next_version(item.marker) or item.marker) if check.isChecked() else item
            for item, check in zip(self._values, self.checks)
        ]

    def _check_clashes(self) -> None:
        owners: dict[str, list[str]] = {}
        for item in self.result_values():
            if item.marker:
                owners.setdefault(item.marker, []).append(item.branch)
        clashes = [
            f"{marker} would be the version of {' and '.join(branches)}"
            for marker, branches in owners.items()
            if len(branches) > 1
        ]
        self.error.setText("\n".join(clashes))
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(not clashes and any(check.isChecked() for check in self.checks))
