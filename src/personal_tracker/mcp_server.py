"""`tracker mcp`: a Model Context Protocol server on stdin/stdout, so agents (Cursor, Antigravity, ...) can keep the
Current board in sync. JSON-RPC 2.0, one message per line. Only protocol messages ever go to stdout; anything else
(warnings, crashes) goes to <data folder>/mcp.log. See docs/api/mcp.md."""
import contextlib
import io
import json
import sys
import traceback
from datetime import datetime

from . import __version__, config, locate, paths, todo
from .errors import TrackerError

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
LOG_MAX_BYTES = 1_000_000

_ID = {"id": {"type": "string", "description": "The task id, e.g. t-0007."}}
TOOLS = [
    {"name": "tracker_todo",
     "description": "List the open tasks on the user's work tracker (to do, in progress, paused). Call this first when "
                    "work starts, and reuse the id of an open task that matches instead of adding a duplicate.",
     "inputSchema": {"type": "object", "properties": {"all": {"type": "boolean", "description": "Also list done and dropped tasks."}}}},
    {"name": "tracker_add",
     "description": "Add a task to the user's work tracker when a piece of work starts (a feature, fix or investigation; "
                    "not every sub-step) and no open task matches. Returns the new id.",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string", "description": "Short imperative title, e.g. 'Add tenant filter to invoices'."},
         "path": {"type": "string", "description": "The absolute path of your workspace folder; the project and repo are worked out from it."},
         "project": {"type": "string", "description": "Optional: overrides the project worked out from path."},
         "repo": {"type": "string", "description": "Optional: overrides the repo worked out from path."},
         "plan": {"type": "string", "description": "Optional: path of a plan or spec file for this work."}},
         "required": ["title", "path"]}},
    {"name": "tracker_start",
     "description": "Mark a tracker task as in progress once you are actually working on it (also resumes a paused task).",
     "inputSchema": {"type": "object", "properties": dict(_ID), "required": ["id"]}},
    {"name": "tracker_note",
     "description": "Add a progress note to a tracker task at a notable milestone (plan approved, tests passing, PR opened).",
     "inputSchema": {"type": "object", "properties": dict(_ID, text={"type": "string", "description": "The note."}),
                     "required": ["id", "text"]}},
    {"name": "tracker_pause",
     "description": "Put an in-progress tracker task aside when the user switches to other work or it is blocked on someone else.",
     "inputSchema": {"type": "object", "properties": dict(_ID, reason={"type": "string", "description": "Why it is paused."}),
                     "required": ["id"]}},
    {"name": "tracker_done",
     "description": "Mark a tracker task as done, only after the work has been verified (tests run, checked working).",
     "inputSchema": {"type": "object", "properties": dict(_ID), "required": ["id"]}},
    {"name": "tracker_drop",
     "description": "Mark a tracker task as dropped when the work is abandoned or superseded.",
     "inputSchema": {"type": "object", "properties": dict(_ID), "required": ["id"]}},
]
_SCHEMAS = {t["name"]: t["inputSchema"] for t in TOOLS}


def log(text):
    try:
        path = paths.file("mcp.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
            path.replace(path.with_name("mcp.log.1"))
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now().isoformat(timespec="seconds"), text))
    except OSError:
        pass   # logging must never take the server down


def _check_args(name, args):
    schema = _SCHEMAS[name]
    if not isinstance(args, dict):
        raise TrackerError("arguments must be an object")
    for key in schema.get("required", []):
        if key not in args:
            raise TrackerError("missing required argument: %s" % key)
    for key, value in args.items():
        want = schema["properties"].get(key, {}).get("type")
        if want == "string" and not isinstance(value, str) or want == "boolean" and not isinstance(value, bool):
            raise TrackerError("argument %s must be a %s" % (key, want))


def _status_line(item, changed, new):
    return todo.fmt(item) if changed else "already %s: %s" % (new, todo.fmt(item))


def _run_tool(name, args):
    _check_args(name, args)
    if name == "tracker_todo":
        return "\n".join(todo.fmt(i) for i in todo.list_items(args.get("all", False))) or "no open tasks"
    if name == "tracker_add":
        root = config.load().root
        project, repo = locate.project_repo_for(args["path"], root)
        hint = "" if project else "\nnote: %s is not under the tracker's root folder %s, so the task has no project" % (args["path"], root)
        item = todo.add(args["title"], args.get("project") or project, args.get("repo") or repo, args.get("plan"))
        return "%s\n%s%s" % (item["id"], todo.fmt(item), hint)
    if name in ("tracker_start", "tracker_done", "tracker_drop"):
        action = name.split("_")[1]
        item, changed = todo.set_status(args["id"], action)
        return _status_line(item, changed, {"start": "in_progress", "done": "done", "drop": "dropped"}[action])
    if name == "tracker_pause":
        item, changed = todo.pause(args["id"], args.get("reason", ""))
        return _status_line(item, changed, "paused")
    if name == "tracker_note":
        return todo.fmt(todo.note(args["id"], args["text"]))
    raise AssertionError(name)


def call_tool(name, args):
    """-> (text, is_error). Expected problems come back as their message; anything else as 'internal error'."""
    if name not in _SCHEMAS:
        return "unknown tool: %s" % name, True
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            if name != "tracker_add":
                config.load()   # every tool needs a config: one clear message if there isn't one
            text, is_error = _run_tool(name, args), False
    except TrackerError as e:
        text, is_error = str(e), True
    except Exception as e:
        log("tool %s failed:\n%s" % (name, traceback.format_exc()))
        text, is_error = "internal error: %s (details in %s)" % (type(e).__name__, paths.file("mcp.log")), True
    warnings = err.getvalue().strip()
    if warnings:
        log("tool %s: %s" % (name, warnings))
        text += "\n" + warnings
    return text, is_error


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg):
    """One parsed message -> the reply to send, or None for a notification."""
    if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    if "id" not in msg:
        return None   # notifications (initialized, cancelled, ...) are never answered
    mid, method, params = msg["id"], msg["method"], msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion") if isinstance(params, dict) else None
        result = {"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "personal-work-dashboard", "version": __version__}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _error(mid, -32602, "tools/call needs a tool name")
        text, is_error = call_tool(params["name"], params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return _error(mid, -32601, "method not found: %s" % method)
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(stdin, stdout):
    """Read one JSON message per line until stdin closes; each line is handled on its own, so a bad one can't stop the server."""
    for stream, opts in ((stdin, {"newline": "\n"}), (stdout, {"newline": "\n"})):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace", **opts)
    log("start (version %s)" % __version__)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = _error(None, -32700, "parse error")
        else:
            try:
                reply = handle(msg)
            except Exception:
                log("handling failed:\n" + traceback.format_exc())
                reply = _error(msg.get("id") if isinstance(msg, dict) else None, -32603, "internal error")
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()
    log("stdin closed, exiting")
