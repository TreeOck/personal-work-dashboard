"""Workspace folder -> (project, repo), the same way the scanner sees the root.

project = the first folder under the root; repo = the git repo the folder is in, looking at most 3 levels below the
root and stopping at the first one, like scan.find_repos (which doesn't descend into a repo)."""
from pathlib import Path

MAX_DEPTH = 3


def _roots(roots):
    """A root folder or a list of them -> resolved paths, the most specific (deepest) first."""
    roots = [roots] if isinstance(roots, (str, Path)) else roots
    return sorted({Path(r).expanduser().resolve() for r in roots}, key=lambda r: len(r.parts), reverse=True)


def _under(path, roots):
    """(root, path relative to it) for the most specific root containing `path`, or (None, None)."""
    for root in _roots(roots):
        try:
            return root, path.relative_to(root)
        except ValueError:
            continue
    return None, None


def project_repo_for(path, roots):
    path = Path(path).expanduser().resolve()
    root, rel = _under(path, roots)
    if root is None:
        return None, None
    parts = rel.parts
    if not parts:
        return None, None
    repo = None
    for depth in range(1, min(len(parts), MAX_DEPTH) + 1):
        if (root.joinpath(*parts[:depth]) / ".git").exists():
            repo = parts[depth - 1]
            break
    return parts[0], repo


def current_branch(path, roots):
    """(repo path under the root, branch) checked out in `path`, or None when it is the default branch, detached, not
    a git folder, or not under the root. A worktree reports its own branch and its main repo's path."""
    from . import scan
    path = Path(path).expanduser()
    if not path.is_dir():
        return None
    branch = scan.git(str(path), "symbolic-ref", "-q", "--short", "HEAD").strip()
    common = scan.git(str(path), "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if not branch or not common:
        return None
    repo = Path(common).resolve().parent   # <repo>/.git -> <repo>, also for a linked worktree
    root, rel = _under(repo, roots)
    if root is None:
        return None
    rel = rel.as_posix()
    if branch == scan.default_branch(str(repo)):
        return None
    return rel, branch


def repo_folder(roots, project, repo):
    """The folder of repo `repo` in `project` under a root (at most 3 levels down, like the scanner), or None."""
    from . import scan
    for root in _roots(roots):
        base = root / project
        for found in scan.find_repos(str(base)) if base.is_dir() else []:
            if Path(found).name == repo:
                return Path(found)
    return None


def repo_dir(roots, repo_path):
    """The folder of a repo given its path under a root ("proj/app"), or None."""
    for root in _roots(roots):
        if (root / repo_path).is_dir():
            return root / repo_path
    return None
