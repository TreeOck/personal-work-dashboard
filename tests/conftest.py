import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def sandbox(tmp_path):
    """A throwaway data folder (TRACKER_HOME) with empty data and a root folder containing no repos.
    Commands run as `python -m personal_tracker ...`, exactly like the installed `tracker`."""
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / "repos").mkdir()
    env = dict(os.environ, TRACKER_HOME=str(home), PYTHONIOENCODING="utf-8")
    env.pop("TRACKER_CONFIG", None)
    (home / "config.json").write_text(json.dumps({"root": str(tmp_path / "repos"), "author_emails": ["me@example.com"],
                                                  "timezone": "Asia/Kolkata", "summariser": None}), encoding="utf-8")
    (home / "commits.json").write_text(json.dumps({"generated_at": "2026-10-01T00:00:00+05:30", "since": "2026-09-01",
                                                   "author_pattern": "me@example.com", "commits": []}), encoding="utf-8")
    (home / "tasks.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")

    def run(*args):
        return subprocess.run([sys.executable, "-m", "personal_tracker", *args], env=env,
                              capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)   # never prompt
    run.dir = home
    run.env = env
    run.root = tmp_path / "repos"
    run.items = lambda: json.loads((home / "todo.json").read_text(encoding="utf-8"))["items"]
    return run
