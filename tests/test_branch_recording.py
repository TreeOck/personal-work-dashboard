"""A task records the branch it is worked on when added (with a path) or started (step 3)."""
import json
import subprocess
import sys

import pytest

from personal_tracker import locate, todo
from test_branches import commit, g, new_repo


@pytest.fixture
def board(sandbox, monkeypatch):
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    repo = new_repo(sandbox.root / "dms" / "dms-be")
    sandbox.repo = repo
    return sandbox


def _item(board, tid):
    return next(i for i in board.items() if i["id"] == tid)


def test_current_branch_main_folder_and_worktree(board, tmp_path):
    repo, root = board.repo, board.root
    assert locate.current_branch(repo, root) is None            # on main (the default branch)
    g(repo, "checkout", "-q", "-b", "feat/a")
    assert locate.current_branch(repo / ".", root) == ("dms/dms-be", "feat/a")
    wt = repo / ".worktrees" / "b"
    g(repo, "worktree", "add", "-q", "-b", "feat/b", str(wt))
    assert locate.current_branch(wt, root) == ("dms/dms-be", "feat/b")   # the worktree's own branch, main repo's path
    g(repo, "checkout", "-q", "--detach")
    assert locate.current_branch(repo, root) is None
    assert locate.current_branch(tmp_path, root) is None         # not a repo / outside the root


def test_start_records_branch_once(board):
    g(board.repo, "checkout", "-q", "-b", "feat/a")
    t = todo.add("A", "dms", "dms-be")["id"]
    todo.set_status(t, "start")
    it = _item(board, t)
    assert (it["branch"], it["branch_repo"], it["branch_source"]) == ("feat/a", "dms/dms-be", "auto")
    todo.pause(t)
    g(board.repo, "checkout", "-q", "-b", "feat/other")
    todo.set_status(t, "start")                                  # resuming doesn't overwrite it
    assert _item(board, t)["branch"] == "feat/a"


def test_start_skips_a_branch_another_open_task_holds(board):
    g(board.repo, "checkout", "-q", "-b", "feat/a")
    first = todo.add("A", "dms", "dms-be")["id"]
    todo.set_status(first, "start")
    second = todo.add("B: plan written before git checkout -b", "dms", "dms-be")["id"]
    todo.set_status(second, "start")
    assert "branch" not in _item(board, second) or _item(board, second)["branch"] is None
    todo.set_status(first, "done")
    third = todo.add("C", "dms", "dms-be")["id"]
    todo.set_status(third, "start")                              # first is closed: the branch is free again
    assert _item(board, third)["branch"] == "feat/a"


def test_add_with_path_records_branch(board):
    wt = board.repo / ".worktrees" / "x"
    g(board.repo, "worktree", "add", "-q", "-b", "feat/x", str(wt))
    t = todo.add("X", "dms", "dms-be", path=str(wt))["id"]
    assert (_item(board, t)["branch"], _item(board, t)["branch_source"]) == ("feat/x", "auto")


def test_cli_start_path_and_mcp_start_path(board):
    wt = board.repo / ".worktrees" / "y"
    g(board.repo, "worktree", "add", "-q", "-b", "feat/y", str(wt))
    board("add", "Y", "-p", "dms", "-r", "dms-be")
    r = board("start", "t-0001", "--path", str(wt))
    assert r.returncode == 0, r.stderr
    assert _item(board, "t-0001")["branch"] == "feat/y"
    wt2 = board.repo / ".worktrees" / "z"
    g(board.repo, "worktree", "add", "-q", "-b", "feat/z", str(wt2))
    board("add", "Z", "-p", "dms", "-r", "dms-be")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "tracker_start", "arguments": {"id": "t-0002", "path": str(wt2)}}}]
    r = subprocess.run([sys.executable, "-m", "personal_tracker", "mcp"], env=board.env, capture_output=True,
                       input="".join(json.dumps(m) + "\n" for m in msgs).encode())
    assert not json.loads(r.stdout.decode().splitlines()[0])["result"]["isError"]
    assert _item(board, "t-0002")["branch"] == "feat/z"


def test_rules_tell_agents_to_pass_the_folder_on_start():
    from personal_tracker import agent_setup
    assert 'tracker start <id> --path "<your workspace folder>"' in agent_setup.rules("cli")
    assert "`tracker_start` with `path`" in agent_setup.rules("mcp")
