import json
import os
import shutil
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


@pytest.fixture
def sandbox(tmp_path):
    """A throwaway copy of the tool with empty data and a root folder containing no repos."""
    for f in ("todo.py", "build.py", "links.py", "inks.py", "scan.py", "config.py", "template.html"):
        shutil.copy(os.path.join(REPO, f), tmp_path / f)
    (tmp_path / "desk" / "src" / "data").mkdir(parents=True)          # build.py reads the ink palette
    shutil.copy(os.path.join(REPO, "desk/src/data/inks.json"), tmp_path / "desk/src/data/inks.json")
    (tmp_path / "repos").mkdir()
    (tmp_path / "config.json").write_text(json.dumps({"root": str(tmp_path / "repos"), "author_emails": ["me@example.com"]}))
    (tmp_path / "commits.json").write_text(json.dumps({"generated_at": "2026-10-01T00:00:00+05:30", "since": "2026-09-01",
                                                       "author_pattern": "me@example.com", "commits": []}))
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": []}))

    def run(*args):
        return subprocess.run([sys.executable, str(tmp_path / "todo.py"), *args], capture_output=True, text=True)
    run.dir = tmp_path
    run.items = lambda: json.loads((tmp_path / "todo.json").read_text())["items"]
    return run
