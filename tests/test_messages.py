from PySide6.QtCore import Qt
from PySide6.QtGui import Qt as GuiQt
from PySide6.QtWidgets import QMessageBox

from git_version_tagger.ui import messages

EVIL = "git push failed: remote: <a href='https://evil.example/login'>Session expired - sign in again</a>"


def test_message_boxes_show_html_literally(qtbot):
    box = messages.message_box(QMessageBox.Icon.Warning, "Git Version Tagger", EVIL)
    qtbot.addWidget(box)
    assert box.textFormat() == Qt.TextFormat.PlainText
    assert box.text() == EVIL


def test_plain_tooltip_is_not_treated_as_html():
    assert GuiQt.mightBeRichText(EVIL)  # what Qt would do with the raw text
    tooltip = messages.plain_tooltip("Last error:", EVIL)
    assert not GuiQt.mightBeRichText(tooltip)
    assert tooltip.endswith(EVIL)


def test_no_markup_neutralises_angle_brackets():
    assert messages.no_markup("<b>x</b> & y") == "‹b›x‹/b› & y"


def click_on_exec(button):
    def exec_(box):
        box.button(button).click()
        return 0

    return exec_


def test_confirm_is_true_only_for_yes(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", click_on_exec(QMessageBox.StandardButton.Yes))
    assert messages.confirm(None, "Log in?", EVIL)
    monkeypatch.setattr(QMessageBox, "exec", click_on_exec(QMessageBox.StandardButton.No))
    assert not messages.confirm(None, "Log in?", EVIL)


def test_confirm_defaults_to_no_and_is_plain(qtbot):
    box = messages.confirm_box(None, "Log in?", EVIL)
    qtbot.addWidget(box)
    assert box.defaultButton() is box.button(QMessageBox.StandardButton.No)
    assert box.textFormat() == Qt.TextFormat.PlainText
