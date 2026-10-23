"""Scan every git repo under the configured root for the user's commits -> commits.json.

Default window is 14 days. Existing commits.json is merged by hash, so history
older than the window is kept once it has been seen.
"""
import os
import subprocess
from datetime import datetime, timedelta

from . import config, files, paths

SEP = "\x1e"  # record separator between commits
FIELD = "\x1f"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout


def find_repos(root):
    root = str(root)
    for dirpath, dirnames, _ in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if ".git" in dirnames:
            dirnames[:] = []  # don't descend into a repo
            yield dirpath
        elif depth >= 3:
            dirnames[:] = []


def scan_repo(repo, since, patterns):
    fmt = FIELD.join(["%H", "%an", "%ae", "%aI", "%s", "%b", "%D"]) + SEP
    # --branches --remotes (not --all) so refs/stash entries are excluded
    out = git(repo, "log", "--branches", "--remotes", "--since=" + since,
              *["--author=" + a for a in patterns],
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
               *["--author=" + a for a in patterns],
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


def run(days=14, since=None):
    """Scan every repo under the configured root; returns how many commits commits.json now holds."""
    cfg = config.load()
    root, patterns = str(cfg.root), cfg.author_emails
    since = since or (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    out = paths.file("commits.json")

    existing = {}
    for c in (files.read_json(out) or {}).get("commits", []):
        existing[(c["repo_path"], c["sha"])] = c

    for repo in find_repos(root):
        rel = os.path.relpath(repo, root)
        project = rel.split(os.sep)[0]
        for sha, c in scan_repo(repo, since, patterns).items():
            c.update({"repo_path": rel, "repo": os.path.basename(rel), "project": project})
            existing[(rel, sha)] = c  # same hash in same repo = one commit

    commits = sorted(existing.values(), key=lambda c: c["date"])
    payload = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "since": since, "author_pattern": " | ".join(patterns), "commits": commits}
    paths.home().mkdir(parents=True, exist_ok=True)
    files.write_json(out, payload)
    print("wrote %d commits across %d repos -> %s" % (
        len(commits), len({c["repo_path"] for c in commits}), out))
    return len(commits)
