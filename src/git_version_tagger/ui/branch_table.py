"""Settings → Branches: every branch and the one version it is tagged with (mkdev → 3.26)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import BranchVersion, validate_branch, validate_marker
from .style import SPACING, error_label, line_edit

BRANCH, VERSION = 0, 1
_LAST_GOOD = Qt.ItemDataRole.UserRole  # an invalid edit puts this text back


class BranchTable(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating = False  # set while the code (not the user) changes cells
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Branch", "Version"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_item_changed)
        self.branch_input = line_edit(placeholder="Branch, e.g. mkdev")
        self.version_input = line_edit(placeholder="Version, e.g. 3.26")
        for field in (self.branch_input, self.version_input):
            field.returnPressed.connect(self._add_from_inputs)
        self.error_label = error_label()
        self.remove_button = self._button("Remove", self._remove_selected)
        self.up_button = self._button("Move up", lambda: self._move(-1))
        self.down_button = self._button("Move down", lambda: self._move(1))

        side = QVBoxLayout()
        side.setSpacing(SPACING)
        for button in (self.remove_button, self.up_button, self.down_button):
            side.addWidget(button)
        side.addStretch()
        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.table, 1)
        body.addLayout(side)
        add_row = QHBoxLayout()
        add_row.setSpacing(SPACING)
        add_row.addWidget(self.branch_input, 1)
        add_row.addWidget(self.version_input, 1)
        add_row.addWidget(self._button("Add", self._add_from_inputs))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(body)
        layout.addLayout(add_row)
        layout.addWidget(self.error_label)

    @staticmethod
    def _button(text: str, slot: Callable[[], object]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    # ---- values -------------------------------------------------------------
    def values(self) -> list[BranchVersion]:
        return [BranchVersion(self._text(row, BRANCH), self._text(row, VERSION)) for row in range(self.table.rowCount())]

    def set_values(self, values: list[BranchVersion]) -> None:
        self._updating = True
        try:
            self.table.setRowCount(0)
            for item in values:
                self._append(item.branch, item.marker)
        finally:
            self._updating = False

    def branches(self) -> list[str]:
        return [item.branch for item in self.values()]

    def versions(self) -> list[str]:
        return [item.marker for item in self.values() if item.marker]

    def selected_branch(self) -> str | None:
        row = self.table.currentRow()
        return self._text(row, BRANCH) if row >= 0 else None

    def add(self, branch: str, marker: str = "") -> bool:
        branch, marker = branch.strip(), marker.strip()
        error = self._check(BRANCH, branch) or self._check(VERSION, marker)
        self.error_label.setText(error or "")
        if error:
            return False
        self._updating = True
        try:
            self._append(branch, marker)
        finally:
            self._updating = False
        self.table.selectRow(self.table.rowCount() - 1)
        return True

    def set_version(self, branch: str, marker: str) -> bool:
        """Set the version of `branch`, found by name because rows may have moved since the caller looked.

        False when the branch is gone or the version is invalid or taken (the error label says why).
        """
        row = next((r for r in range(self.table.rowCount()) if self._text(r, BRANCH) == branch), None)
        if row is None:
            return False
        self.table.item(row, VERSION).setText(marker)  # checked by _on_item_changed
        return self._text(row, VERSION) == marker.strip()

    # ---- editing ------------------------------------------------------------
    def _append(self, branch: str, marker: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, text in ((BRANCH, branch), (VERSION, marker)):
            item = QTableWidgetItem(text)
            item.setData(_LAST_GOOD, text)
            self.table.setItem(row, column, item)

    def _text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _check(self, column: int, text: str, row: int = -1) -> str | None:
        """Why `text` may not stand in `column` (ignoring `row` itself), or None."""
        owner = next((r for r in range(self.table.rowCount()) if r != row and self._text(r, column) == text), None)
        if column == BRANCH:
            if error := validate_branch(text):
                return error
            return f"Branch {text!r} is already in the list" if owner is not None else None
        if not text:
            return None  # a branch may wait for its version; Save asks for it
        if error := validate_marker(text):
            return error
        return f"{text} is already the version of {self._text(owner, BRANCH)}" if owner is not None else None

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        text = item.text().strip()
        error = self._check(item.column(), text, item.row())
        self._updating = True
        try:
            if error:
                item.setText(item.data(_LAST_GOOD))
            else:
                item.setText(text)
                item.setData(_LAST_GOOD, text)
        finally:
            self._updating = False
        self.error_label.setText(error or "")

    def _add_from_inputs(self) -> None:
        if self.add(self.branch_input.text(), self.version_input.text()):
            self.branch_input.clear()
            self.version_input.clear()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _move(self, delta: int) -> None:
        row = self.table.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.table.rowCount():
            return
        values = self.values()
        values[row], values[target] = values[target], values[row]
        self.set_values(values)
        self.table.selectRow(target)
