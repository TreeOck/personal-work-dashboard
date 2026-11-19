"""Workspace folder -> (project, repo), the same way the scanner sees the root.

project = the first folder under the root; repo = the git repo the folder is in, looking at most 3 levels below the
root and stopping at the first one, like scan.find_repos (which doesn't descend into a repo)."""
from pathlib import Path

MAX_DEPTH = 3


def project_repo_for(path, root):
    path, root = Path(path).expanduser().resolve(), Path(root).expanduser().resolve()
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return None, None
    if not parts:
        return None, None
    repo = None
    for depth in range(1, min(len(parts), MAX_DEPTH) + 1):
        if (root.joinpath(*parts[:depth]) / ".git").exists():
            repo = parts[depth - 1]
            break
    return parts[0], repo


def current_branch(path, root):
    """(repo path under the root, branch) checked out in `path`, or None when it is the default branch, detached, not
    a git folder, or not under the root. A worktree reports its own branch and its main repo's path."""
    from . import scan
    path, root = Path(path).expanduser(), Path(root).expanduser().resolve()
    if not path.is_dir():
        return None
    branch = scan.git(str(path), "symbolic-ref", "-q", "--short", "HEAD").strip()
    common = scan.git(str(path), "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if not branch or not common:
        return None
    repo = Path(common).resolve().parent   # <repo>/.git -> <repo>, also for a linked worktree
    try:
        rel = repo.relative_to(root).as_posix()
    except ValueError:
        return None
    if branch == scan.default_branch(str(repo)):
        return None
    return rel, branch


def repo_folder(root, project, repo):
    """The folder of repo `repo` in `project` under the root (at most 3 levels down, like the scanner), or None."""
    from . import scan
    base = Path(root).expanduser() / project
    for found in scan.find_repos(str(base)) if base.is_dir() else []:
        if Path(found).name == repo:
            return Path(found)
    return None
