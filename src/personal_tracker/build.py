"""Inline commits.json + tasks.json + todo.json into the page templates.

templates/dashboard.html -> <data folder>/dashboard.html   (always)
<data folder>/desk-template.html -> desk.html              (only if the desk has been built: `cd desk && npm run build`)
"""
import json
import sys
from datetime import datetime
from importlib import resources

from . import files, inks, paths
from .errors import TrackerError
from .links import link


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
        data = files.read_json(paths.file("commits.json"))
        if data is None:
            raise TrackerError("no commits.json yet -- run: tracker scan")
        data["tasks"] = files.read_json(paths.file("tasks.json"), {"tasks": []})["tasks"]
        data["todo"] = files.read_json(paths.file("todo.json"), {"items": []})["items"]
        _now = datetime.now().astimezone()
        for it in data["todo"]:  # commits made while each current-task was open (computed fresh every build)
            it["linked"] = [c["repo_path"] + ":" + c["sha"] for c in link(it, data["commits"], _now)]
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
