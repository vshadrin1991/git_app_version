"""Shows every git command the app runs, and the results."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from ..platform_support import bring_to_front


class _LogEmitter(QObject):
    message = Signal(str)


class QtLogHandler(logging.Handler):
    """Forwards log records from any thread to the UI thread through a Qt signal."""

    def __init__(self) -> None:
        super().__init__()
        self.emitter = _LogEmitter()
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.emitter.message.emit(self.format(record))


class LogWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Git Version Tagger — Log")
        self.resize(760, 420)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        copy_button = QPushButton("Copy all")
        copy_button.clicked.connect(lambda _checked=False: QGuiApplication.clipboard().setText(self.text.toPlainText()))
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(lambda _checked=False: self.text.clear())

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(copy_button)
        buttons.addWidget(clear_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        layout.addLayout(buttons)

    def append_line(self, line: str) -> None:
        self.text.appendPlainText(line)

    def show_and_raise(self) -> None:
        bring_to_front()
        self.show()
        self.raise_()
        self.activateWindow()
