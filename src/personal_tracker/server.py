"""Local edit server: lets dashboard.html change todo.json, through the tracker CLI.

  tracker open    start the server (or reuse a running one) and open the dashboard through it
  tracker serve   run in the foreground (what `open` starts in the background)

Bound to 127.0.0.1. Each run makes a random token and writes it into the page it serves; a POST
needs that token, a same-origin Origin and a local Host header, so other sites (or DNS-rebinding
tricks) can't drive it. Every edit runs the tracker CLI, so it shares the CLI's lock, git rescan and rebuild.
The server exits after 12 h without a request; `tracker` starts a new one.
"""
import json
import os
import platform
import re
import secrets
import signal
import socketserver
import subprocess
import sys
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, files, paths
from .errors import TrackerError

PORT = 47615            # fixed so a bookmark keeps working; any free port if it's taken
IDLE = 12 * 3600
ID = re.compile(r"^t-\d{4,}$")
MAX_BODY = 16 * 1024


def todo_argv(body):
    """Validated tracker CLI arguments for one request body, or raise ValueError with a readable reason.
    `--` stops argparse reading user text that starts with '-' as an option."""
    if not isinstance(body, dict):
        raise ValueError("expected a JSON object")
    action = body.get("action")
    text = lambda k, n: str(body.get(k) or "").strip()[:n]
    if action == "add":
        title = text("title", 300)
        if not title:
            raise ValueError("title can't be empty")
        argv = ["add"]
        for flag, key in (("-p", "project"), ("-r", "repo")):
            v = text(key, 200)
            if v:
                if not re.match(r"^[\w.-]+$", v):
                    raise ValueError("%s can only use letters, digits, '.', '_' and '-'" % key)
                argv += [flag, v]
        return argv + ["--", title]
    tid = str(body.get("id") or "")
    if not ID.match(tid):
        raise ValueError("bad task id")
    if action in ("start", "done", "drop"):
        return [action, "--", tid]
    if action == "pause":
        reason = text("text", 2000)
        return ["pause", "--", tid] + ([reason] if reason else [])
    if action == "note":
        note = text("text", 2000)
        if not note:
            raise ValueError("note can't be empty")
        return ["note", "--", tid, note]
    raise ValueError("unknown action")


