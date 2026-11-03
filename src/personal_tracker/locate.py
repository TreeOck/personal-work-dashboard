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
