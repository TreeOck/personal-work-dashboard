#!/usr/bin/env python3
"""Summarise commits that no task covers yet, using `claude -p` (no tools, JSON out).

  python3 summarise.py                     # summarise new commits (run by refresh.sh)
  python3 summarise.py --backfill-threads  # give a thread to every task that has none

Claude only returns JSON; this script validates it and merges it into tasks.json.
On any failure tasks.json is left untouched and the dashboard keeps showing those
commits as 'unsummarised' (or the tasks without a thread).
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
IST = ZoneInfo("Asia/Kolkata")
KINDS = {"feature", "fix", "infra", "docs"}


def load(n):
    with open(os.path.join(HERE, n)) as f:
        return json.load(f)


def save_tasks(doc):
    out = os.path.join(HERE, "tasks.json")
    with open(out + ".tmp", "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    os.replace(out + ".tmp", out)


def ist(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)  # py3.9 can't parse "Z"


def thread_projects(tasks):
    """thread name -> project, from tasks that already have a thread."""
    return {t["thread"]: t["project"] for t in tasks if t.get("thread")}


def unique_id(base, taken):
    i = 1
    while "%s-%d" % (base, i) in taken:
        i += 1
    taken.add("%s-%d" % (base, i))
    return "%s-%d" % (base, i)


def validate_new_tasks(new, orphans, known_threads):
    """Raise ValueError unless `new` covers every orphan commit exactly once, on the
    right date and project, and each thread stays inside one project."""
    want = {c["sha"][:7]: c for c in orphans}
    seen, threads = [], dict(known_threads)
    for t in new:
        if t.get("kind") not in KINDS:
            raise ValueError("bad kind: %r" % t.get("kind"))
        if not (t.get("title") and t.get("summary")):
            raise ValueError("missing title/summary")
        if not isinstance(t.get("details"), list) or not t.get("commits"):
            raise ValueError("bad details/commits")
        th = (t.get("thread") or "").strip()
        if not th:
            raise ValueError("missing thread for %r" % t["title"])
        if threads.setdefault(th, t["project"]) != t["project"]:
            raise ValueError("thread %r used in two projects" % th)
        for p in t["commits"]:
            if p not in want:
                raise ValueError("unknown sha %s" % p)
            c = want[p]
            if str(ist(c["date"]).date()) != t["date"]:
                raise ValueError("date mismatch for %s" % p)
            if c["project"] != t["project"]:
                raise ValueError("project mismatch for %s" % p)
            seen.append(p)
    if sorted(seen) != sorted(want):
        raise ValueError("coverage mismatch: missing %s, dupes %s" % (
            sorted(set(want) - set(seen)), sorted({p for p in seen if seen.count(p) > 1})))


def validate_backfill(assign, tasks, known_threads):
    """`assign` maps task id -> thread for every task lacking one; threads stay per-project."""
    need = {t["id"]: t for t in tasks if not t.get("thread")}
    if set(assign) != set(need):
        raise ValueError("ids mismatch: missing %s, unknown %s" % (
            sorted(set(need) - set(assign)), sorted(set(assign) - set(need))))
    threads = dict(known_threads)
    for tid, th in assign.items():
        th = (th or "").strip()
        if not th:
            raise ValueError("empty thread for %s" % tid)
        if threads.setdefault(th, need[tid]["project"]) != need[tid]["project"]:
            raise ValueError("thread %r used in two projects" % th)


def ask_claude(prompt):
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--output-format", "text", prompt],
                       capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        sys.exit("claude -p failed (%d): stderr=%s stdout=%s" % (r.returncode, r.stderr.strip()[:500], r.stdout.strip()[:500]))
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.stdout.strip())
    try:
        return json.loads(txt)
    except Exception as e:
        sys.exit("could not parse claude output as JSON: %s\n%s" % (e, txt[:500]))


def threads_hint(tasks):
    by = {}
    for t in tasks:
        if t.get("thread"):
            by.setdefault(t["project"], {})[t["thread"]] = t["date"]
    if not by:
        return "(none yet)"
    return "\n".join("- %s: %s" % (p, "; ".join("%s (last %s)" % kv for kv in sorted(th.items(), key=lambda kv: kv[1])[-15:]))
                     for p, th in sorted(by.items()))


THREAD_RULES = """A "thread" names a piece of work that can span several days, e.g. "DMS Wave 4: versioning" or
"km-investigation-be Foundation". Reuse an existing thread name EXACTLY when the work continues it;
otherwise make a new short name. A thread belongs to one project only."""


def summarise():
    commits = load("commits.json")["commits"]
    doc = load("tasks.json")
    covered = [p for t in doc["tasks"] for p in t["commits"]]
    orphans = [c for c in commits if not any(c["sha"].startswith(p) for p in covered)]
    if not orphans:
        print("nothing to summarise")
        return
    lines = []
    for c in sorted(orphans, key=lambda c: c["date"]):
        d = ist(c["date"])
        lines.append("- sha=%s date=%s time=%s project=%s repo=%s +%d/-%d\n  subject: %s\n  body: %s\n  files: %s" % (
            c["sha"][:7], d.date(), d.strftime("%H:%M"), c["project"], c["repo"], c["ins"], c["del"],
            c["subject"], (c["body"] or "(none)")[:700].replace("\n", " "), ", ".join(c["files"][:15]) or "(none)"))
    prompt = """You are writing entries for a personal work tracker. Group the git commits below into tasks.

