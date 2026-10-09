#!/usr/bin/env python3
"""Summarise commits that no task covers yet, using `claude -p` (no tools, JSON out).

Claude only returns JSON; this script validates it and merges it into tasks.json.
Exit 0 with nothing to do is normal. On any failure tasks.json is left untouched
and the dashboard keeps showing those commits as 'unsummarised'.
"""
import json, os, re, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
IST = ZoneInfo("Asia/Kolkata")
KINDS = {"feature", "fix", "infra", "docs"}

def load(n):
    with open(os.path.join(HERE, n)) as f:
        return json.load(f)

def ist(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)  # py3.9 can't parse "Z"

commits = load("commits.json")["commits"]
tasks_doc = load("tasks.json")
covered = [p for t in tasks_doc["tasks"] for p in t["commits"]]
orphans = [c for c in commits if not any(c["sha"].startswith(p) for p in covered)]
if not orphans:
    print("nothing to summarise"); sys.exit(0)

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
- Output ONLY a JSON object, no prose, no code fences:
  {"tasks":[{"date":"YYYY-MM-DD","project":"...","kind":"feature|fix|infra|docs","title":"short title","summary":"1-2 sentences on what was done and why","details":["bullet","bullet"],"commits":["sha7","sha7"]}]}

Commits:
""" + "\n".join(lines)

env = dict(os.environ)
r = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence", "--output-format", "text", prompt],
                   capture_output=True, text=True, timeout=600, env=env, stdin=subprocess.DEVNULL)
if r.returncode != 0:
    sys.exit("claude -p failed (%d): stderr=%s stdout=%s" % (r.returncode, r.stderr.strip()[:500], r.stdout.strip()[:500]))
txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.stdout.strip())
try:
    new = json.loads(txt)["tasks"]
except Exception as e:
    sys.exit("could not parse claude output as JSON: %s\n%s" % (e, txt[:500]))

want = {c["sha"][:7]: c for c in orphans}
seen = []
for t in new:
    assert t.get("kind") in KINDS, "bad kind: %r" % t.get("kind")
    assert t.get("title") and t.get("summary"), "missing title/summary"
    assert isinstance(t.get("details"), list) and t["commits"], "bad details/commits"
    for p in t["commits"]:
        assert p in want, "unknown sha %s" % p
        c = want[p]
        assert str(ist(c["date"]).date()) == t["date"], "date mismatch for %s" % p
        assert c["project"] == t["project"], "project mismatch for %s" % p
        seen.append(p)
assert sorted(seen) == sorted(want), "coverage mismatch: missing %s, dupes %s" % (
    sorted(set(want) - set(seen)), sorted({p for p in seen if seen.count(p) > 1}))

for i, t in enumerate(new, 1):
    t["id"] = "auto-%s-%s-%d" % (t["date"], t["project"], i)
tasks_doc["tasks"].extend(new)
out = os.path.join(HERE, "tasks.json")
with open(out + ".tmp", "w") as f:
    json.dump(tasks_doc, f, indent=1, ensure_ascii=False)
os.replace(out + ".tmp", out)
print("added %d tasks covering %d commits" % (len(new), len(seen)))
