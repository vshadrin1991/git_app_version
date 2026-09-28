import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFormLayout, QInputDialog

from git_version_tagger.config import BranchVersion
from git_version_tagger.git_runner import GitError
from git_version_tagger.github_auth import LOGIN_HINT
from git_version_tagger.tagger import Tagger
from git_version_tagger.ui import messages
from git_version_tagger.ui.next_release import NextReleaseDialog
from git_version_tagger.ui.settings_dialog import SettingsDialog
from git_version_tagger.ui.style import FIELD_HEIGHT
from helpers import git


@pytest.fixture
def warnings(monkeypatch):
    shown = []
    monkeypatch.setattr(messages, "warning", lambda parent, title, text: shown.append(text))
    return shown


def make_dialog(qtbot, config) -> SettingsDialog:
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)
    return dialog


def accepted_after_save(dialog) -> bool:
    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))
    dialog.accept()
    return accepted == [True]


def test_dialog_shows_and_returns_the_config(qtbot, config):
    config.launch_at_login = True
    config.git_executable = "/usr/bin/git"
    assert make_dialog(qtbot, config).current_config() == config


def test_save_with_valid_settings_accepts(qtbot, config, warnings):
    assert accepted_after_save(make_dialog(qtbot, config))
    assert warnings == []


def test_save_rejects_folder_that_is_not_a_repository(qtbot, config, tmp_path, warnings):
    plain = tmp_path / "plain"
    plain.mkdir()
    config.project_path = str(plain)
    assert not accepted_after_save(make_dialog(qtbot, config))
    assert "not a git repository" in warnings[0]


def test_save_rejects_a_branch_without_version(qtbot, config, warnings):
    config.branch_versions = [BranchVersion("mkdev")]
    assert not accepted_after_save(make_dialog(qtbot, config))
    assert "Choose the version for mkdev in Settings" in warnings[0]


def test_template_preview(qtbot, config):
    dialog = make_dialog(qtbot, config)
    assert dialog.template_preview.text() == "Example: 3.25-#a1b2c3d"
    dialog.tag_template.setText("v{marker}")
    assert "must contain" in dialog.template_preview.text()


def pick_first(offered):
    def fake_get_item(parent, title, label, items, current=0, editable=True):
        offered.append(list(items))
        return items[0], True

    return fake_get_item


def push_tags(repos, *tags):
    for tag in tags:
        git(repos.other, "tag", tag)
        git(repos.other, "push", "origin", tag)


def test_general_tab_shows_the_github_login(qtbot, config, fake_gh, monkeypatch):
    status = {"hosts": {"github.com": [{"login": "octocat", "active": True, "state": "success"}]}}
    monkeypatch.setenv("FAKE_GH_STATUS", json.dumps(status))
    dialog = make_dialog(qtbot, config)
    qtbot.waitUntil(lambda: dialog.github.status.text() == "Logged in to github.com as octocat", timeout=15000)


def test_general_fields_fill_the_width(qtbot, config):
    dialog = make_dialog(qtbot, config)
    assert dialog.general_form.fieldGrowthPolicy() == QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
    dialog.show()
    qtbot.waitExposed(dialog)
    assert dialog.remote.width() > 300  # the macOS default kept fields at ~125 px


def test_text_fields_share_one_height(qtbot, config):
    dialog = make_dialog(qtbot, config)
    for field in (dialog.project_path, dialog.remote, dialog.git_executable, dialog.tag_template):
        assert field.minimumHeight() == FIELD_HEIGHT


def test_example_and_hint_are_secondary_text(qtbot, config):
    dialog = make_dialog(qtbot, config)
    for label in (dialog.template_preview, dialog.github.hint):
        assert label.foregroundRole() == QPalette.ColorRole.PlaceholderText
        assert label.font().pointSizeF() < dialog.remote.font().pointSizeF()


def test_github_row_lines_up_with_the_other_fields(qtbot, config):
    dialog = make_dialog(qtbot, config)
    assert dialog.general_form.labelForField(dialog.github).text() == "GitHub:"


def test_tabs_are_general_and_branches(qtbot, config):
    dialog = make_dialog(qtbot, config)
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["General", "Branches"]
    assert dialog.branch_table.values() == config.branch_versions
    assert dialog.tabs.currentIndex() == 0


def test_branches_tab_opens_first_when_a_branch_has_no_version(qtbot, config):
    config.branch_versions.append(BranchVersion("hotfix"))
    assert make_dialog(qtbot, config).tabs.currentIndex() == 1


def test_import_branch_adds_it_without_a_version(qtbot, config, monkeypatch):
    offered = []
    monkeypatch.setattr(QInputDialog, "getItem", pick_first(offered))
    dialog = make_dialog(qtbot, config)
    dialog.import_branch_button.click()
    qtbot.waitUntil(lambda: "main" in dialog.branch_table.branches(), timeout=15000)
    assert offered == [["main"]]
    assert dialog.branch_table.values()[-1] == BranchVersion("main", "")


def select_branch(dialog, row: int) -> None:
    dialog.branch_table.table.selectRow(row)


