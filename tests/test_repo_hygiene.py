import subprocess

import pytest

from conftest import REPO


@pytest.mark.skipif(subprocess.run(["git", "-C", REPO, "rev-parse"], capture_output=True).returncode != 0, reason="not a git checkout")
@pytest.mark.parametrize("name", ["config.json", "todo.json", "tasks.json", "commits.json", "inks.json"])
def test_migrated_copies_of_personal_data_are_git_ignored(name):
    # `tracker migrate` leaves <name>.migrated-YYYYMMDD next to the code; one `git add -A` must not publish them
    r = subprocess.run(["git", "-C", REPO, "check-ignore", "-q", "%s.migrated-20261023" % name])
    assert r.returncode == 0
