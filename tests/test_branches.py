"""Which branch each commit was made on (scanner, step 3)."""
import json
import subprocess

from personal_tracker import scan


def g(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=Me", "-c", "user.email=me@example.com", *args],
                       check=True, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def commit(repo, msg):
    g(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return g(repo, "rev-parse", "HEAD")


def new_repo(path, branch="main"):
    path.mkdir(parents=True)
    g(path, "init", "-q", "-b", branch)
    commit(path, "base")
    return path


def test_reflog_names_the_branch_incl_amend_and_second_worktree(tmp_path):
    repo = new_repo(tmp_path / "app")
    g(repo, "checkout", "-q", "-b", "feat/a")
    a1 = commit(repo, "a1")
    commit(repo, "a2")
    g(repo, "commit", "-q", "--amend", "--allow-empty", "-m", "a2 amended")
    a2 = g(repo, "rev-parse", "HEAD")
    g(repo, "checkout", "-q", "main")
    base = g(repo, "rev-parse", "HEAD")
    wt = tmp_path / "wt"
    g(repo, "worktree", "add", "-q", "-b", "feat/b", str(wt))
    b1 = commit(wt, "b1")
    got = scan.made_on(str(repo), "main")
    assert got[a1] == "feat/a" and got[a2] == "feat/a" and got[b1] == "feat/b"
    assert base not in got


def test_unique_to_branch_fallback(tmp_path):
    repo = new_repo(tmp_path / "app")
    base = g(repo, "rev-parse", "HEAD")
    tree = g(repo, "rev-parse", "HEAD^{tree}")
    c = g(repo, "commit-tree", tree, "-p", base, "-m", "made without a reflog entry")
    g(repo, "update-ref", "refs/heads/feat/c", c)
    assert scan.made_on(str(repo), "main") == {c: "feat/c"}


def test_branch_remembered_after_ff_merge_and_delete(sandbox):
    repo = new_repo(sandbox.root / "proj" / "app")
    g(repo, "checkout", "-q", "-b", "feat/a")
    a1 = commit(repo, "a1")
    g(repo, "checkout", "-q", "main")
    assert sandbox("scan").returncode == 0
    g(repo, "merge", "-q", "--ff-only", "feat/a")
    g(repo, "branch", "-q", "-d", "feat/a")
    r = sandbox("scan")
    assert r.returncode == 0, r.stderr
    by_sha = {c["sha"]: c for c in json.loads((sandbox.dir / "commits.json").read_text(encoding="utf-8"))["commits"]}
    assert by_sha[a1]["branch"] == "feat/a"
    assert by_sha[g(repo, "rev-parse", "HEAD~1")]["branch"] is None   # "base", made on main


def test_default_branch_detection(tmp_path):
    assert scan.default_branch(str(new_repo(tmp_path / "m"))) == "main"
    assert scan.default_branch(str(new_repo(tmp_path / "ms", "master"))) == "master"
    d = new_repo(tmp_path / "d", "develop")
    g(d, "update-ref", "refs/remotes/origin/develop", "HEAD")
    g(d, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    assert scan.default_branch(str(d)) == "develop"
    assert scan.default_branch(str(new_repo(tmp_path / "x", "trunk"))) is None


def test_scan_runs_one_reflog_read_per_branch(tmp_path, monkeypatch):
    repo = new_repo(tmp_path / "app")
    for b in ("feat/one", "feat/two"):
        g(repo, "checkout", "-q", "-b", b, "main")
        for i in range(3):
            commit(repo, "%s %d" % (b, i))
    calls = []
    real = scan.git
    monkeypatch.setattr(scan, "git", lambda r, *a: (calls.append(a), real(r, *a))[1])
    scan.made_on(str(repo), "main")
    assert sum(1 for a in calls if "reflog" in a) == 2 + 1   # one per branch, plus the HEAD log of the one checkout


def test_head_reflog_remembers_branches_deleted_before_any_scan(tmp_path):
    repo = new_repo(tmp_path / "app")
    g(repo, "checkout", "-q", "-b", "feat/old")
    old = commit(repo, "on a branch that is gone by the first scan")
    g(repo, "checkout", "-q", "main")
    g(repo, "merge", "-q", "--ff-only", "feat/old")
    g(repo, "branch", "-q", "-d", "feat/old")
    direct = commit(repo, "made on main")
    got = scan.made_on(str(repo), "main")
    assert got.get(old) == "feat/old" and direct not in got
