#!/usr/bin/env python3
"""Inline commits.json + tasks.json into template.html -> dashboard.html."""
import fcntl, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
def load(n):
    with open(os.path.join(HERE, n)) as f:
        return json.load(f)
# Serialise builds: concurrent `tracker` calls each rebuild; the last one to run
# reads the newest todo.json, so the page never ends up stale.
_lock = open(os.path.join(HERE, "build.lock"), "w")
fcntl.flock(_lock, fcntl.LOCK_EX)
data = load("commits.json")
data["tasks"] = load("tasks.json")["tasks"]
data["todo"] = load("todo.json")["items"] if os.path.exists(os.path.join(HERE, "todo.json")) else []
blob = json.dumps(data).replace("</", "<\\/")  # keep commit text from closing the script tag
with open(os.path.join(HERE, "template.html")) as f:
    html = f.read()
assert "/*__DATA__*/null" in html
out = os.path.join(HERE, "dashboard.html")
with open(out + ".tmp", "w") as f:
    f.write(html.replace("/*__DATA__*/null", blob))
os.replace(out + ".tmp", out)
print("built", out, "(%d commits, %d tasks)" % (len(data["commits"]), len(data["tasks"])))
