"""Scan every git repo under the configured root for the user's commits -> commits.json.

Default window is 14 days. Existing commits.json is merged by hash, so history
older than the window is kept once it has been seen.
"""
import os
import shutil
import subprocess
from datetime import datetime, timedelta

from . import config, files, paths, procs
from .errors import TrackerError

SEP = "\x1e"  # record separator between commits
FIELD = "\x1f"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace", **procs.no_window(),
    ).stdout


def rel_posix(repo, root, pathmod=os.path):
    """Repo path relative to the root, always with "/" (stored in commits.json and matched by the page)."""
    return pathmod.relpath(repo, root).replace(pathmod.sep, "/")


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


def default_branch(repo):
    """main, else master, else the branch origin/HEAD points to; None if none of them exists."""
    for name in ("main", "master"):
        if git(repo, "rev-parse", "--verify", "-q", "refs/heads/" + name).strip():
            return name
    ref = git(repo, "symbolic-ref", "-q", "refs/remotes/origin/HEAD").strip()
    return ref.split("/", 3)[-1] if ref.startswith("refs/remotes/origin/") else None


def made_on(repo, default):
    """full sha -> the branch it was made on, for commits that can still be told apart.
    Best source: each branch's reflog, whose "commit" entries are exactly the commits made on it (also from other
    worktrees). For commits with no such entry: a branch that has them while the default branch doesn't."""
    branches = [b.strip() for b in git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/").splitlines()
                if b.strip() and b.strip() != default]
    out = {}
    for b in branches:
        for line in git(repo, "reflog", "show", "--format=%H" + FIELD + "%gs", "refs/heads/" + b, "--").splitlines():
            sha, _, subject = line.partition(FIELD)
            if subject.startswith(("commit", "cherry-pick")) and sha not in out:
                out[sha] = b
    if default:
        for b in branches:
            for sha in git(repo, "rev-list", "refs/heads/%s..refs/heads/%s" % (default, b), "--").split():
                out.setdefault(sha, b)
    return out


def run(days=14, since=None):
    """Scan every repo under the configured root; returns how many commits commits.json now holds."""
    if not shutil.which("git"):
        raise TrackerError("git not found on PATH -- install git and try again")
    cfg = config.load()
    root, patterns = str(cfg.root), cfg.author_emails
    since = since or (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    out = paths.file("commits.json")

    existing = {}
    for c in (files.read_json(out) or {}).get("commits", []):
        existing[(c["repo_path"], c["sha"])] = c

    for repo in find_repos(root):
        rel = rel_posix(repo, root)
        project = rel.split("/")[0]
        made = made_on(repo, default_branch(repo))
        for sha, c in scan_repo(repo, since, patterns).items():
            c.update({"repo_path": rel, "repo": rel.split("/")[-1], "project": project})
            old = existing.get((rel, sha), {})
            c["branch"] = old.get("branch") or made.get(sha)   # once known, kept: the branch may be merged and deleted later
            existing[(rel, sha)] = c  # same hash in same repo = one commit

    commits = sorted(existing.values(), key=lambda c: c["date"])
    payload = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "since": since, "author_pattern": " | ".join(patterns), "commits": commits}
    paths.home().mkdir(parents=True, exist_ok=True)
    files.write_json(out, payload)
    print("wrote %d commits across %d repos -> %s" % (
        len(commits), len({c["repo_path"] for c in commits}), out))
    return len(commits)
