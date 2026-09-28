from git_version_tagger.config import BranchVersion
from git_version_tagger.ui.branch_table import VERSION, BranchTable

PAIRS = [BranchVersion("mkdev", "3.26"), BranchVersion("mkdev-rc", "3.25")]


def make_table(qtbot, values=PAIRS) -> BranchTable:
    table = BranchTable()
    qtbot.addWidget(table)
    table.set_values(list(values))
    return table


def test_values_round_trip(qtbot):
    table = make_table(qtbot)
    assert table.values() == PAIRS
    assert table.branches() == ["mkdev", "mkdev-rc"]
    assert table.versions() == ["3.26", "3.25"]
    assert table.selected_branch() is None


def test_add_from_the_inputs(qtbot):
    table = make_table(qtbot)
    table.branch_input.setText("mkdev-react")
    table.version_input.setText("3.0-react")
    table.version_input.returnPressed.emit()
    assert table.values()[-1] == BranchVersion("mkdev-react", "3.0-react")
    assert table.branch_input.text() == "" and table.version_input.text() == ""
    assert table.selected_branch() == "mkdev-react"


def test_a_branch_may_wait_for_its_version(qtbot):
    table = make_table(qtbot)
    assert table.add("hotfix")
    assert table.values()[-1] == BranchVersion("hotfix", "")


def test_add_rejects_bad_or_duplicate_values(qtbot):
    table = make_table(qtbot)
    assert not table.add("mk dev", "3.27")
    assert "Invalid branch name" in table.error_label.text()
    assert not table.add("mkdev", "3.27")
    assert table.error_label.text() == "Branch 'mkdev' is already in the list"
    assert not table.add("hotfix", "3.25")
    assert table.error_label.text() == "3.25 is already the version of mkdev-rc"
    assert not table.add("hotfix", "3 25")
    assert "Invalid marker" in table.error_label.text()
    assert table.values() == PAIRS


def test_invalid_edit_goes_back_to_the_last_good_text(qtbot):
    table = make_table(qtbot)
    table.table.item(0, VERSION).setText("3.25")  # mkdev-rc's version
    assert table.values()[0] == BranchVersion("mkdev", "3.26")
    assert table.error_label.text() == "3.25 is already the version of mkdev-rc"
    table.table.item(0, VERSION).setText(" 3.27 ")
    assert table.values()[0] == BranchVersion("mkdev", "3.27")
    assert table.error_label.text() == ""


def test_set_version_by_branch_name(qtbot):
    table = make_table(qtbot)
    assert table.set_version("mkdev-rc", "3.24")
    assert not table.set_version("mkdev-rc", "3.26")  # mkdev's version
    assert not table.set_version("gone", "3.30")
    assert table.values() == [BranchVersion("mkdev", "3.26"), BranchVersion("mkdev-rc", "3.24")]


def test_move_and_remove(qtbot):
    table = make_table(qtbot)
    table.table.selectRow(1)
    table.up_button.click()
    assert table.branches() == ["mkdev-rc", "mkdev"]
    assert table.selected_branch() == "mkdev-rc"
    table.down_button.click()
    assert table.branches() == ["mkdev", "mkdev-rc"]
    table.remove_button.click()
    assert table.values() == [BranchVersion("mkdev", "3.26")]
