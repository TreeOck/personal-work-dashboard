"""Current-tasks list for the personal tracker (todo.json).

Every change takes an exclusive lock, writes atomically, then rebuilds dashboard.html.
The CLI (cli.py) is a thin layer over the functions below.
"""
import io
import os
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime

from . import config, files, paths
from .errors import TrackerError

STATUSES = ("todo", "in_progress", "paused", "done", "dropped")
OPEN = ("todo", "in_progress", "paused")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


@contextmanager
def locked():
    """Yield the todo.json document under the exclusive lock; it is written back on a clean exit."""
    paths.home().mkdir(parents=True, exist_ok=True)
    with files.lock(paths.file("todo.json.lock")):
        doc = files.read_json(paths.file("todo.json"), {"items": []})
        yield doc
        files.write_json(paths.file("todo.json"), doc)


def rebuild():
    from . import build
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):   # `tracker add` must print only the id
            build.build()
    except Exception as e:   # a failed page rebuild must never lose the edit that was just saved
        print("warning: dashboard rebuild failed:\n" + str(e)[-400:], file=sys.stderr)


def scan():
    from . import scan as scanner
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            scanner.run()
    except Exception as e:
        print("warning: git scan failed, linking uses the last scan:\n" + str(e)[-300:], file=sys.stderr)


def find(doc, tid):
    for it in doc["items"]:
        if it["id"] == tid:
            return it
    raise TrackerError("no task with id %s (run: tracker todo --all)" % tid)


def fmt(it):
    where = "/".join(x for x in (it.get("project"), it.get("repo")) if x) or "-"
    return "%s  %-11s %-34s %s" % (it["id"], it["status"], where, it["title"])


def list_items(all_=False):
    doc = files.read_json(paths.file("todo.json"), {"items": []})
    return [i for i in doc["items"] if all_ or i["status"] in OPEN]


def add(title, project=None, repo=None, plan=None):
    title = title.strip()
    if not title:
        raise TrackerError("title can't be empty")
    cfg = config.load()
    if project and not (cfg.root / project).is_dir():
        print("warning: %s doesn't exist; keeping it anyway" % (cfg.root / project), file=sys.stderr)
    with locked() as doc:
        nxt = 1 + max([int(i["id"][2:]) for i in doc["items"]] or [0])
        it = {"id": "t-%04d" % nxt, "title": title, "project": project, "repo": repo,
              "plan": os.path.abspath(plan) if plan else None, "status": "todo",
              "created_at": now(), "updated_at": now(), "started_at": None, "closed_at": None, "notes": []}
        doc["items"].append(it)
    rebuild()
    return it


def note(tid, text):
    text = text.strip()
    if not text:
        raise TrackerError("note can't be empty")
    with locked() as doc:
        it = find(doc, tid)
        it["notes"].append({"at": now(), "text": text})
        it["updated_at"] = now()
    rebuild()
    return it


def pause(tid, reason=""):
    """Put an in-progress task aside. Returns (item, changed); pausing a paused task is a no-op."""
    with locked() as doc:
        it = find(doc, tid)
        if it["status"] == "paused":
            return it, False
        if it["status"] != "in_progress":
            raise TrackerError("can only pause a task that's in progress (%s is %s)" % (it["id"], it["status"]))
        it["status"], it["paused_at"], it["updated_at"] = "paused", now(), now()
        if reason.strip():
            it["notes"].append({"at": now(), "text": "Paused: " + reason.strip()})
    rebuild()
    return it, True


def set_status(tid, action):
    """action is start, done or drop. Returns (item, changed); asking for the status it already has is a no-op."""
    new = {"start": "in_progress", "done": "done", "drop": "dropped"}[action]
    with locked() as doc:
        it = find(doc, tid)
        if it["status"] == new:
            return it, False
        if new == "done":
            scan()  # pick up commits made since the last refresh so they get linked
        if it.get("paused_at"):  # leaving a pause: keep the gap so its commits aren't linked
            it.setdefault("pauses", []).append({"from": it["paused_at"], "to": now()})
            it["paused_at"] = None
        it["status"], it["updated_at"] = new, now()
        it["closed_at"] = now() if new in ("done", "dropped") else None
        if new == "in_progress" and not it.get("started_at"):
            it["started_at"] = now()  # first start only; re-opening keeps the original
    rebuild()
    return it, True