class Handler(BaseHTTPRequestHandler):
    timeout = 15   # drop sockets that connect and never send (browser preconnects)

    def setup(self):
        self.server.last = time.time()   # any request resets the idle clock
        super().setup()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def reply(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def local_host(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in ("127.0.0.1:%d" % port, "localhost:%d" % port)

    def do_GET(self):
        if not self.local_host():
            return self.reply(403, {"error": "bad host"})
        path = self.path.split("?")[0]
        if path == "/api/ping":
            return self.reply(200, {"app": "tracker", "home": str(paths.home()), "version": __version__})
        if path == "/api/version":
            return self.reply(200, {"version": __version__, "environment": "local", "python": platform.python_version()})
        if path in ("/", "/dashboard.html"):
            try:
                html = paths.file("dashboard.html").read_text(encoding="utf-8")
            except OSError:
                return self.reply(500, {"error": "dashboard.html not built yet (run: tracker build)"})
            meta = '<meta name="tracker-token" content="%s">' % self.server.token
            return self.reply(200, html.replace("<head>", "<head>\n" + meta, 1).encode(), "text/html; charset=utf-8")
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        if not self.local_host() or self.headers.get("Origin") != "http://" + self.headers.get("Host", ""):
            return self.reply(403, {"error": "cross-site request refused"})
        if not secrets.compare_digest(self.headers.get("X-Tracker-Token", ""), self.server.token):
            return self.reply(403, {"error": "stale page: reload it"})
        if self.path != "/api/todo":
            return self.reply(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self.reply(413, {"error": "request too large"})
        try:
            argv = todo_argv(json.loads(self.rfile.read(n) or b"null"))
        except ValueError as e:   # includes bad JSON
            return self.reply(400, {"error": str(e)})
        try:
            r = subprocess.run([sys.executable, "-m", "personal_tracker", *argv],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        except subprocess.TimeoutExpired:
            return self.reply(500, {"error": "the tracker command timed out"})
        err = r.stderr.strip()
        if r.returncode != 0:
            msg = err.splitlines()[-1] if err else "the tracker command failed"
            return self.reply(404 if msg.startswith("no task") else 400, {"error": msg})
        self.reply(200, {"ok": True, "out": r.stdout.strip(), "warning": err or None})


class _Server(ThreadingHTTPServer):   # one thread per connection; the CLI's file lock serialises edits
    def server_bind(self):
        # http.server's version calls socket.getfqdn(), a reverse-DNS lookup that can take many seconds on a Mac
        # with slow DNS (the server then looks like it never started). We only ever listen on 127.0.0.1.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


def make_server(port):
    return _Server(("127.0.0.1", port), Handler)


def serve():
    try:
        srv = make_server(PORT)
    except OSError:
        srv = make_server(0)
    srv.token = secrets.token_urlsafe(32)
    srv.timeout, srv.last = 60, time.time()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # so the finally below removes server.json
    port = srv.server_address[1]
    paths.home().mkdir(parents=True, exist_ok=True)
    files.write_json(paths.file("server.json"), {"pid": os.getpid(), "port": port})
    print("tracker server on http://127.0.0.1:%d/" % port, file=sys.stderr, flush=True)
    try:
        while time.time() - srv.last < IDLE:
            srv.handle_request()
    finally:
        try:
            if files.read_json(paths.file("server.json"), {}).get("pid") == os.getpid():
                paths.file("server.json").unlink()
        except (OSError, ValueError, TrackerError):
            pass


def detach_kwargs(plat=sys.platform):
    """Popen options that let the server outlive the terminal that started it."""
    if plat == "win32":
        DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW = 0x8, 0x200, 0x08000000
        return {"creationflags": DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW}
    return {"start_new_session": True}


def background_python(exe=sys.executable, plat=sys.platform):
    """On Windows prefer pythonw.exe (no console window) when it sits beside python.exe."""
    if plat == "win32":
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w):
            return w
    return exe


def taskkill_argv(pid):
    return ["taskkill", "/PID", str(pid), "/F"]


def terminate(pid):
    """Stop a server process. Windows can't run our cleanup handler, so server.json may be left behind;
    readers treat a server.json whose port doesn't answer as stale."""
    try:
        if sys.platform == "win32":
            subprocess.run(taskkill_argv(pid), capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


def _ping(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1) as r:
            info = json.load(r)
        return info if info.get("app") == "tracker" else None
    except (OSError, ValueError):
        return None


def _registered():
    """(pid, port) from server.json, or (None, None) when missing or unreadable."""
    try:
        state = files.read_json(paths.file("server.json"), {})
        return state["pid"], state["port"]
    except (KeyError, TypeError, TrackerError):
        return None, None


def running_port():
    """Port of a live server for *this* data folder and this version, else None."""
    _, port = _registered()
    info = _ping(port) if port else None
    return port if info and info.get("home") == str(paths.home()) and info.get("version") == __version__ else None


def _stop_old_version():
    """Stop a server of ours (same data folder) that was started by a different tracker version.
    Only a server that answers as ours is stopped: a stale server.json must never lead to killing an unrelated pid."""
    pid, port = _registered()
    info = _ping(port) if port else None
    if info and info.get("home") == str(paths.home()) and info.get("version") != __version__ and pid:
        terminate(pid)
        for _ in range(30):
            if _ping(port) is None:
                break
            time.sleep(0.1)


def ensure():
    port = running_port()
    if port:
        return port
    _stop_old_version()
    paths.home().mkdir(parents=True, exist_ok=True)
    with open(paths.file("server.log"), "a", encoding="utf-8") as log:
        subprocess.Popen([background_python(), "-m", "personal_tracker", "serve"],
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, **detach_kwargs())
    for _ in range(150):   # up to 15 s: a cold Python start on a slow machine can take a while
        time.sleep(0.1)
        port = running_port()
        if port:
            return port
    return None


def open_dashboard():
    port = ensure()
    if port:
        webbrowser.open("http://127.0.0.1:%d/" % port)
    else:
        print("warning: couldn't start the edit server (see server.log); opening read-only", file=sys.stderr)
        webbrowser.open(paths.file("dashboard.html").as_uri())
