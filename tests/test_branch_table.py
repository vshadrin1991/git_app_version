from git_version_tagger.config import BranchVersion
from git_version_tagger.ui.branch_table import BRANCH, VERSION, BranchTable

PAIRS = [BranchVersion("trunk", "3.26"), BranchVersion("trunk-rc", "3.25")]


def make_table(qtbot, values=PAIRS) -> BranchTable:
    table = BranchTable()
    qtbot.addWidget(table)
    table.set_values(list(values))
    return table


def test_values_round_trip(qtbot):
    table = make_table(qtbot)
    assert table.values() == PAIRS
    assert table.branches() == ["trunk", "trunk-rc"]
    assert table.versions() == ["3.26", "3.25"]
    assert table.selected() is None


def test_add_from_the_inputs(qtbot):
    table = make_table(qtbot)
    table.branch_input.setText("trunk-react")
    table.version_input.setText("3.0-react")
    table.version_input.returnPressed.emit()
    assert table.values()[-1] == BranchVersion("trunk-react", "3.0-react")
    assert table.branch_input.text() == "" and table.version_input.text() == ""
    assert table.selected() == BranchVersion("trunk-react", "3.0-react")


def test_a_branch_may_wait_for_its_version(qtbot):
    table = make_table(qtbot)
    assert table.add("hotfix")
    assert table.values()[-1] == BranchVersion("hotfix", "")


def test_add_rejects_bad_or_duplicate_values(qtbot):
    table = make_table(qtbot)
    assert not table.add("mk dev", "3.27")
    assert "Invalid branch name" in table.error_label.text()
    assert not table.add("trunk", "3.26")
    assert table.error_label.text() == "trunk → 3.26 is already in the list"
    assert not table.add("hotfix", "3.25")
    assert table.error_label.text() == "3.25 is already the version of trunk-rc"
    assert not table.add("hotfix", "3 25")
    assert "Invalid marker" in table.error_label.text()
    assert table.values() == PAIRS


def test_a_branch_may_have_several_versions(qtbot):
    table = make_table(qtbot)
    assert table.add("trunk", "alt-1.55")
    assert table.error_label.text() == ""
    assert table.values()[-1] == BranchVersion("trunk", "alt-1.55")
    assert table.add("trunk")  # one more row, waiting for its version
    assert not table.add("trunk")
    assert table.error_label.text() == "trunk (no version) is already in the list"


def test_edits_that_would_repeat_a_record_go_back(qtbot):
    table = make_table(qtbot, PAIRS + [BranchVersion("trunk"), BranchVersion("hotfix")])
    table.table.item(3, BRANCH).setText("trunk")  # hotfix (no version) → trunk (no version): that is row 2
    assert table.values()[3] == BranchVersion("hotfix")
    assert table.error_label.text() == "trunk (no version) is already in the list"
    table.table.item(1, BRANCH).setText("trunk")  # trunk-rc → 3.25 becomes trunk → 3.25: a new record
    assert table.values()[1] == BranchVersion("trunk", "3.25")
    assert table.error_label.text() == ""
    table.table.item(1, VERSION).setText("")  # trunk (no version) is row 2 already
    assert table.values()[1] == BranchVersion("trunk", "3.25")
    assert table.error_label.text() == "trunk (no version) is already in the list"


def test_invalid_edit_goes_back_to_the_last_good_text(qtbot):
    table = make_table(qtbot)
    table.table.item(0, VERSION).setText("3.25")  # trunk-rc's version
    assert table.values()[0] == BranchVersion("trunk", "3.26")
    assert table.error_label.text() == "3.25 is already the version of trunk-rc"
    table.table.item(0, VERSION).setText(" 3.27 ")
    assert table.values()[0] == BranchVersion("trunk", "3.27")
    assert table.error_label.text() == ""


def test_set_version_finds_the_row_by_its_record(qtbot):
    table = make_table(qtbot, PAIRS + [BranchVersion("trunk", "alt-1.55")])
    assert table.set_version(BranchVersion("trunk", "alt-1.55"), "alt-1.56")
    assert not table.set_version(BranchVersion("trunk-rc", "3.25"), "3.26")  # trunk's version
    assert not table.set_version(BranchVersion("trunk", "3.20"), "3.30")  # no such row any more
    assert table.values() == [
        BranchVersion("trunk", "3.26"),
        BranchVersion("trunk-rc", "3.25"),
        BranchVersion("trunk", "alt-1.56"),
    ]


def test_move_and_remove(qtbot):
    table = make_table(qtbot)
    table.table.selectRow(1)
    table.up_button.click()
    assert table.branches() == ["trunk-rc", "trunk"]
    assert table.selected() == BranchVersion("trunk-rc", "3.25")
    table.down_button.click()
    assert table.branches() == ["trunk", "trunk-rc"]
    table.remove_button.click()
    assert table.values() == [BranchVersion("trunk", "3.26")]
