import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from personal_tracker.server import todo_argv


@pytest.fixture
def live(sandbox):
    """The sandbox's edit server running for real; yields (base url, token, sandbox)."""
    sandbox("add", "Seed")                                          # builds dashboard.html
    p = subprocess.Popen([sys.executable, "-m", "personal_tracker", "serve"], env=sandbox.env, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if (sandbox.dir / "server.json").exists():
                break
            time.sleep(0.1)
        base = "http://127.0.0.1:%d" % json.loads((sandbox.dir / "server.json").read_text())["port"]
        html = urllib.request.urlopen(base + "/").read().decode()
        token = re.search(r'name="tracker-token" content="([^"]+)"', html).group(1)
        yield base, token, sandbox
    finally:
        p.terminate(); p.wait()


def post(base, body, token, origin=None, host=None):
    host = host or base[len("http://"):]
    req = urllib.request.Request(base + "/api/todo", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Tracker-Token": token,
                                          "Origin": origin or "http://" + host, "Host": host})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_actions_go_through_todo_py_and_rebuild(live):
    base, token, sb = live
    assert post(base, {"action": "add", "title": "-starts with a dash", "project": "alpha"}, token)[0] == 200
    assert post(base, {"action": "start", "id": "t-0002"}, token)[0] == 200
    assert post(base, {"action": "pause", "id": "t-0002", "text": "blocked"}, token)[0] == 200
    assert post(base, {"action": "note", "id": "t-0002", "text": "-x still blocked"}, token)[0] == 200
    it = sb.items()[1]
    assert it["title"] == "-starts with a dash" and it["status"] == "paused"
    assert [n["text"] for n in it["notes"]] == ["Paused: blocked", "-x still blocked"]
    assert '"status": "paused"' in urllib.request.urlopen(base + "/").read().decode()   # page rebuilt


def test_refuses_bad_token_origin_and_host(live):
    base, token, sb = live
    body = {"action": "start", "id": "t-0001"}
    assert post(base, body, "wrong")[0] == 403
    assert post(base, body, token, origin="http://evil.example")[0] == 403
    assert post(base, body, token, host="evil.example")[0] == 403         # DNS rebinding
    assert sb.items()[0]["status"] == "todo"


def test_errors_come_back_readable(live):
    base, token, _ = live
    assert post(base, {"action": "start", "id": "t-0999"}, token) == (404, {"error": "no task with id t-0999 (run: tracker todo --all)"})
    code, body = post(base, {"action": "pause", "id": "t-0001"}, token)    # still to do
    assert code == 400 and "in progress" in body["error"]
    assert post(base, {"action": "rm", "id": "t-0001"}, token)[0] == 400


@pytest.mark.parametrize("body", [None, [], {"action": "add"}, {"action": "add", "title": "x", "project": "../etc"},
                                  {"action": "start", "id": "t-1; rm"}, {"action": "note", "id": "t-0001", "text": "  "}])
def test_todo_argv_rejects(body):
    with pytest.raises(ValueError):
        todo_argv(body)


def test_todo_argv_puts_user_text_after_double_dash():
    assert todo_argv({"action": "add", "title": "T", "project": "p", "repo": "r"}) == ["add", "-p", "p", "-r", "r", "--", "T"]
    assert todo_argv({"action": "pause", "id": "t-0001"}) == ["pause", "--", "t-0001"]


def test_an_idle_connection_does_not_block_other_requests(live):
    # browsers preconnect sockets they may never use; a one-at-a-time server would hang on them
    import socket
    base, token, _ = live
    idle = socket.create_connection(("127.0.0.1", int(base.rsplit(":", 1)[1])))
    try:
        assert json.load(urllib.request.urlopen(base + "/api/ping", timeout=2))["app"] == "tracker"
    finally:
        idle.close()