Rules:
- A task groups related commits from the SAME date and SAME project (it may span repos).
- Every sha must appear in exactly one task. Use the 7-char sha exactly as given.
- Use ONLY facts present in the commit data below. Do not invent features, numbers or outcomes.
- """ + THREAD_RULES.replace("\n", " ") + """
- Output ONLY a JSON object, no prose, no code fences:
  {"tasks":[{"date":"YYYY-MM-DD","project":"...","kind":"feature|fix|infra|docs","thread":"thread name","title":"short title","summary":"1-2 sentences on what was done and why","details":["bullet","bullet"],"commits":["sha7","sha7"]}]}

Existing threads by project:
""" + threads_hint(doc["tasks"]) + "\n\nCommits:\n" + "\n".join(lines)
    try:
        new = ask_claude(prompt)["tasks"]
        validate_new_tasks(new, orphans, thread_projects(doc["tasks"]))
    except (KeyError, TypeError, ValueError) as e:
        sys.exit("rejected claude output: %s" % e)
    taken = {t["id"] for t in doc["tasks"]}
    for t in new:
        t["thread"] = t["thread"].strip()
        t["id"] = unique_id("auto-%s-%s" % (t["date"], t["project"]), taken)
    doc["tasks"].extend(new)
    save_tasks(doc)
    print("added %d tasks covering %d commits" % (len(new), len(orphans)))


def backfill_threads():
    doc = load("tasks.json")
    need = [t for t in doc["tasks"] if not t.get("thread")]
    if not need:
        print("every task already has a thread")
        return
    rows = "\n".join("- id=%s date=%s project=%s kind=%s title: %s | %s" % (
        t["id"], t["date"], t["project"], t["kind"], t["title"], t["summary"][:200]) for t in sorted(need, key=lambda t: t["date"]))
    prompt = """Assign a thread to each task of a personal work tracker. """ + THREAD_RULES.replace("\n", " ") + """
Group consecutive related tasks of the same project into the same thread; a one-off task gets its own thread.

Output ONLY a JSON object mapping every task id to its thread name, no prose, no code fences:
{"threads": {"<task id>": "<thread name>"}}

Existing threads by project:
""" + threads_hint(doc["tasks"]) + "\n\nTasks:\n" + rows
    try:
        assign = ask_claude(prompt)["threads"]
        validate_backfill(assign, doc["tasks"], thread_projects(doc["tasks"]))
    except (KeyError, TypeError, ValueError) as e:
        sys.exit("rejected claude output: %s" % e)
    for t in need:
        t["thread"] = assign[t["id"]].strip()
    save_tasks(doc)
    print("assigned threads to %d tasks (%d threads)" % (len(need), len({t["thread"] for t in need})))


def dedupe_ids(doc):
    """Older runs could reuse auto ids; give later duplicates a fresh id. Returns count fixed."""
    taken, fixed = set(), 0
    for t in doc["tasks"]:
        if t["id"] in taken:
            base = t["id"].rsplit("-", 1)[0]
            t["id"] = unique_id(base, taken | {x["id"] for x in doc["tasks"]})
            fixed += 1
        taken.add(t["id"])
    return fixed


if __name__ == "__main__":
    doc = load("tasks.json")
    if dedupe_ids(doc):
        save_tasks(doc)
    backfill_threads() if "--backfill-threads" in sys.argv else summarise()
