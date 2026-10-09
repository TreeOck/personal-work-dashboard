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
    data = json.loads((sandbox.dir / "commits.json").read_text())
    data["commits"] = [{"sha": "abc1234def", "date": started, "project": "alpha", "repo": "alpha-be", "repo_path": "alpha/alpha-be",
                        "subject": "s", "body": "", "files": [], "ins": 1, "del": 0, "author": "me", "email": "me@example.com"}]
    (sandbox.dir / "commits.json").write_text(json.dumps(data))
    r = sandbox("done", "t-0001")
    assert r.returncode == 0, r.stderr
    html = (sandbox.dir / "dashboard.html").read_text()
    # scan.py ran (root has no repos) and kept the existing commit; the build linked it
    assert '"linked": ["alpha/alpha-be:abc1234def"]' in html


def test_errors(sandbox):
    assert sandbox("add", "  ").returncode == 1
    assert sandbox("start", "t-0999").returncode == 1
    sandbox("add", "x")
    assert "already" in sandbox("drop", "t-0001").stdout + sandbox("drop", "t-0001").stdout
