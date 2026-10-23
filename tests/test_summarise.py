import json
import os
import stat
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from personal_tracker.summarise import (dedupe_ids, local, resolve_command, unique_id, validate_backfill,
                                        validate_new_tasks, zone)

IST = ZoneInfo("Asia/Kolkata")

ORPHANS = [
    {"sha": "aaaaaaa111", "date": "2026-10-06T10:00:00+05:30", "project": "alpha"},
    {"sha": "bbbbbbb222", "date": "2026-10-05T20:00:00Z", "project": "alpha"},  # 01:30 IST on 6 Oct
]


def task(**kw):
    t = {"date": "2026-10-06", "project": "alpha", "kind": "feature", "thread": "Versioning", "title": "T",
         "summary": "S", "details": [], "commits": ["aaaaaaa", "bbbbbbb"]}
    t.update(kw)
    return t


def test_valid_output_passes_and_utc_commit_lands_on_ist_day():
    validate_new_tasks([task()], ORPHANS, {}, IST)


@pytest.mark.parametrize("bad, msg", [
    (dict(kind="chore"), "bad kind"),
    (dict(title=""), "missing title"),
    (dict(thread="  "), "missing thread"),
    (dict(commits=[]), "bad details/commits"),
    (dict(commits=["aaaaaaa"]), "coverage mismatch"),
    (dict(commits=["aaaaaaa", "bbbbbbb", "aaaaaaa"]), "coverage mismatch"),
    (dict(commits=["aaaaaaa", "zzzzzzz"]), "unknown sha"),
    (dict(date="2026-10-05"), "date mismatch"),
    (dict(project="beta"), "project mismatch"),
])
def test_bad_output_is_rejected(bad, msg):
    with pytest.raises(ValueError, match=msg):
        validate_new_tasks([task(**bad)], ORPHANS, {}, IST)


def test_thread_cannot_cross_projects():
    with pytest.raises(ValueError, match="two projects"):
        validate_new_tasks([task()], ORPHANS, {"Versioning": "beta"}, IST)


def test_existing_thread_in_same_project_is_reused():
    validate_new_tasks([task()], ORPHANS, {"Versioning": "alpha"}, IST)


TASKS = [{"id": "x1", "project": "alpha"}, {"id": "x2", "project": "beta"}, {"id": "x3", "project": "alpha", "thread": "Old"}]


def test_backfill_must_cover_exactly_the_tasks_without_thread():
    validate_backfill({"x1": "A", "x2": "B"}, TASKS, {"Old": "alpha"})
    with pytest.raises(ValueError, match="ids mismatch"):
        validate_backfill({"x1": "A"}, TASKS, {"Old": "alpha"})
    with pytest.raises(ValueError, match="ids mismatch"):
        validate_backfill({"x1": "A", "x2": "B", "x3": "C"}, TASKS, {"Old": "alpha"})


def test_backfill_rejects_empty_and_cross_project_threads():
    with pytest.raises(ValueError, match="empty thread"):
        validate_backfill({"x1": "", "x2": "B"}, TASKS, {})
    with pytest.raises(ValueError, match="two projects"):
        validate_backfill({"x1": "Same", "x2": "Same"}, TASKS, {})
    with pytest.raises(ValueError, match="two projects"):
        validate_backfill({"x1": "A", "x2": "Old"}, TASKS, {"Old": "alpha"})


def test_unique_id_skips_taken():
    taken = {"auto-d-p-1", "auto-d-p-2"}
    assert unique_id("auto-d-p", taken) == "auto-d-p-3"
    assert "auto-d-p-3" in taken


def test_dedupe_ids_renames_only_later_duplicates():
    doc = {"tasks": [{"id": "auto-d-p-1"}, {"id": "auto-d-p-1"}, {"id": "auto-d-p-2"}]}
    assert dedupe_ids(doc) == 1
    ids = [t["id"] for t in doc["tasks"]]
    assert ids[0] == "auto-d-p-1" and len(set(ids)) == 3


