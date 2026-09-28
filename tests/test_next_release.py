from PySide6.QtWidgets import QDialogButtonBox

from git_version_tagger.config import BranchVersion
from git_version_tagger.ui.next_release import NextReleaseDialog


def make_dialog(qtbot, values) -> NextReleaseDialog:
    dialog = NextReleaseDialog(values)
    qtbot.addWidget(dialog)
    return dialog


def ok_enabled(dialog) -> bool:
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_every_branch_moves_to_its_next_version_by_default(qtbot):
    dialog = make_dialog(qtbot, [BranchVersion("mkdev", "3.26"), BranchVersion("mkdev-rc", "3.25")])
    assert [check.text() for check in dialog.checks] == ["mkdev: 3.26 → 3.27", "mkdev-rc: 3.25 → 3.26"]
    assert dialog.result_values() == [BranchVersion("mkdev", "3.27"), BranchVersion("mkdev-rc", "3.26")]
    assert ok_enabled(dialog)


def test_an_unchecked_branch_keeps_its_version(qtbot):
    values = [BranchVersion("mkdev", "3.26"), BranchVersion("mkdev-rc", "3.25"), BranchVersion("mkdev-react", "3.0-react")]
    dialog = make_dialog(qtbot, values)
    dialog.checks[2].setChecked(False)
    assert dialog.result_values()[2] == BranchVersion("mkdev-react", "3.0-react")


def test_moving_only_some_branches_cannot_give_two_branches_one_version(qtbot):
    dialog = make_dialog(qtbot, [BranchVersion("mkdev", "3.26"), BranchVersion("mkdev-rc", "3.25")])
    dialog.checks[0].setChecked(False)  # mkdev-rc 3.25 → 3.26, which mkdev keeps
    assert dialog.error.text() == "3.26 would be the version of mkdev and mkdev-rc"
    assert not ok_enabled(dialog)
    dialog.checks[0].setChecked(True)
    assert dialog.error.text() == ""
    assert ok_enabled(dialog)


def test_branches_without_a_number_or_version_cannot_move(qtbot):
    dialog = make_dialog(qtbot, [BranchVersion("preview", "beta"), BranchVersion("hotfix", "")])
    assert [check.isEnabled() for check in dialog.checks] == [False, False]
    assert dialog.checks[0].text() == "preview: beta (no number to increase)"
    assert dialog.checks[1].text() == "hotfix: no version yet"
    assert not ok_enabled(dialog)
    assert dialog.result_values() == [BranchVersion("preview", "beta"), BranchVersion("hotfix", "")]
