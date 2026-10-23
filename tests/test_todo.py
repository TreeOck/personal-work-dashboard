import json


def test_start_records_started_at_once_and_reopen_keeps_it(sandbox):
    assert sandbox("add", "Thing", "-p", "alpha").stdout.strip() == "t-0001"
    assert sandbox.items()[0]["started_at"] is None
    sandbox("start", "t-0001")
    first = sandbox.items()[0]["started_at"]
    assert first
    sandbox("done", "t-0001")
    assert sandbox.items()[0]["closed_at"]
    sandbox("start", "t-0001")                       # re-open
    it = sandbox.items()[0]
    assert it["started_at"] == first and it["closed_at"] is None and it["status"] == "in_progress"


def test_done_rescans_and_build_links_commits(sandbox):
    sandbox("add", "Thing", "-p", "alpha", "-r", "alpha-be")
    sandbox("start", "t-0001")
    # a commit that only lands in commits.json via the scan at `done` time would be found here;
    # the sandbox root has no repos, so simulate the scanned result instead
    started = sandbox.items()[0]["started_at"]
    data = json.loads((sandbox.dir / "commits.json").read_text(encoding="utf-8"))
    data["commits"] = [{"sha": "abc1234def", "date": started, "project": "alpha", "repo": "alpha-be", "repo_path": "alpha/alpha-be",
                        "subject": "s", "body": "", "files": [], "ins": 1, "del": 0, "author": "me", "email": "me@example.com"}]
    (sandbox.dir / "commits.json").write_text(json.dumps(data))
    r = sandbox("done", "t-0001")
    assert r.returncode == 0, r.stderr
    html = (sandbox.dir / "dashboard.html").read_text(encoding="utf-8")
    # scan.py ran (root has no repos) and kept the existing commit; the build linked it
    assert '"linked": ["alpha/alpha-be:abc1234def"]' in html


def test_errors(sandbox):
    assert sandbox("add", "  ").returncode == 1
    assert sandbox("start", "t-0999").returncode == 1
    sandbox("add", "x")
    assert "already" in sandbox("drop", "t-0001").stdout + sandbox("drop", "t-0001").stdout


def test_pause_resume_keeps_start_and_records_the_pause(sandbox):
    sandbox("add", "Thing", "-p", "alpha")
    sandbox("start", "t-0001")
    started = sandbox.items()[0]["started_at"]
    r = sandbox("pause", "t-0001", "waiting on review")
    assert r.returncode == 0, r.stderr
    it = sandbox.items()[0]
    assert it["status"] == "paused" and it["paused_at"] and it["closed_at"] is None
    assert it["notes"][-1]["text"] == "Paused: waiting on review"
    assert "t-0001" in sandbox("todo").stdout                     # paused tasks are still open work
    sandbox("start", "t-0001")                                    # resume
    it = sandbox.items()[0]
    assert it["status"] == "in_progress" and it["started_at"] == started and it["paused_at"] is None
    assert len(it["pauses"]) == 1 and it["pauses"][0]["to"]


def test_pause_without_reason_adds_no_note(sandbox):
    sandbox("add", "Thing"); sandbox("start", "t-0001")
    sandbox("pause", "t-0001")
    assert sandbox.items()[0]["notes"] == []
    assert "already" in sandbox("pause", "t-0001").stdout


def test_pause_only_from_in_progress(sandbox):
    sandbox("add", "Thing")
    assert sandbox("pause", "t-0001").returncode == 1             # still to do
    sandbox("start", "t-0001"); sandbox("done", "t-0001")
    assert sandbox("pause", "t-0001").returncode == 1             # finished
    assert sandbox.items()[0]["status"] == "done"


def test_done_or_drop_while_paused_closes_the_pause(sandbox):
    sandbox("add", "Thing"); sandbox("start", "t-0001"); sandbox("pause", "t-0001")
    sandbox("drop", "t-0001")
    it = sandbox.items()[0]
    assert it["status"] == "dropped" and it["paused_at"] is None and it["pauses"][0]["to"] == it["closed_at"]


def test_note_rejects_empty_text(sandbox):
    sandbox("add", "Thing")
    assert sandbox("note", "t-0001", "   ").returncode == 1
    assert sandbox.items()[0]["notes"] == []
