"""Inline commits.json + tasks.json + todo.json into the page templates.

templates/dashboard.html -> <data folder>/dashboard.html   (always)
<data folder>/desk-template.html -> desk.html              (only if the desk has been built: `cd desk && npm run build`)
"""
import json
import sys
from datetime import datetime
from importlib import resources

from . import __version__, config, files, inks, paths
from .errors import TrackerError
from .links import assign, branch_info


def _branch_list(commits):
    """repo path -> the branches its commits were made on, with first/last commit date and count (for the page's
    branch picker)."""
    seen = {}
    for c in commits:
        if c.get("branch") and c.get("repo_path"):
            b = seen.setdefault(c["repo_path"], {}).setdefault(c["branch"], {"branch": c["branch"], "first": c["date"],
                                                                             "last": c["date"], "count": 0})
            b["first"], b["last"], b["count"] = min(b["first"], c["date"]), max(b["last"], c["date"]), b["count"] + 1
    return {rp: sorted(bs.values(), key=lambda b: b["last"], reverse=True) for rp, bs in sorted(seen.items())}


def _render(html, blob, name):
    assert "/*__DATA__*/null" in html, "%s has no data slot" % name
    out = paths.file(name)
    files.write_text(out, html.replace("/*__DATA__*/null", blob))
    return out


def build():
    """Write dashboard.html (and desk.html when the desk template exists); returns the paths written."""
    paths.home().mkdir(parents=True, exist_ok=True)
    # Serialise builds: concurrent `tracker` calls each rebuild; the last one to run
    # reads the newest todo.json, so the pages never end up stale.
    with files.lock(paths.file("build.lock")):
        cfg = config.load()
        data = files.read_json(paths.file("commits.json"))
        if data is None:   # before the first `tracker scan`: an empty page, so adding tasks doesn't warn
            data = {"generated_at": None, "since": None, "author_pattern": " | ".join(cfg.author_emails), "commits": []}
        data["timezone"], data["version"] = cfg.timezone, __version__
        data["tasks"] = files.read_json(paths.file("tasks.json"), {"tasks": []})["tasks"]
        todo_doc = files.read_json(paths.file("todo.json"), {"items": []})
        data["todo"] = todo_doc["items"]
        _now = datetime.now().astimezone()
        # each task's commits, by branch and date window plus the owner's hand moves (computed fresh every build)
        linked = assign(data["todo"], data["commits"], _now, todo_doc.get("moves"))
        branches = branch_info(data["todo"], data["commits"], _now)
        for it in data["todo"]:
            it["linked"] = [c["repo_path"] + ":" + c["sha"] for c in linked[it["id"]]]
            it["branch_effective"] = branches[it["id"]]
        data["branches"] = _branch_list(data["commits"])
        projects = {c["project"] for c in data["commits"]} | {t["project"] for t in data["tasks"]} | {i["project"] for i in data["todo"] if i.get("project")}
        try:   # inks only colour the desk: a broken ink file must never stop the dashboard from building
            _assigned = inks.assign(sorted(projects), inks.load_assignments())
            inks.save_assignments(_assigned)
            data["inks"] = inks.resolve(_assigned)
        except (OSError, ValueError, KeyError, TrackerError) as e:
            print("warning: ink assignment skipped (%s); the desk will use the fallback ink" % e, file=sys.stderr)
            data["inks"] = {}
        blob = json.dumps(data).replace("</", "<\\/")  # keep commit text from closing the script tag

        written = []
        template = resources.files("personal_tracker").joinpath("templates/dashboard.html").read_text(encoding="utf-8")
        written.append(_render(template, blob, "dashboard.html"))
        print("built", written[-1], "(%d commits, %d tasks)" % (len(data["commits"]), len(data["tasks"])))
        desk_template = paths.file("desk-template.html")
        if desk_template.exists():
            written.append(_render(desk_template.read_text(encoding="utf-8"), blob, "desk.html"))
            print("built", written[-1])
        else:
            print("skipped desk (no desk-template.html; run: cd desk && npm run build)")
        files.write_json(paths.file("dev-data.json"), data)
        return written