def test_day_boundary_follows_timezone():
    # 23:30 UTC on 24 Oct is 00:30 BST on the 25th in London (BST ends 01:00 UTC on the 25th): the zone, not UTC, picks the day
    assert local("2026-10-24T23:30:00+00:00", zone("Europe/London")).date().isoformat() == "2026-10-25"
    assert local("2026-10-22T20:00:00+00:00", zone("Asia/Kolkata")).date().isoformat() == "2026-10-23"
    assert local("2026-10-22T20:00:00Z", zone("Asia/Kolkata")).date().isoformat() == "2026-10-23"   # py3.9-style Z suffix too


def test_no_timezone_means_this_computers_zone():
    assert zone(None).utcoffset(datetime.now()) == datetime.now().astimezone().utcoffset()


def _fake_command(directory, name, body):
    """An executable `name` on disk that runs `body` with python: .cmd shim on Windows, #! script elsewhere."""
    if sys.platform == "win32":
        path = directory / (name + ".cmd")
        path.write_text('@echo off\r\n"%s" -c "%s"\r\n' % (sys.executable, body), encoding="utf-8")
    else:
        path = directory / name
        path.write_text('#!/bin/sh\nexec "%s" -c \'%s\'\n' % (sys.executable, body), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_summariser_resolved_via_which(tmp_path, monkeypatch):
    fake = _fake_command(tmp_path, "fakesum", "print(1)")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    resolved = resolve_command(["fakesum", "-p", "--flag"])
    assert os.path.samefile(resolved[0], fake) and resolved[1:] == ["-p", "--flag"]
    assert resolve_command(["no-such-command-xyz"]) is None


def test_no_summariser_configured_is_a_noop(sandbox, tmp_path):
    (sandbox.dir / "commits.json").write_text(json.dumps({"generated_at": "2026-10-13T10:00:00+05:30", "since": "2026-10-01",
        "author_pattern": "me", "commits": [{"sha": "a" * 40, "date": "2026-10-12T10:00:00+05:30", "project": "alpha", "repo": "r",
        "repo_path": "alpha/r", "subject": "s", "body": "", "files": [], "ins": 1, "del": 0}]}), encoding="utf-8")
    before = (sandbox.dir / "tasks.json").read_bytes()
    sandbox.env["PATH"] = str(tmp_path)          # no `claude` anywhere: nothing may even try to run
    r = sandbox("summarise")
    assert r.returncode == 0 and "summaries are off" in r.stdout and "Traceback" not in r.stderr
    assert (sandbox.dir / "tasks.json").read_bytes() == before


def test_configured_summariser_gets_the_prompt_on_stdin_and_its_json_is_validated_and_saved(sandbox, tmp_path):
    script = tmp_path / "fake_llm.py"
    script.write_text("import sys, json\nassert 'alpha' in sys.stdin.read()\n"
        "print(json.dumps({'tasks': [{'date': '2026-10-12', 'project': 'alpha', 'kind': 'feature', 'thread': 'T',"
        " 'title': 'हिंदी → ✅', 'summary': 's', 'details': [], 'commits': ['aaaaaaa']}]}, ensure_ascii=False))\n", encoding="utf-8")
    cfg = json.loads((sandbox.dir / "config.json").read_text(encoding="utf-8"))
    cfg["summariser"] = [sys.executable, str(script)]
    (sandbox.dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (sandbox.dir / "commits.json").write_text(json.dumps({"generated_at": "2026-10-13T10:00:00+05:30", "since": "2026-10-01",
        "author_pattern": "me", "commits": [{"sha": "a" * 40, "date": "2026-10-12T10:00:00+05:30", "project": "alpha", "repo": "r",
        "repo_path": "alpha/r", "subject": "s", "body": "", "files": [], "ins": 1, "del": 0}]}), encoding="utf-8")
    r = sandbox("summarise")
    assert r.returncode == 0, r.stderr
    (t,) = json.loads((sandbox.dir / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert t["title"] == "हिंदी → ✅" and t["commits"] == ["aaaaaaa"]
