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
    log = open(sandbox.dir / "serve.log", "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "personal_tracker", "serve"], env=sandbox.env, stderr=log)
    try:
        for _ in range(300):                                            # 30 s: CI runners can be slow
            if (sandbox.dir / "server.json").exists() or p.poll() is not None:
                break
            time.sleep(0.1)
        if not (sandbox.dir / "server.json").exists():
            log.flush()
            pytest.fail("the server did not start (exit code %s):\n%s" % (p.poll(), (sandbox.dir / "serve.log").read_text(encoding="utf-8")))
        base = "http://127.0.0.1:%d" % json.loads((sandbox.dir / "server.json").read_text(encoding="utf-8"))["port"]
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


# ---- identity, version, detaching (Task 4)

import platform
import textwrap

from personal_tracker import __version__, server


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.load(r)


def test_version_endpoint_needs_no_token(live):
    base, _, _ = live
    assert get(base + "/api/version") == {"version": __version__, "environment": "local", "python": platform.python_version()}


def test_ping_reports_home_and_version(live):
    base, _, sb = live
    assert get(base + "/api/ping") == {"app": "tracker", "home": str(sb.dir), "version": __version__}


FAKE = textwrap.dedent('''
    import http.server, json, sys
    HOME, VERSION = sys.argv[1], sys.argv[2]
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"app": "tracker", "home": HOME, "version": VERSION}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    print(srv.server_address[1], flush=True)
    srv.serve_forever()
''')


@pytest.fixture
def fake_server(tmp_path):
    """Start a stand-in tracker server answering /api/ping with the given home and version."""
    procs = []

    def start(home, version):
        script = tmp_path / "fake_tracker.py"
        script.write_text(FAKE, encoding="utf-8")
        p = subprocess.Popen([sys.executable, str(script), str(home), version], stdout=subprocess.PIPE, text=True)
        procs.append(p)
        return p, int(p.stdout.readline())
    yield start
    for p in procs:
        if p.poll() is None:
            p.kill()
        p.wait()


def ensure_in(sandbox):
    """Run server.ensure() as a separate process in the sandbox; returns (port, pid of the server now registered)."""
    r = subprocess.run([sys.executable, "-c", "from personal_tracker import server; print(server.ensure())"],
                       env=sandbox.env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return int(r.stdout.strip()), json.loads((sandbox.dir / "server.json").read_text(encoding="utf-8"))["pid"]


def register(sandbox, pid, port):
    (sandbox.dir / "server.json").write_text(json.dumps({"pid": pid, "port": port}))


def test_version_mismatch_replaces_server(sandbox, fake_server):
    old, old_port = fake_server(sandbox.dir, "0.0.1")
    register(sandbox, old.pid, old_port)
    new_port = new_pid = None
    try:
        new_port, new_pid = ensure_in(sandbox)
        assert new_port != old_port and new_pid != old.pid
        assert old.wait(timeout=10) is not None                          # the old-version server was stopped
        assert get("http://127.0.0.1:%d/api/ping" % new_port)["version"] == __version__
    finally:
        if new_pid:
            server.terminate(new_pid)


def test_server_for_another_data_folder_is_neither_reused_nor_stopped(sandbox, fake_server, tmp_path):
    other, other_port = fake_server(tmp_path / "elsewhere", __version__)
    register(sandbox, other.pid, other_port)
    new_pid = None
    try:
        new_port, new_pid = ensure_in(sandbox)
        assert new_port != other_port
        assert other.poll() is None                                      # not ours to stop
    finally:
        if new_pid:
            server.terminate(new_pid)


def test_stale_server_json_is_ignored(sandbox):
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); closed_port = s.getsockname()[1]; s.close()
    register(sandbox, 2 ** 22 + 1, closed_port)                          # a pid and port nothing owns
    new_pid = None
    try:
        new_port, new_pid = ensure_in(sandbox)
        assert get("http://127.0.0.1:%d/api/ping" % new_port)["home"] == str(sandbox.dir)
    finally:
        if new_pid:
            server.terminate(new_pid)


def test_detach_options_per_platform():
    assert server.detach_kwargs("darwin") == {"start_new_session": True}
    assert server.detach_kwargs("linux") == {"start_new_session": True}
    DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW = 0x8, 0x200, 0x08000000
    assert server.detach_kwargs("win32") == {"creationflags": DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW}


def test_windows_background_python_prefers_pythonw(tmp_path):
    (tmp_path / "python.exe").write_text("")
    exe = str(tmp_path / "python.exe")
    assert server.background_python(exe, "win32") == exe                 # no pythonw beside it: keep python.exe
    (tmp_path / "pythonw.exe").write_text("")
    assert server.background_python(exe, "win32") == str(tmp_path / "pythonw.exe")
    assert server.background_python(exe, "darwin") == exe


def test_taskkill_command():
    assert server.taskkill_argv(1234) == ["taskkill", "/PID", "1234", "/F"]


def test_open_dashboard_uses_the_browser_module(monkeypatch, tmp_path, capsys):
    opened = []
    monkeypatch.setenv("TRACKER_HOME", str(tmp_path))
    monkeypatch.setattr(server.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(server, "ensure", lambda: 47615)
    server.open_dashboard()
    assert opened == ["http://127.0.0.1:47615/"]
    monkeypatch.setattr(server, "ensure", lambda: None)                  # server couldn't start: read-only file
    server.open_dashboard()
    assert opened[1] == (tmp_path / "dashboard.html").as_uri()
    assert "read-only" in capsys.readouterr().err


def test_server_start_does_not_do_a_reverse_dns_lookup(monkeypatch):
    # http.server's default bind calls socket.getfqdn(), which can take many seconds on a Mac with slow DNS (CI runners)
    import socket

    def slow(*a, **k):
        raise AssertionError("socket.getfqdn() must not be called when the server starts")
    monkeypatch.setattr(socket, "getfqdn", slow)
    srv = server.make_server(0)
    try:
        assert srv.server_address[0] == "127.0.0.1" and srv.server_name == "127.0.0.1"
    finally:
        srv.server_close()


def _shadow_dir(tmp_path):
    """A folder with a secrets.py that breaks anything importing it: stands in for 'whatever folder you ran tracker from'."""
    d = tmp_path / "somewhere"
    d.mkdir()
    (d / "secrets.py").write_text("raise RuntimeError('the stdlib module was shadowed by the current folder')\n", encoding="utf-8")
    return d


def test_server_started_by_tracker_ignores_the_callers_folder(sandbox, tmp_path):
    shadow = _shadow_dir(tmp_path)
    r = subprocess.run([sys.executable, "-P", "-c", "from personal_tracker import server; print(server.ensure())"],
                       env=sandbox.env, cwd=shadow, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    port = r.stdout.strip()
    assert port.isdigit(), "the background server did not start from a folder that shadows the stdlib: " + r.stdout + r.stderr
    try:
        assert get("http://127.0.0.1:%s/api/ping" % port)["home"] == str(sandbox.dir)
    finally:
        server.terminate(json.loads((sandbox.dir / "server.json").read_text(encoding="utf-8"))["pid"])


def test_edits_from_the_page_ignore_the_servers_inherited_folder(sandbox, tmp_path):
    shadow = _shadow_dir(tmp_path)
    sandbox("add", "Seed")                                                  # builds dashboard.html
    p = subprocess.Popen([sys.executable, "-P", "-m", "personal_tracker", "serve"], env=sandbox.env, cwd=shadow, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            if (sandbox.dir / "server.json").exists():
                break
            time.sleep(0.1)
        base = "http://127.0.0.1:%d" % json.loads((sandbox.dir / "server.json").read_text(encoding="utf-8"))["port"]
        token = re.search(r'name="tracker-token" content="([^"]+)"', urllib.request.urlopen(base + "/").read().decode()).group(1)
        code, body = post(base, {"action": "note", "id": "t-0001", "text": "from the page"}, token)
        assert code == 200, body
    finally:
        p.terminate()
        p.wait()
