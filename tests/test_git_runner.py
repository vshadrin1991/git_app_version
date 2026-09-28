import shutil
import subprocess

import pytest

from git_version_tagger import git_runner
from git_version_tagger.git_runner import DEFAULT_TIMEOUT, GitError, GitRunner, find_git
from helpers import git


def test_run_returns_stripped_stdout(tmp_path):
    git(tmp_path, "init")
    assert GitRunner(tmp_path).run("rev-parse", "--is-inside-work-tree") == "true"


def test_failure_raises_git_error_with_stderr(tmp_path):
    git(tmp_path, "init")
    with pytest.raises(GitError) as info:
        GitRunner(tmp_path).run("rev-parse", "--verify", "does-not-exist")
    assert info.value.command == ["rev-parse", "--verify", "does-not-exist"]
    assert info.value.returncode == 128
    assert "Needed a single revision" in info.value.stderr


def test_missing_git_executable_raises_git_error(tmp_path):
    with pytest.raises(GitError, match="cannot run"):
        GitRunner(tmp_path, git="/nonexistent/git").run("status")


def test_missing_repo_directory_raises_git_error(tmp_path):
    with pytest.raises(GitError, match="cannot run"):
        GitRunner(tmp_path / "missing").run("status")


def test_git_never_prompts_for_credentials(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert GitRunner(tmp_path).run("status") == "ok"
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["timeout"] == DEFAULT_TIMEOUT


def test_timeout_raises_git_error(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(GitError, match="timed out after 1s"):
        GitRunner(tmp_path, timeout=1).run("fetch")


def test_find_git_prefers_configured_path():
    assert find_git("/custom/git") == "/custom/git"


def test_find_git_uses_path(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git")
    assert find_git("") == "/usr/bin/git"


def test_find_git_checks_well_known_locations_when_path_is_minimal(tmp_path, monkeypatch):
    fake = tmp_path / "git"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(git_runner, "GIT_CANDIDATES", (str(tmp_path / "missing"), str(fake)))
    assert find_git("") == str(fake)
