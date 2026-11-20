"""Hand corrections: a task's branch and where a commit belongs (step 3)."""
import json
import subprocess
import sys

import pytest

from personal_tracker import server, todo
from personal_tracker.errors import TrackerError

A, B, C = "a" * 40, "ab" + "c" * 38, "b" * 40


def _commits(sandbox, extra=()):
    rows = [("alpha/alpha-be", A, "feat/x"), ("alpha/alpha-be", B, "feat/y"), ("alpha/alpha-fe", C, "feat/y")] + list(extra)
    commits = [{"sha": sha, "date": "2026-10-12T10:00:00+05:30", "project": rp.split("/")[0], "repo": rp.split("/")[-1],
                "repo_path": rp, "branch": br, "subject": "s", "body": "", "files": [], "ins": 0, "del": 0}
               for rp, sha, br in rows]
    (sandbox.dir / "commits.json").write_text(json.dumps({"generated_at": "2026-10-13T00:00:00+05:30", "since": "2026-10-01",
                                                          "author_pattern": "me", "commits": commits}), encoding="utf-8")


@pytest.fixture
def board(sandbox, monkeypatch):
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    _commits(sandbox)
    todo.add("with repo", "alpha", "alpha-be")
    todo.add("whole project", "alpha")
    return sandbox


def _doc(board):
    return json.loads((board.dir / "todo.json").read_text(encoding="utf-8"))


def test_set_branch_manual_none_auto(board):
    it = todo.set_branch("t-0001", "feat/x")
    assert (it["branch"], it["branch_repo"], it["branch_source"]) == ("feat/x", "alpha/alpha-be", "manual")
    it = todo.set_branch("t-0001", None)
    assert (it["branch"], it["branch_source"]) == (None, "manual")
    it = todo.set_branch("t-0001", "auto")
    assert "branch_source" not in it and "branch" not in it


def test_branch_for_no_repo_task_needs_repo_when_ambiguous(board):
    with pytest.raises(TrackerError, match="alpha/alpha-be, alpha/alpha-fe"):
        todo.set_branch("t-0002", "feat/y")
    assert todo.set_branch("t-0002", "feat/y", repo="alpha/alpha-fe")["branch_repo"] == "alpha/alpha-fe"
    assert todo.set_branch("t-0002", "feat/x")["branch_repo"] == "alpha/alpha-be"   # only one repo has it
    with pytest.raises(TrackerError, match="no commits on branch feat/nope"):
        todo.set_branch("t-0002", "feat/nope")


def test_move_prefix_resolution_and_errors(board):
    assert todo.move("aaaa", ["t-0002"]) == "alpha/alpha-be:" + A
    assert _doc(board)["moves"] == {"alpha/alpha-be:" + A: ["t-0002"]}
    with pytest.raises(TrackerError, match="matches 2 commits"):
        todo.move("a", None)   # "a" prefixes A and B
    with pytest.raises(TrackerError, match="no commit"):
        todo.move("dddd", None)
    with pytest.raises(TrackerError, match="no task with id t-0099"):
        todo.move("bbbb", ["t-0099"])
    todo.move("bbbb", None)
    assert _doc(board)["moves"]["alpha/alpha-fe:" + C] == []
    todo.move("aaaa", "auto")
    assert "alpha/alpha-be:" + A not in _doc(board)["moves"]


def test_manual_branch_and_moves_survive_rescan_and_rebuild(board):
    todo.set_branch("t-0001", "feat/x")
    todo.move("bbbb", ["t-0001"])
    before = _doc(board)
    assert board("scan").returncode == 0 and board("build").returncode == 0
    after = _doc(board)
    assert after["moves"] == before["moves"] and after["items"][0]["branch_source"] == "manual"


def test_server_branch_and_move_actions_validated():
    assert server.todo_argv({"action": "branch", "id": "t-0001", "branch": "feat/x"}) == ["branch", "--", "t-0001", "feat/x"]
    assert server.todo_argv({"action": "branch", "id": "t-0001", "branch": "feat/x", "repo": "a/b"}) == \
        ["branch", "--repo", "a/b", "--", "t-0001", "feat/x"]
    assert server.todo_argv({"action": "branch", "id": "t-0001", "branch": "none"}) == ["branch", "--none", "--", "t-0001"]
    assert server.todo_argv({"action": "branch", "id": "t-0001", "branch": "auto"}) == ["branch", "--auto", "--", "t-0001"]
    assert server.todo_argv({"action": "move", "sha": "abc1234", "ids": ["t-0001", "t-0002"]}) == \
        ["move", "--", "abc1234", "t-0001", "t-0002"]
    assert server.todo_argv({"action": "move", "sha": "abc1234", "ids": "none"}) == ["move", "--none", "--", "abc1234"]
    assert server.todo_argv({"action": "move", "sha": "abc1234", "ids": "auto"}) == ["move", "--auto", "--", "abc1234"]
    for bad in ({"action": "branch", "id": "t-0001", "branch": "-rf"}, {"action": "branch", "id": "t-0001", "branch": "a b"},
                {"action": "move", "sha": "zz", "ids": []}, {"action": "move", "sha": "abc1234", "ids": ["x"]},
                {"action": "branch", "id": "t-0001", "branch": "feat/x", "repo": "../x"}):
        with pytest.raises(ValueError):
            server.todo_argv(bad)


def test_cli_branch_and_move(board):
    r = board("branch", "t-0001", "feat/x")
    assert r.returncode == 0, r.stderr
    assert board("move", "bbbb", "t-0001", "t-0002").returncode == 0
    assert board("move", "aaaa", "--none").returncode == 0
    assert board("branch", "t-0001", "--auto").returncode == 0
    doc = _doc(board)
    assert doc["moves"] == {"alpha/alpha-fe:" + C: ["t-0001", "t-0002"], "alpha/alpha-be:" + A: []}
    assert "branch_source" not in doc["items"][0]


def test_mcp_branch_and_move_tools(board):
    calls = [{"name": "tracker_branch", "arguments": {"id": "t-0001", "branch": "feat/x"}},
             {"name": "tracker_move", "arguments": {"sha": "bbbb", "ids": ["t-0002"]}},
             {"name": "tracker_move", "arguments": {"sha": "aaaa", "auto": True}}]
    msgs = "".join(json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": c}) + "\n" for i, c in enumerate(calls))
    r = subprocess.run([sys.executable, "-m", "personal_tracker", "mcp"], env=board.env, capture_output=True, input=msgs.encode())
    replies = [json.loads(l) for l in r.stdout.decode().splitlines()]
    assert [x["result"]["isError"] for x in replies] == [False, False, False], replies
    doc = _doc(board)
    assert doc["items"][0]["branch"] == "feat/x" and doc["moves"] == {"alpha/alpha-fe:" + C: ["t-0002"]}
