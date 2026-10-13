#!/usr/bin/env python3
"""Inline commits.json + tasks.json + todo.json into the page templates.

template.html      -> dashboard.html   (always)
desk-template.html -> desk.html        (only if the desk has been built: `cd desk && npm run build`)
"""
import fcntl, json, os, sys
from datetime import datetime
from links import link
import inks
HERE = os.path.dirname(os.path.abspath(__file__))
def load(n):
    with open(os.path.join(HERE, n)) as f:
        return json.load(f)
# Serialise builds: concurrent `tracker` calls each rebuild; the last one to run
# reads the newest todo.json, so the pages never end up stale.
_lock = open(os.path.join(HERE, "build.lock"), "w")
fcntl.flock(_lock, fcntl.LOCK_EX)
data = load("commits.json")
data["tasks"] = load("tasks.json")["tasks"]
data["todo"] = load("todo.json")["items"] if os.path.exists(os.path.join(HERE, "todo.json")) else []
_now = datetime.now().astimezone()
for it in data["todo"]:  # commits made while each current-task was open (computed fresh every build)
    it["linked"] = [c["repo_path"] + ":" + c["sha"] for c in link(it, data["commits"], _now)]
projects = {c["project"] for c in data["commits"]} | {t["project"] for t in data["tasks"]} | {i["project"] for i in data["todo"] if i.get("project")}
try:   # inks only colour the desk: a broken ink file must never stop the dashboard from building
    _assigned = inks.assign(sorted(projects), inks.load_assignments())
    inks.save_assignments(_assigned)
    data["inks"] = inks.resolve(_assigned)
except (OSError, ValueError, KeyError) as e:
    print("warning: ink assignment skipped (%s); the desk will use the fallback ink" % e, file=sys.stderr)
    data["inks"] = {}
blob = json.dumps(data).replace("</", "<\\/")  # keep commit text from closing the script tag


def render(template, out):
    with open(os.path.join(HERE, template)) as f:
        html = f.read()
    assert "/*__DATA__*/null" in html, "%s has no data slot" % template
    path = os.path.join(HERE, out)
    with open(path + ".tmp", "w") as f:
        f.write(html.replace("/*__DATA__*/null", blob))
    os.replace(path + ".tmp", path)
    return path


print("built", render("template.html", "dashboard.html"), "(%d commits, %d tasks)" % (len(data["commits"]), len(data["tasks"])))
if os.path.exists(os.path.join(HERE, "desk-template.html")):
    print("built", render("desk-template.html", "desk.html"))
else:
    print("skipped desk (no desk-template.html; run: cd desk && npm run build)")
os.makedirs(os.path.join(HERE, "desk"), exist_ok=True)
with open(os.path.join(HERE, "desk", "dev-data.json"), "w") as f:
    json.dump(data, f)
