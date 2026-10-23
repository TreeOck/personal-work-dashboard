from datetime import datetime, timedelta, timezone

from links import link, window

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=IST)


def commit(sha, date, project="alpha", repo="alpha-be"):
    return {"sha": sha, "date": date, "project": project, "repo": repo}


COMMITS = [
    commit("a1", "2026-10-05T09:00:00+05:30"),                   # before start
    commit("a2", "2026-10-06T10:00:00+05:30"),                   # inside
    commit("a3", "2026-10-06T05:00:00Z"),                        # inside, recorded in UTC (10:30 IST)
    commit("a4", "2026-10-06T11:00:00+05:30", repo="alpha-fe"),    # inside, other repo
    commit("a5", "2026-10-06T11:00:00+05:30", project="beta", repo="alpha-be"),  # other project, same repo name
    commit("a6", "2026-10-08T09:00:00+05:30"),                   # after close
]


def item(**kw):
    base = {"status": "done", "project": "alpha", "repo": "alpha-be", "created_at": "2026-10-01T09:00:00+05:30",
            "started_at": "2026-10-06T09:00:00+05:30", "closed_at": "2026-10-07T18:00:00+05:30"}
    base.update(kw)
    return base


def shas(it):
    return sorted(c["sha"] for c in link(it, COMMITS, NOW))


def test_links_commits_inside_window_in_same_repo():
    assert shas(item()) == ["a2", "a3"]


def test_no_repo_means_whole_project():
    assert shas(item(repo=None)) == ["a2", "a3", "a4"]


def test_no_project_links_nothing():
    assert shas(item(project=None)) == []


def test_never_started_links_nothing():
    assert window(item(status="todo"), NOW) is None
    assert shas(item(status="todo")) == []


def test_in_progress_runs_until_now():
    assert shas(item(status="in_progress", closed_at=None)) == ["a2", "a3", "a6"]


def test_missing_started_at_falls_back_to_created_at():
    assert shas(item(started_at=None)) == ["a1", "a2", "a3"]


def test_window_edges_are_inclusive():
    it = item(started_at="2026-10-06T10:00:00+05:30", closed_at="2026-10-06T10:30:00+05:30")
    assert shas(it) == ["a2", "a3"]


def test_dropped_tasks_still_show_their_commits():
    assert shas(item(status="dropped")) == ["a2", "a3"]


def test_commits_during_a_finished_pause_are_not_linked():
    # paused 09:30-10:15 on the 6th: a2 (10:00) falls inside the pause, a3 (10:30) after it
    it = item(pauses=[{"from": "2026-10-06T09:30:00+05:30", "to": "2026-10-06T10:15:00+05:30"}])
    assert shas(it) == ["a3"]


def test_commits_after_an_open_pause_are_not_linked():
    it = item(status="paused", closed_at=None, paused_at="2026-10-06T10:15:00+05:30")
    assert shas(it) == ["a2"]