def test_version_from_remote_sets_the_selected_branch(qtbot, config, repos, monkeypatch):
    push_tags(repos, "3.26-#abcdef1", "3.25-#abcdef2")
    offered = []
    monkeypatch.setattr(QInputDialog, "getItem", pick_first(offered))
    dialog = make_dialog(qtbot, config)
    select_branch(dialog, 0)  # mkdev → 3.25
    dialog.version_from_remote_button.click()
    qtbot.waitUntil(lambda: dialog.branch_table.values()[0].marker == "3.26", timeout=15000)
    assert offered == [["3.26"]]  # 3.25 and 3.24 already belong to branches
    assert dialog.version_from_remote_button.text() == "Version from remote…"
    assert dialog.version_from_remote_button.isEnabled()


def test_version_from_remote_uses_the_tag_format_being_edited(qtbot, config, repos, monkeypatch):
    push_tags(repos, "v4.0+abcdef1", "3.26-#abcdef2")
    offered = []
    monkeypatch.setattr(QInputDialog, "getItem", pick_first(offered))
    dialog = make_dialog(qtbot, config)
    dialog.tag_template.setText("v{marker}+{hash}")  # not saved yet
    select_branch(dialog, 0)
    dialog.version_from_remote_button.click()
    qtbot.waitUntil(lambda: dialog.branch_table.values()[0].marker == "4.0", timeout=15000)
    assert offered == [["4.0"]]


def test_version_from_remote_needs_a_selected_branch(qtbot, config, monkeypatch):
    infos = []
    monkeypatch.setattr(messages, "information", lambda parent, title, text: infos.append(text))
    dialog = make_dialog(qtbot, config)
    dialog.version_from_remote_button.click()
    assert infos == ["Select a branch first."]


def test_version_from_remote_says_when_the_remote_has_none(qtbot, config, monkeypatch):
    infos = []
    monkeypatch.setattr(messages, "information", lambda parent, title, text: infos.append(text))
    dialog = make_dialog(qtbot, config)
    select_branch(dialog, 0)
    dialog.version_from_remote_button.click()
    qtbot.waitUntil(lambda: bool(infos), timeout=15000)
    assert infos == ["No versions found on the remote."]


def test_version_from_remote_with_a_broken_tag_format_warns(qtbot, config, warnings):
    dialog = make_dialog(qtbot, config)
    dialog.tag_template.setText("v{marker}")
    select_branch(dialog, 0)
    dialog.version_from_remote_button.click()
    qtbot.waitUntil(lambda: bool(warnings), timeout=15000)
    assert "must contain" in warnings[0]
    assert dialog.version_from_remote_button.isEnabled()


def test_version_for_a_branch_removed_meanwhile_is_dropped(qtbot, config, repos, monkeypatch):
    push_tags(repos, "3.26-#abcdef1")
    dialog = make_dialog(qtbot, config)

    def remove_mkdev_then_pick(parent, title, label, items, current=0, editable=True):
        select_branch(dialog, 0)
        dialog.branch_table.remove_button.click()  # the user removed mkdev before the answer arrived
        return items[0], True

    monkeypatch.setattr(QInputDialog, "getItem", remove_mkdev_then_pick)
    select_branch(dialog, 0)
    dialog.version_from_remote_button.click()
    qtbot.waitUntil(dialog.version_from_remote_button.isEnabled, timeout=15000)
    assert dialog.branch_table.values() == [BranchVersion("mkdev-rc", "3.24")]


def test_remote_credential_failure_points_to_the_github_login(qtbot, config, warnings, monkeypatch):
    def fail(self):
        raise GitError(["fetch"], 128, "fatal: could not read Username for 'https://github.com': terminal prompts disabled")

    monkeypatch.setattr(Tagger, "remote_markers", fail)
    dialog = make_dialog(qtbot, config)
    select_branch(dialog, 0)
    dialog.version_from_remote_button.click()
    qtbot.waitUntil(lambda: bool(warnings), timeout=15000)
    assert warnings[0].endswith(LOGIN_HINT)


def test_next_release_moves_the_versions_in_the_table(qtbot, config, monkeypatch):
    monkeypatch.setattr(NextReleaseDialog, "exec", lambda self: 1)
    dialog = make_dialog(qtbot, config)
    dialog.next_release_button.click()
    assert dialog.branch_table.values() == [BranchVersion("mkdev", "3.26"), BranchVersion("mkdev-rc", "3.25")]


def test_cancelled_next_release_changes_nothing(qtbot, config, monkeypatch):
    monkeypatch.setattr(NextReleaseDialog, "exec", lambda self: 0)
    dialog = make_dialog(qtbot, config)
    dialog.next_release_button.click()
    assert dialog.branch_table.values() == config.branch_versions


def test_labels_with_outside_text_are_plain(qtbot, config):
    dialog = make_dialog(qtbot, config)
    for label in (dialog.github.status, dialog.github.hint, dialog.template_preview, dialog.branch_table.error_label):
        assert label.textFormat() == Qt.TextFormat.PlainText
