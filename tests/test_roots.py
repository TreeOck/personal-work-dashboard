"""1.0.3: the page is built by `scan` and by `tracker` when missing; several root folders."""
import json

import pytest

from personal_tracker import cli, config, locate, server
from test_branches import commit, g, new_repo


def _cfg(sandbox, **kw):
    path = sandbox.dir / "config.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.update(kw)
    path.write_text(json.dumps(cfg), encoding="utf-8")


def test_scan_builds_the_page(sandbox):
    (sandbox.dir / "commits.json").unlink()
    assert not (sandbox.dir / "dashboard.html").exists()
    r = sandbox("scan")
    assert r.returncode == 0, r.stderr
    assert (sandbox.dir / "dashboard.html").exists()


def test_page_after_rescan_shows_the_new_commits(sandbox):
    repo = new_repo(sandbox.root / "proj" / "app")
    assert sandbox("scan").returncode == 0
    commit(repo, "a new one")
    assert sandbox("scan").returncode == 0
    data = json.loads((sandbox.dir / "dev-data.json").read_text(encoding="utf-8"))
    assert len(data["commits"]) == 2


def test_open_builds_a_missing_page(sandbox, monkeypatch):
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    opened = []
    monkeypatch.setattr(server, "ensure", lambda: 47999)
    monkeypatch.setattr(server.webbrowser, "open", opened.append)
    assert not (sandbox.dir / "dashboard.html").exists()
    assert cli.main([]) == 0
    assert (sandbox.dir / "dashboard.html").exists() and opened == ["http://127.0.0.1:47999/"]


def test_config_reads_root_or_roots(sandbox, monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    assert config.load().roots == [sandbox.root]
    a, b = tmp_path / "a", tmp_path / "b"
    _cfg(sandbox, root=None, roots=[str(a), str(b)])
    assert config.load().roots == [a, b]
    _cfg(sandbox, roots=[])
    with pytest.raises(config.TrackerError, match="root"):
        config.load()


def test_init_takes_several_roots(sandbox, tmp_path):
    (sandbox.dir / "config.json").unlink()
    a, b = tmp_path / "work", tmp_path / "OneDrive" / "Work"
    a.mkdir(); b.mkdir(parents=True)
    r = sandbox("init", "--root", str(a), "--root", str(b), "--email", "me@example.com", "--no-summariser")
    assert r.returncode == 0, r.stderr
    cfg = json.loads((sandbox.dir / "config.json").read_text(encoding="utf-8"))
    assert cfg["roots"] == [str(a), str(b)] and "root" not in cfg
    (sandbox.dir / "config.json").unlink()
    assert sandbox("init", "--root", str(a), "--email", "me@example.com", "--no-summariser").returncode == 0
    assert json.loads((sandbox.dir / "config.json").read_text(encoding="utf-8"))["root"] == str(a)   # one root: as before


def test_scan_covers_every_root_once(sandbox, tmp_path):
    second = tmp_path / "OneDrive" / "Work"
    commit(new_repo(sandbox.root / "alpha" / "alpha-be"), "in the first root")
    commit(new_repo(second / "beta" / "beta-app"), "in the second root")
    _cfg(sandbox, root=None, roots=[str(sandbox.root), str(second), str(second / "beta")])   # last one overlaps
    assert sandbox("scan").returncode == 0, sandbox("scan").stderr
    commits = json.loads((sandbox.dir / "commits.json").read_text(encoding="utf-8"))["commits"]
    assert sorted({(c["project"], c["repo_path"]) for c in commits}) == [("alpha", "alpha/alpha-be"), ("beta", "beta/beta-app")]
    assert len(commits) == 4   # base + one commit per repo, nothing counted twice


def test_locate_with_several_roots(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    repo = new_repo(b / "proj" / "app")
    assert locate.project_repo_for(repo, [a, b]) == ("proj", "app")
    assert locate.project_repo_for(tmp_path / "elsewhere", [a, b]) == (None, None)
    assert locate.repo_folder([a, b], "proj", "app") == repo
    g(repo, "checkout", "-q", "-b", "feat/x")
    assert locate.current_branch(repo, [a, b]) == ("proj/app", "feat/x")


def test_add_path_in_the_second_root(sandbox, tmp_path):
    second = tmp_path / "OneDrive" / "Work"
    repo = new_repo(second / "beta" / "beta-app")
    _cfg(sandbox, root=None, roots=[str(sandbox.root), str(second)])
    assert sandbox("add", "T", "--path", str(repo)).returncode == 0
    (it,) = sandbox.items()
    assert (it["project"], it["repo"]) == ("beta", "beta-app")
