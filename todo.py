#!/usr/bin/env python3
"""Current-tasks list for the personal tracker (todo.json).

  add "Title" [-p project] [-r repo] [--plan path]   -> prints new id
  start|done|drop ID
  note ID "text"
  todo [--all]                                       -> list open (or all) tasks

Every change takes an exclusive lock, writes atomically, then rebuilds dashboard.html.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "todo.json")
from config import ROOT
STATUSES = ("todo", "in_progress", "done", "dropped")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


@contextmanager
def locked():
    with open(PATH + ".lock", "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)  # serialises concurrent Claude sessions
        doc = {"items": []}
        if os.path.exists(PATH):
            with open(PATH) as f:
                doc = json.load(f)
        yield doc
        with open(PATH + ".tmp", "w") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
        os.replace(PATH + ".tmp", PATH)


def rebuild():
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py")], capture_output=True, text=True)
    if r.returncode != 0:
        print("warning: dashboard rebuild failed:\n" + r.stderr.strip()[-400:], file=sys.stderr)


def find(doc, tid):
    for it in doc["items"]:
        if it["id"] == tid:
            return it
    sys.exit("no task with id %s (run: tracker todo --all)" % tid)


def fmt(it):
    where = "/".join(x for x in (it.get("project"), it.get("repo")) if x) or "-"
    return "%s  %-11s %-34s %s" % (it["id"], it["status"], where, it["title"])


def main():
    ap = argparse.ArgumentParser(prog="tracker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("title"); a.add_argument("-p", "--project")
    a.add_argument("-r", "--repo"); a.add_argument("--plan")
    for c in ("start", "done", "drop"):
        sub.add_parser(c).add_argument("id")
    n = sub.add_parser("note"); n.add_argument("id"); n.add_argument("text")
    sub.add_parser("todo").add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.cmd == "todo":
        doc = json.load(open(PATH)) if os.path.exists(PATH) else {"items": []}
        rows = [i for i in doc["items"] if args.all or i["status"] in ("todo", "in_progress")]
        print("\n".join(fmt(i) for i in rows) or "no open tasks")
        return

    with locked() as doc:
        if args.cmd == "add":
            title = args.title.strip()
            if not title:
                sys.exit("title can't be empty")
            if args.project and not os.path.isdir(os.path.join(ROOT, args.project)):
                print("warning: %s doesn't exist; keeping it anyway" % os.path.join(ROOT, args.project), file=sys.stderr)
            nxt = 1 + max([int(i["id"][2:]) for i in doc["items"]] or [0])
            it = {"id": "t-%04d" % nxt, "title": title, "project": args.project, "repo": args.repo,
                  "plan": os.path.abspath(args.plan) if args.plan else None, "status": "todo",
                  "created_at": now(), "updated_at": now(), "closed_at": None, "notes": []}
            doc["items"].append(it)
            print(it["id"])
        elif args.cmd == "note":
            it = find(doc, args.id)
            it["notes"].append({"at": now(), "text": args.text.strip()})
            it["updated_at"] = now()
            print(fmt(it))
        else:
            it = find(doc, args.id)
            new = {"start": "in_progress", "done": "done", "drop": "dropped"}[args.cmd]
            if it["status"] == new:
                print("already %s: %s" % (new, fmt(it)))
                return
            it["status"], it["updated_at"] = new, now()
            it["closed_at"] = now() if new in ("done", "dropped") else None
            print(fmt(it))
    rebuild()


if __name__ == "__main__":
    main()
