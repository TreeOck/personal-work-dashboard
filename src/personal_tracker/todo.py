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


def _record_branch(doc, it, path, cfg):
    """Remember the branch the task is worked on (auto), once: only if nothing is recorded yet, the task has a repo,
    and no other open task already holds that branch (a plan is often written before `git checkout -b`)."""
    from . import locate
    if it.get("branch_source") or not it.get("project") or not it.get("repo"):
        return
    if path is None:
        folder = locate.repo_folder(cfg.root, it["project"], it["repo"])
        path = str(folder) if folder else None
    found = locate.current_branch(path, cfg.root) if path else None
    if not found:
        return
    repo_path, branch = found
    others = [o for o in doc["items"] if o is not it and o.get("status") in ("in_progress", "paused")]
    if any(o.get("branch") == branch and o.get("branch_repo") == repo_path for o in others):
        return
    if any(o.get("project") == it["project"] and o.get("repo") == it["repo"] for o in others):
        # another task is open in this repo: a branch that already has commits of its own (on no other branch) is
        # probably that task's (started before `git checkout -b`); one fresh from `checkout -b` has none yet
        from . import scan
        own = scan.git(str(cfg.root / repo_path), "rev-list", "--count", "refs/heads/" + branch, "--not",
                       "--exclude=" + branch, "--branches", "--")   # --exclude takes the bare name with --branches
        if own.strip() != "0":
            return
    it["branch"], it["branch_repo"], it["branch_source"] = branch, repo_path, "auto"


def add(title, project=None, repo=None, plan=None, path=None):
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
        if path:
            _record_branch(doc, it, path, cfg)
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


def set_status(tid, action, path=None):
    """action is start, done or drop. Returns (item, changed); asking for the status it already has is a no-op.
    Starting records the task's branch (see _record_branch), from `path` (the agent's folder) or the repo's folder."""
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
        if new == "in_progress":
            _record_branch(doc, it, path, config.load())
        if new == "in_progress" and not it.get("started_at"):
            it["started_at"] = now()  # first start only; re-opening keeps the original
    rebuild()
    return it, True


# ---- hand corrections (step 3) --------------------------------------------------------------------------------------

def _commits():
    return (files.read_json(paths.file("commits.json")) or {}).get("commits", [])


def set_branch(tid, branch, repo=None):
    """Set a task's branch by hand: a branch name, None (dates only) or "auto" (back to automatic).
    The branch is stored with its repo path; a task without a repo needs `repo` when several of its project's repos
    have commits on that branch."""
    with locked() as doc:
        it = find(doc, tid)
        if branch == "auto":
            for k in ("branch", "branch_repo", "branch_source"):
                it.pop(k, None)
        elif branch is None:
            it["branch"], it["branch_repo"], it["branch_source"] = None, None, "manual"
        else:
            it["branch"], it["branch_repo"], it["branch_source"] = branch, _branch_repo(it, branch, repo), "manual"
        it["updated_at"] = now()
    rebuild()
    return it


def _branch_repo(it, branch, repo):
    if repo:
        return repo.strip("/")
    commits = _commits()
    if it.get("repo"):
        for c in commits:
            if c.get("project") == it.get("project") and c.get("repo") == it["repo"]:
                return c["repo_path"]
        return "%s/%s" % (it.get("project"), it["repo"])
    have = sorted({c["repo_path"] for c in commits if c.get("project") == it.get("project") and c.get("branch") == branch})
    if not have:
        raise TrackerError("no commits on branch %s in project %s (pass --repo to set it anyway)" % (branch, it.get("project")))
    if len(have) > 1:
        raise TrackerError("branch %s is in several repos: %s -- pass --repo" % (branch, ", ".join(have)))
    return have[0]


def move(sha, target):
    """Put a commit on these task ids, on no task (None) or back to automatic ("auto"). Returns its key."""
    sha = sha.strip().lower()
    keys = sorted({"%s:%s" % (c["repo_path"], c["sha"]) for c in _commits() if c["sha"].startswith(sha)})
    if not keys:
        raise TrackerError("no commit %s in the scanned commits (run: tracker scan)" % sha)
    if len(keys) > 1:
        raise TrackerError("%s matches %d commits: %s -- use more characters" % (sha, len(keys), ", ".join(keys)))
    key = keys[0]
    with locked() as doc:
        moves = doc.setdefault("moves", {})
        if target == "auto":
            moves.pop(key, None)
        else:
            ids = list(dict.fromkeys(target or []))
            for tid in ids:
                find(doc, tid)
            moves[key] = ids
        if not moves:
            doc.pop("moves")
    rebuild()
    return key
