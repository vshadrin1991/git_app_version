from PySide6.QtCore import Qt

from git_version_tagger.ui.pick_dialog import PickDialog
from helpers import ok_enabled

BRANCHES = ["main", "trunk", "trunk-rc", "cursor/distributor-test-stabilization-27e3", "feature/Distributor-ui"]


def make_dialog(qtbot, values=BRANCHES) -> PickDialog:
    dialog = PickDialog("Import branch", "Branch on the remote:", values)
    qtbot.addWidget(dialog)
    return dialog


def test_shows_every_value_and_selects_the_first(qtbot):
    dialog = make_dialog(qtbot)
    assert dialog.visible_values() == BRANCHES
    assert dialog.value() == "main"
    assert dialog.count.text() == "5 in all"
    assert ok_enabled(dialog)


def test_search_filters_ignoring_case_and_selects_the_first_match(qtbot):
    dialog = make_dialog(qtbot)
    dialog.search.setText("DISTRIBUTOR")
    assert dialog.visible_values() == ["cursor/distributor-test-stabilization-27e3", "feature/Distributor-ui"]
    assert dialog.value() == "cursor/distributor-test-stabilization-27e3"
    assert dialog.count.text() == "2 of 5"


def test_every_search_word_must_match(qtbot):
    dialog = make_dialog(qtbot)
    dialog.search.setText("distributor ui")
    assert dialog.visible_values() == ["feature/Distributor-ui"]


def test_no_match_disables_ok(qtbot):
    dialog = make_dialog(qtbot)
    dialog.search.setText("nothing-like-this")
    assert dialog.visible_values() == []
    assert dialog.value() is None
    assert not ok_enabled(dialog)
    dialog.accept()
    assert dialog.result() == 0


def test_arrow_keys_in_the_search_field_move_the_selection(qtbot):
    dialog = make_dialog(qtbot)
    dialog.show()
    dialog.search.setText("trunk")
    qtbot.keyClick(dialog.search, Qt.Key.Key_Down)
    assert dialog.value() == "trunk-rc"
    assert dialog.search.text() == "trunk"  # the key moved the list, not the cursor in the text


def test_enter_picks_the_selected_value(qtbot):
    dialog = make_dialog(qtbot)
    dialog.show()
    dialog.search.setText("rc")
    qtbot.keyClick(dialog.search, Qt.Key.Key_Return)
    assert dialog.result() == PickDialog.DialogCode.Accepted
    assert dialog.value() == "trunk-rc"
