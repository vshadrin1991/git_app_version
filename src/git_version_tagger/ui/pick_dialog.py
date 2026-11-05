"""Pick one value from a long list: a search field filters it as you type (remotes have hundreds of branches)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QVBoxLayout, QWidget

from .style import SPACING, line_edit, secondary

# Keys that the search field passes on to the list, so they move the selection instead of the text cursor.
_LIST_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)


class PickDialog(QDialog):
    def __init__(self, title: str, label: str, values: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 420)
        self._folded = [value.casefold() for value in values]  # what the search matches against
        self.search = line_edit(placeholder="Search…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _text: self._filter())
        self.search.installEventFilter(self)  # ↑/↓ in the search field move through the list
        self.list = QListWidget()
        self.list.setUniformItemSizes(True)  # one row height: filtering thousands of rows needs no re-measuring
        self.list.addItems(values)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        self.list.currentItemChanged.connect(lambda _current, _previous: self._update_ok())
        self.count = secondary(QLabel())
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING)
        layout.addWidget(QLabel(label))
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        layout.addWidget(self.count)
        layout.addWidget(self.buttons)
        self._filter()
        self.search.setFocus()

    def value(self) -> str | None:
        item = self.list.currentItem()  # never a hidden row: _filter moves it to the first match or clears it
        return item.text() if item is not None else None

    def visible_values(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count()) if not self.list.item(i).isHidden()]

    def accept(self) -> None:
        if self.value() is not None:
            super().accept()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress and event.key() in _LIST_KEYS:
            self.list.event(event)
            return True
        return super().eventFilter(watched, event)

    def _filter(self) -> None:
        words = self.search.text().casefold().split()
        first, shown = None, 0
        for i, folded in enumerate(self._folded):
            item = self.list.item(i)
            hidden = not all(word in folded for word in words)
            if item.isHidden() != hidden:
                item.setHidden(hidden)
            if not hidden:
                shown += 1
                if first is None:
                    first = item
        current = self.list.currentItem()
        if current is None or current.isHidden():
            self.list.setCurrentItem(first)  # None clears it: nothing matches
        total = len(self._folded)
        self.count.setText(f"{shown} of {total}" if words else f"{total} in all")
        self._update_ok()

    def _update_ok(self) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.value() is not None)


def pick(parent: QWidget | None, title: str, label: str, values: list[str]) -> str | None:
    dialog = PickDialog(title, label, values, parent)
    try:
        return dialog.value() if dialog.exec() else None
    finally:
        dialog.deleteLater()  # the parent would otherwise keep every closed dialog, and its list, until it closes
