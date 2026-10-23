import json
import subprocess
import sys

from personal_tracker import __version__


def test_version(sandbox):
    r = sandbox("--version")
    assert r.returncode == 0 and r.stdout.strip() == "tracker " + __version__ == "tracker 0.8.0"


def test_no_config_says_run_init(sandbox):
    (sandbox.dir / "config.json").unlink()
    r = sandbox("todo")
    assert r.returncode == 1 and "tracker init" in r.stderr


def test_add_hindi_title(sandbox):
    title = "हिंदी दस्तावेज़ → ✅"
    assert sandbox("add", title).stdout.strip() == "t-0001"
    assert title in sandbox("todo").stdout


def test_user_errors_are_one_line_not_a_traceback(sandbox):
    r = sandbox("start", "t-0999")
    assert r.returncode == 1 and "Traceback" not in r.stderr and "no task with id t-0999" in r.stderr


def test_unicode_output_survives_a_windows_style_stdout_codepage(sandbox):
    # Windows pipes stdout in the ANSI code page (cp1252); the CLI must still print UTF-8 instead of dying after saving
    title = "हिंदी → ✅"
    sandbox("add", title)
    sandbox("start", "t-0001")
    env = dict(sandbox.env, PYTHONIOENCODING="cp1252")
    r = subprocess.run([sys.executable, "-m", "personal_tracker", "note", "t-0001", "hello"], env=env, capture_output=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert title in r.stdout.decode("utf-8")
    assert sandbox.items()[0]["notes"][-1]["text"] == "hello"


def _bad_summariser(sandbox, tmp_path):
    script = tmp_path / "bad_llm.py"
    script.write_text("print('{\"tasks\": [\"x\"]}')\n", encoding="utf-8")
    cfg = json.loads((sandbox.dir / "config.json").read_text(encoding="utf-8"))
    cfg["summariser"] = [sys.executable, str(script)]
    (sandbox.dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (sandbox.dir / "commits.json").write_text(json.dumps({"generated_at": "2026-10-13T10:00:00+05:30", "since": "2026-10-01",
        "author_pattern": "me", "commits": [{"sha": "a" * 40, "date": "2026-10-12T10:00:00+05:30", "project": "alpha", "repo": "r",
        "repo_path": "alpha/r", "subject": "s", "body": "", "files": [], "ins": 1, "del": 0}]}), encoding="utf-8")


def test_refresh_still_builds_the_page_when_the_summariser_misbehaves(sandbox, tmp_path):
    _bad_summariser(sandbox, tmp_path)
    r = sandbox("refresh", "--quiet")
    assert r.returncode == 0, r.stderr
    log = (sandbox.dir / "refresh.log").read_text(encoding="utf-8")
    assert "summarise failed" in log and "=== done" in log
    assert (sandbox.dir / "dashboard.html").exists()


def test_refresh_logs_a_crash_in_any_step_and_still_builds(sandbox, monkeypatch):
    from personal_tracker import cli
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))

    def boom():
        raise RuntimeError("unexpected boom")
    monkeypatch.setattr(cli.summarise, "run", lambda *a, **k: boom())
    cli.refresh(quiet=True)                                                  # a summariser crash must not stop the page
    log = (sandbox.dir / "refresh.log").read_text(encoding="utf-8")
    assert "unexpected boom" in log and "=== done" in log
    assert (sandbox.dir / "dashboard.html").exists()


def test_refresh_log_records_why_the_page_build_failed(sandbox, monkeypatch):
    import pytest as _pytest
    from personal_tracker import cli
    from personal_tracker.errors import TrackerError
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))

    def bad_build():
        raise TrackerError("bad page")
    monkeypatch.setattr(cli.build, "build", bad_build)
    with _pytest.raises(TrackerError):
        cli.refresh(quiet=True)
    assert "refresh failed: bad page" in (sandbox.dir / "refresh.log").read_text(encoding="utf-8")   # not only in launchd.err.log
