"""Message boxes and tooltips that show their text literally.

Errors quote git and gh, and git quotes the remote ("remote: ..."), so the text is not ours. Qt
renders text that looks like HTML as HTML, and QMessageBox opens its links, so text from outside
must never reach Qt as rich text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget


def message_box(icon: QMessageBox.Icon, title: str, text: str, parent: QWidget | None = None) -> QMessageBox:
    box = QMessageBox(icon, title, text, QMessageBox.StandardButton.Ok, parent)
    box.setTextFormat(Qt.TextFormat.PlainText)
    return box


def warning(parent: QWidget | None, title: str, text: str) -> None:
    message_box(QMessageBox.Icon.Warning, title, text, parent).exec()


def information(parent: QWidget | None, title: str, text: str) -> None:
    message_box(QMessageBox.Icon.Information, title, text, parent).exec()


def confirm_box(parent: QWidget | None, title: str, text: str) -> QMessageBox:
    box = message_box(QMessageBox.Icon.Question, title, text, parent)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box


def confirm(parent: QWidget | None, title: str, text: str) -> bool:
    box = confirm_box(parent, title, text)
    box.exec()
    return box.clickedButton() is box.button(QMessageBox.StandardButton.Yes)


def plain_tooltip(heading: str, text: str) -> str:
    """Tooltip text shown literally: Qt decides "is this HTML?" from the first line only, so a plain
    heading line keeps the rest literal (native macOS menus show tooltips as plain text anyway).
    Escaping "<" as "&lt;" would not work: Qt takes "&lt;" itself as a sign of HTML."""
    return f"{heading}\n{text}"


def no_markup(text: str) -> str:
    """For desktop notifications: some Linux notification servers render markup in the message."""
    return text.replace("<", "‹").replace(">", "›")
