import json
import shutil
import subprocess
import sys

import pytest

from conftest import REPO


@pytest.fixture
def site(tmp_path):
    for f in ("build.py", "links.py", "inks.py", "template.html"):
        shutil.copy(f"{REPO}/{f}", tmp_path / f)
    (tmp_path / "desk" / "src" / "data").mkdir(parents=True)
    shutil.copy(f"{REPO}/desk/src/data/inks.json", tmp_path / "desk/src/data/inks.json")
    (tmp_path / "commits.json").write_text(json.dumps({"generated_at": "2026-10-13T10:00:00+05:30", "since": "2026-10-01",
        "author_pattern": "me@example.com", "commits": [{"sha": "a" * 40, "date": "2026-10-12T10:00:00+05:30",
        "project": "alpha", "repo": "alpha-be", "repo_path": "alpha/alpha-be", "subject": "s", "body": "", "files": [], "ins": 1, "del": 0}]}))
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": []}))
    (tmp_path / "todo.json").write_text(json.dumps({"items": [{"id": "t-0001", "title": "x", "project": "beta", "repo": None,
        "status": "todo", "created_at": "2026-10-12T10:00:00+05:30", "updated_at": "2026-10-12T10:00:00+05:30",
        "started_at": None, "closed_at": None, "plan": None, "notes": []}]}))
    run = lambda: subprocess.run([sys.executable, str(tmp_path / "build.py")], capture_output=True, text=True)
    run.dir = tmp_path
    return run


def test_without_desk_template_only_dashboard_is_built(site):
    r = site()
    assert r.returncode == 0, r.stderr
    assert (site.dir / "dashboard.html").exists()
    assert not (site.dir / "desk.html").exists()
    assert "skipped desk" in r.stdout


def test_with_desk_template_both_pages_get_the_same_data(site):
    (site.dir / "desk-template.html").write_text("<script>window.__DESK_DATA__=/*__DATA__*/null;</script>")
    assert site().returncode == 0
    desk = (site.dir / "desk.html").read_text()
    blob = json.loads(desk.split("window.__DESK_DATA__=")[1].split(";</script>")[0])
    assert set(blob["inks"]) == {"alpha", "beta"}
    assert blob["inks"]["alpha"]["hex"].startswith("#")


def test_inks_are_persisted_and_stable_across_builds(site):
    site()
    first = json.loads((site.dir / "inks.json").read_text())
    site()
    assert json.loads((site.dir / "inks.json").read_text()) == first


def test_dev_data_written_for_vite(site):
    site()
    d = json.loads((site.dir / "desk" / "dev-data.json").read_text())
    assert "commits" in d and "inks" in d


def test_broken_ink_file_never_blocks_the_dashboard(site):
    # review M6: a hand-edited, malformed inks.json used to crash build.py before dashboard.html was written
    (site.dir / "inks.json").write_text("{ not json")
    r = site()
    assert r.returncode == 0, r.stderr
    assert (site.dir / "dashboard.html").exists()
    assert "ink" in (r.stdout + r.stderr).lower() and "warning" in (r.stdout + r.stderr).lower()
