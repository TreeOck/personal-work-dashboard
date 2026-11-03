import json
import subprocess
import sys

TOOL_NAMES = ["tracker_todo", "tracker_add", "tracker_start", "tracker_note", "tracker_pause", "tracker_done", "tracker_drop"]


def _rpc(sandbox, lines):
    """Run `python -m personal_tracker mcp`, send the lines, close stdin, return (replies, raw stdout)."""
    data = "".join((l if isinstance(l, str) else json.dumps(l, ensure_ascii=False)) + "\n" for l in lines)
    r = subprocess.run([sys.executable, "-m", "personal_tracker", "mcp"], env=sandbox.env, input=data.encode("utf-8"),
                       capture_output=True, timeout=60)
    out = r.stdout.decode("utf-8")
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    return [json.loads(l) for l in out.splitlines()], out


def _req(i, method, params=None):
    m = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        m["params"] = params
    return m


def _call(i, name, args):
    return _req(i, "tools/call", {"name": name, "arguments": args})


def _init(i, version="2025-11-25"):
    return _req(i, "initialize", {"protocolVersion": version, "capabilities": {"roots": {}}, "clientInfo": {"name": "t", "version": "1"}})


def _text(reply):
    return reply["result"]["content"][0]["text"]


def test_handshake_and_tool_list(sandbox):
    replies, _ = _rpc(sandbox, [_init(1), {"jsonrpc": "2.0", "method": "notifications/initialized"}, _req(2, "tools/list"),
                                _init(3, "2024-01-01"), _init(4, "2025-06-18")])
    assert [r["id"] for r in replies] == [1, 2, 3, 4]
    assert replies[0]["result"]["protocolVersion"] == "2025-11-25"
    assert replies[0]["result"]["serverInfo"]["name"] == "personal-work-dashboard"
    assert replies[0]["result"]["capabilities"] == {"tools": {}}
    assert replies[2]["result"]["protocolVersion"] == "2025-11-25"
    assert replies[3]["result"]["protocolVersion"] == "2025-06-18"
    tools = replies[1]["result"]["tools"]
    assert [t["name"] for t in tools] == TOOL_NAMES
    assert all(t["inputSchema"]["type"] == "object" and t["description"] for t in tools)
    add = next(t for t in tools if t["name"] == "tracker_add")
    assert add["inputSchema"]["required"] == ["title", "path"]


def test_every_tool_round_trip(sandbox):
    repo = sandbox.root / "alpha" / "alpha-be"
    (repo / ".git").mkdir(parents=True)
    title = "हिंदी → ✅"
    replies, _ = _rpc(sandbox, [
        _init(1),
        _call(2, "tracker_add", {"title": title, "path": str(repo)}),
        _call(3, "tracker_start", {"id": "t-0001"}),
        _call(4, "tracker_note", {"id": "t-0001", "text": "tests passing"}),
        _call(5, "tracker_pause", {"id": "t-0001", "reason": "waiting on review"}),
        _call(6, "tracker_start", {"id": "t-0001"}),
        _call(7, "tracker_done", {"id": "t-0001"}),
        _call(8, "tracker_add", {"title": "second", "path": str(sandbox.root / "outside-nothing")}),
        _call(9, "tracker_drop", {"id": "t-0002"}),
        _call(10, "tracker_todo", {"all": True}),
        _call(11, "tracker_todo", {}),
    ])
    assert all(not r["result"]["isError"] for r in replies[1:]), replies
    assert _text(replies[1]).splitlines()[0] == "t-0001"
    assert title in _text(replies[9]) and "t-0002" in _text(replies[9])
    assert _text(replies[10]) == "no open tasks"
    a, b = sandbox.items()
    assert (a["status"], a["project"], a["repo"]) == ("done", "alpha", "alpha-be")
    assert a["title"] == title and [n["text"] for n in a["notes"]] == ["tests passing", "Paused: waiting on review"]
    assert (b["status"], b["project"], b["repo"]) == ("dropped", "outside-nothing", None)


def test_path_outside_root_adds_without_project_and_says_so(sandbox, tmp_path):
    replies, _ = _rpc(sandbox, [_call(1, "tracker_add", {"title": "x", "path": str(tmp_path / "somewhere-else")})])
    assert not replies[0]["result"]["isError"]
    assert "not under" in _text(replies[0])
    assert sandbox.items()[0]["project"] is None


def test_tool_errors_are_results_not_crashes(sandbox):
    replies, _ = _rpc(sandbox, [
        _call(1, "tracker_start", {"id": "t-0999"}),
        _call(2, "tracker_add", {"title": "a", "path": str(sandbox.root)}),
        _call(3, "tracker_pause", {"id": "t-0001"}),
        _call(4, "tracker_add", {"path": str(sandbox.root)}),
        _call(5, "tracker_nope", {}),
        _call(6, "tracker_note", {"id": "t-0001", "text": 5}),
    ])
    errs = [r["result"]["isError"] for r in replies]
    assert errs == [True, False, True, True, True, True]
    assert "no task with id t-0999" in _text(replies[0])
    assert "can only pause" in _text(replies[2])
    assert "title" in _text(replies[3])
    assert "tracker_nope" in _text(replies[4])
    assert "Traceback" not in "".join(_text(r) for r in replies)


def test_server_survives_bad_input(sandbox):
    replies, out = _rpc(sandbox, ["", "{not json", "[1, 2]", {"jsonrpc": "2.0", "method": "notifications/whatever"},
                                  _req(9, "nope"), _req(10, "ping")])
    assert all(l.startswith("{") for l in out.splitlines())
    by_id = {r.get("id"): r for r in replies}
    assert by_id[9]["error"]["code"] == -32601
    assert by_id[10]["result"] == {}
    # parse error for "{not json", invalid request for [1, 2], -32601, ping; the notification got nothing
    assert [r["error"]["code"] for r in replies if r["id"] is None] == [-32700, -32600]
    assert len(replies) == 4


def test_no_config_gives_a_clear_tool_error(sandbox):
    (sandbox.dir / "config.json").unlink()
    replies, _ = _rpc(sandbox, [_init(1), _req(2, "tools/list"), _call(3, "tracker_todo", {})])
    assert len(replies[1]["result"]["tools"]) == 7
    assert replies[2]["result"]["isError"] and "tracker init" in _text(replies[2])


def test_unexpected_exception_is_logged_not_shown(sandbox):
    (sandbox.dir / "todo.json").write_text('{"items": 5}', encoding="utf-8")
    replies, _ = _rpc(sandbox, [_call(1, "tracker_todo", {})])
    assert replies[0]["result"]["isError"] and _text(replies[0]).startswith("internal error: ")
    assert "Traceback" in (sandbox.dir / "mcp.log").read_text(encoding="utf-8")


def test_deeply_nested_line_does_not_kill_the_server(sandbox):
    replies, _ = _rpc(sandbox, ["[" * 100000 + "]" * 100000, _req(2, "ping")])
    assert replies[0]["error"]["code"] == -32700 and replies[-1] == {"jsonrpc": "2.0", "id": 2, "result": {}}
