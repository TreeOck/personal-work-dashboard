#!/usr/bin/env python3
"""Scan every git repo under the configured root for the user's commits -> commits.json.

Usage: python3 scan.py [--days N] [--since YYYY-MM-DD]
Default window is 14 days. Existing commits.json is merged by hash, so history
older than the window is kept once it has been seen.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta

from config import ROOT, AUTHOR_EMAILS
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "commits.json")
AUTHOR_PATTERNS = AUTHOR_EMAILS  # every identity you commit as
AUTHOR_PATTERN = " | ".join(AUTHOR_PATTERNS)
SEP = "\x1e"  # record separator between commits
FIELD = "\x1f"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True, errors="replace",
    ).stdout


def find_repos():
    for dirpath, dirnames, _ in os.walk(ROOT):
        depth = dirpath[len(ROOT):].count(os.sep)
        if ".git" in dirnames:
            dirnames[:] = []  # don't descend into a repo
            yield dirpath
        elif depth >= 3:
            dirnames[:] = []


def scan_repo(repo, since):
    fmt = FIELD.join(["%H", "%an", "%ae", "%aI", "%s", "%b", "%D"]) + SEP
    # --branches --remotes (not --all) so refs/stash entries are excluded
    out = git(repo, "log", "--branches", "--remotes", "--since=" + since,
              *["--author=" + a for a in AUTHOR_PATTERNS],
              "--format=" + SEP + fmt)
    commits = {}
    for rec in out.split(SEP):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split(FIELD)
        if len(parts) < 7:
            continue
        sha, name, email, date, subj, body, refs = parts[:7]
        commits[sha] = {"sha": sha, "author": name, "email": email, "date": date,
                        "subject": subj, "body": body.strip(), "files": [], "ins": 0, "del": 0}
    # second pass for per-file stats (kept separate so body text can't corrupt parsing)
    stat = git(repo, "log", "--branches", "--remotes", "--since=" + since,
               *["--author=" + a for a in AUTHOR_PATTERNS],
               "--numstat", "--format=@@%H")
    cur = None
    for line in stat.splitlines():
        if line.startswith("@@"):
            cur = commits.get(line[2:])
        elif line.strip() and cur is not None:
            a, d, path = (line.split("\t") + ["", "", ""])[:3]
            cur["files"].append(path)
            cur["ins"] += int(a) if a.isdigit() else 0
            cur["del"] += int(d) if d.isdigit() else 0
    # branches containing each commit
    for sha, c in commits.items():
        br = git(repo, "branch", "-a", "--contains", sha, "--format=%(refname:short)")
        c["branches"] = sorted({b.strip() for b in br.splitlines() if b.strip()})[:6]
    return commits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--since")
    args = ap.parse_args()
    since = args.since or (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    existing = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            for c in json.load(f).get("commits", []):
                existing[(c["repo_path"], c["sha"])] = c

    for repo in find_repos():
        rel = os.path.relpath(repo, ROOT)
        project = rel.split(os.sep)[0]
        for sha, c in scan_repo(repo, since).items():
            c.update({"repo_path": rel, "repo": os.path.basename(rel), "project": project})
            existing[(rel, sha)] = c  # same hash in same repo = one commit

    commits = sorted(existing.values(), key=lambda c: c["date"])
    payload = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "since": since, "author_pattern": AUTHOR_PATTERN, "commits": commits}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=1)
    os.replace(tmp, OUT)
    print("wrote %d commits across %d repos -> %s" % (
        len(commits), len({c["repo_path"] for c in commits}), OUT))


if __name__ == "__main__":
    main()
