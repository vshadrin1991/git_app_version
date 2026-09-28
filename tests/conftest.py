import os
import sys

# Qt widgets in tests render off-screen (used from Task 7 on; harmless before that).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from git_version_tagger.config import AppConfig, BranchVersion  # noqa: E402
from git_version_tagger.tagger import Tagger, make_tagger  # noqa: E402
from helpers import FAKE_GH_SCRIPT, FakeGh, Repos, git  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_git_env(tmp_path_factory, monkeypatch):
    """Keep the developer's ~/.gitconfig (signing, hooks, aliases) out of the tests."""
    home = tmp_path_factory.mktemp("home")
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repos(tmp_path) -> Repos:
    """origin.git has branches main, trunk and trunk-rc; project/ and other/ are clones of it."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", str(origin), str(seed))
    (seed / "file.txt").write_text("initial")
    git(seed, "add", "file.txt")
    git(seed, "commit", "-m", "initial")
    git(seed, "push", "origin", "main")
    for branch in ("trunk", "trunk-rc"):
        git(seed, "push", "origin", f"main:refs/heads/{branch}")
    project = tmp_path / "project"
    git(tmp_path, "clone", str(origin), str(project))
    other = tmp_path / "other"
    git(tmp_path, "clone", str(origin), str(other))
    return Repos(origin=origin, project=project, other=other)


@pytest.fixture
def config(repos) -> AppConfig:
    return AppConfig(
        project_path=str(repos.project),
        branch_versions=[BranchVersion("trunk", "3.25"), BranchVersion("trunk-rc", "3.24")],
    )


@pytest.fixture
def tagger(config) -> Tagger:
    return make_tagger(config)


@pytest.fixture(autouse=True)
def isolated_gh_env(tmp_path_factory, monkeypatch):
    """Keep the developer's GitHub login out of the tests: a real gh (if installed) sees no accounts."""
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path_factory.mktemp("gh-config")))
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fake_gh(tmp_path, monkeypatch) -> FakeGh:
    """A fake `gh` first on PATH; helpers.FAKE_GH_SCRIPT lists its FAKE_GH_* switches."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    script = bin_dir / "gh"
    script.write_text(f"#!{sys.executable}\n{FAKE_GH_SCRIPT}", encoding="utf-8")
    script.chmod(0o755)
    calls = tmp_path / "gh-calls.log"
    monkeypatch.setenv("FAKE_GH_LOG", str(calls))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return FakeGh(path=script, calls_file=calls)
