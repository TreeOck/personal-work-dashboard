import json
import ntpath
import os
import posixpath
import subprocess

from personal_tracker import scan


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Me", "-c", "user.email=me@example.com", *args],
                   check=True, capture_output=True, text=True, encoding="utf-8")


def test_scan_real_repo_with_spaces_and_unicode(sandbox):
    root = sandbox.root / "my repos"
    repo = root / "प्रोजेक्ट" / "app"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "commit", "-q", "--allow-empty", "-m", "Fix → ✅")
    cfg = json.loads((sandbox.dir / "config.json").read_text(encoding="utf-8"))
    cfg["root"] = str(root)
    (sandbox.dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = sandbox("scan")
    assert r.returncode == 0, r.stderr
    (c,) = json.loads((sandbox.dir / "commits.json").read_text(encoding="utf-8"))["commits"]
    assert (c["project"], c["repo"], c["repo_path"], c["subject"]) == ("प्रोजेक्ट", "app", "प्रोजेक्ट/app", "Fix → ✅")


def test_repo_paths_are_stored_with_forward_slashes_on_every_os():
    assert scan.rel_posix("C:\\code\\proj\\app", "C:\\code", ntpath) == "proj/app"
    assert scan.rel_posix("/code/proj/app", "/code", posixpath) == "proj/app"


def test_scan_without_git(sandbox, tmp_path):
    empty = tmp_path / "empty-path"
    empty.mkdir()
    sandbox.env["PATH"] = str(empty)
    r = sandbox("scan")
    assert r.returncode == 1 and "git not found" in r.stderr and "Traceback" not in r.stderr
