import os

import pytest

from personal_tracker.locate import project_repo_for


def _repo(path):
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    return path


def test_project_repo_for_simple(tmp_path):
    root = tmp_path / "root"
    repo = _repo(root / "dms" / "dms-be")
    (repo / "src").mkdir()
    assert project_repo_for(repo / "src", root) == ("dms", "dms-be")
    assert project_repo_for(str(root / "dms"), root) == ("dms", None)


def test_project_repo_for_edge_paths(tmp_path):
    root = tmp_path / "my repos"
    repo = _repo(root / "प्रोजेक्ट" / "app")
    assert project_repo_for(repo, root) == ("प्रोजेक्ट", "app")
    link = tmp_path / "shortcut"
    try:
        os.symlink(repo, link, target_is_directory=True)
    except OSError:   # Windows without symlink rights
        pytest.skip("symlinks not available")
    assert project_repo_for(link, root) == ("प्रोजेक्ट", "app")
    assert project_repo_for(tmp_path / "elsewhere", root) == (None, None)
    assert project_repo_for(root, root) == (None, None)
    assert project_repo_for(root / "newproj" / "not-yet", root) == ("newproj", None)


def test_project_repo_for_ignores_repos_deeper_than_the_scanner(tmp_path):
    root = tmp_path / "root"
    deep = _repo(root / "a" / "b" / "c" / "d")
    assert project_repo_for(deep, root) == ("a", None)


def test_cli_add_with_path(sandbox):
    _repo(sandbox.root / "alpha" / "alpha-be")
    assert sandbox("add", "T", "--path", str(sandbox.root / "alpha" / "alpha-be")).returncode == 0
    assert sandbox("add", "U", "-p", "beta", "--path", str(sandbox.root / "alpha" / "alpha-be")).returncode == 0
    a, b = sandbox.items()
    assert (a["project"], a["repo"]) == ("alpha", "alpha-be")
    assert (b["project"], b["repo"]) == ("beta", "alpha-be")
