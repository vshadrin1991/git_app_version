"""One look for the app's windows: form layout, field height, spacing, secondary and error text."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

FIELD_HEIGHT = 28  # Qt's QLineEdit is 21 px next to 32 px macOS push buttons; this evens the rows out
SPACING = 8
MARGINS = (20, 16, 20, 16)
ERROR_COLOR = "#c0392b"


def form_layout(parent: QWidget) -> QFormLayout:
    """Label: field rows whose fields fill the width (the macOS default keeps them at their ~125 px hint)."""
    form = QFormLayout(parent)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.setContentsMargins(*MARGINS)
    return form


def line_edit(text: str = "", placeholder: str = "") -> QLineEdit:
    edit = QLineEdit(text)
    edit.setPlaceholderText(placeholder)
    edit.setMinimumHeight(FIELD_HEIGHT)
    return edit


def row(*widgets: QWidget) -> QWidget:
    """Widgets side by side in one form field; the first one stretches. A container widget (not a bare
    layout) keeps the row's label vertically centred."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SPACING)
    for index, widget in enumerate(widgets):
        layout.addWidget(widget, 1 if index == 0 else 0)
    return container


def column(*widgets: QWidget, spacing: int = 4) -> QWidget:
    """Widgets stacked in one form field, e.g. a field and the example under it."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    return container


def plain(label: QLabel) -> QLabel:
    """Show the text literally (see ui/messages.py for why)."""
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def secondary(label: QLabel) -> QLabel:
    """Smaller, dimmer text for examples and hints."""
    font = label.font()
    if font.pointSizeF() > 4:  # a pixel-sized font reports -1: leave it alone
        font.setPointSizeF(font.pointSizeF() - 2)
        label.setFont(font)
    label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
    label.setWordWrap(True)
    plain(label)
    return label


def error_label() -> QLabel:
    label = QLabel()
    label.setStyleSheet(f"color: {ERROR_COLOR}")
    label.setWordWrap(True)
    return plain(label)
