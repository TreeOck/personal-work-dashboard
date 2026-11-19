"""Regression tests for the step-3 final review."""
import json
import os
import subprocess
import sys

from personal_tracker import links, scan, todo
from test_branch_recording import board, _item  # noqa: F401  (fixture)
from test_branches import commit, g, new_repo
from test_links import NOW, bc, ids, task


def test_start_does_not_take_a_branch_with_another_open_tasks_commits(board):
    a = todo.add("A", "dms", "dms-be")["id"]
    todo.set_status(a, "start")                      # started on main: nothing recorded
    g(board.repo, "checkout", "-q", "-b", "feat/a")
    commit(board.repo, "a1")                         # A's work
    b = todo.add("B", "dms", "dms-be")["id"]
    todo.set_status(b, "start")                      # feat/a still checked out
    assert not _item(board, b).get("branch")
    g(board.repo, "checkout", "-q", "-b", "feat/b")  # a fresh branch has no commits of its own: fine to record
    c = todo.add("C", "dms", "dms-be")["id"]
    todo.set_status(c, "start")
    assert _item(board, c)["branch"] == "feat/b"


def test_scan_backfills_branch_on_older_commits(sandbox):
    repo = new_repo(sandbox.root / "proj" / "app")
    g(repo, "checkout", "-q", "-b", "feat/old")
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-09-01T10:00:00+05:30", GIT_COMMITTER_DATE="2026-09-01T10:00:00+05:30")
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Me", "-c", "user.email=me@example.com", "commit", "-q",
                    "--allow-empty", "-m", "old work"], check=True, env=env)
    old = g(repo, "rev-parse", "HEAD")
    assert sandbox("scan", "--since", "2026-08-01").returncode == 0
    path = sandbox.dir / "commits.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    for c in doc["commits"]:
        c.pop("branch", None)                        # as written by 0.9.0
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert sandbox("scan").returncode == 0           # default 14 days: the old commit isn't re-read
    by = {c["sha"]: c for c in json.loads(path.read_text(encoding="utf-8"))["commits"]}
    assert by[old]["branch"] == "feat/old"


def test_inference_skips_many_held_candidates():
    long = task("t-0100", "2026-10-01T00:00:00+05:30", "2026-10-30T00:00:00+05:30")
    holders, commits = [], []
    for n in range(5):   # branch b<n> has 5-n commits in L's window, each held by a manual task
        day = "2026-10-%02dT" % (2 + n * 5)
        holders.append(task("t-02%02d" % n, day + "00:00:00+05:30", day + "23:00:00+05:30", branch="b%d" % n,
                            branch_repo="dms/dms-be", branch_source="manual"))
        commits += [bc("c%d_%d" % (n, k), day + "1%d:00:00+05:30" % k, "b%d" % n) for k in range(5 - n)]
    r = links.assign([long] + holders, commits, NOW)
    assert ids(r, "t-0100") == []
    assert links.branch_info([long] + holders, commits, NOW)["t-0100"] is None


def test_rebased_commits_keep_branch_after_ff_merge_and_delete(tmp_path):
    repo = new_repo(tmp_path / "app")
    g(repo, "checkout", "-q", "-b", "feat/a")
    commit(repo, "a1")
    g(repo, "checkout", "-q", "main")
    commit(repo, "m1")
    g(repo, "checkout", "-q", "feat/a")
    g(repo, "rebase", "-q", "main")
    rebased = g(repo, "rev-parse", "HEAD")
    g(repo, "checkout", "-q", "main")
    g(repo, "merge", "-q", "--ff-only", "feat/a")
    g(repo, "branch", "-q", "-d", "feat/a")
    assert scan.made_on(str(repo), "main").get(rebased) == "feat/a"


def test_detached_checkouts_are_not_branches(tmp_path):
    repo = new_repo(tmp_path / "app")
    g(repo, "tag", "v1")
    g(repo, "checkout", "-q", "--detach")
    d1 = commit(repo, "detached")
    g(repo, "checkout", "-q", "v1")
    d2 = commit(repo, "on a tag")
    got = scan.made_on(str(repo), "main")
    assert d1 not in got and d2 not in got and "HEAD" not in got.values()


def test_none_option_says_what_it_does():
    from importlib import resources
    page = resources.files("personal_tracker").joinpath("templates/dashboard.html").read_text(encoding="utf-8")
    assert "None (use the dates)" not in page and "No branch (only commits no other task claims)" in page


def test_mcp_move_requires_ids_or_auto(sandbox):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tracker_move", "arguments": {"sha": "abcd"}}}
    r = subprocess.run([sys.executable, "-m", "personal_tracker", "mcp"], env=sandbox.env, capture_output=True,
                       input=(json.dumps(msg) + "\n").encode())
    res = json.loads(r.stdout.decode())["result"]
    assert res["isError"] and "ids" in res["content"][0]["text"]
