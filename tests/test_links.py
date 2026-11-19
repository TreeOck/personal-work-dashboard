from datetime import datetime, timedelta, timezone

from personal_tracker.links import link, window

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


# ---- step 3: whole-board linking by branch (links.assign) ----

from personal_tracker.links import assign, branch_info  # noqa: E402


def bc(sha, date, branch=None, repo_path="dms/dms-be"):
    project, repo = repo_path.split("/")[0], repo_path.split("/")[-1]
    return {"sha": sha, "date": date, "project": project, "repo": repo, "repo_path": repo_path, "branch": branch}


def task(tid, start, end, status="done", **kw):
    it = {"id": tid, "status": status, "project": "dms", "repo": "dms-be", "created_at": start,
          "started_at": start if status != "todo" else None, "closed_at": end}
    it.update(kw)
    return it


def ids(result, tid):
    return sorted(c["sha"] for c in result[tid])


# t-0061 (5 days, analysis) overlaps t-0066 (1 day, its own branch) in dms-be
T61 = task("t-0061", "2026-10-29T10:00:00+05:30", "2026-11-03T15:00:00+05:30")
T66 = task("t-0066", "2026-11-01T10:00:00+05:30", "2026-11-01T20:00:00+05:30")
BOARD = [
    bc("y1", "2026-10-30T10:00:00+05:30", "feat/y"), bc("y2", "2026-11-02T10:00:00+05:30", "feat/y"),
    bc("x1", "2026-11-01T11:00:00+05:30", "feat/x"), bc("x2", "2026-11-01T12:00:00+05:30", "feat/x"),
    bc("x3", "2026-11-01T13:00:00+05:30", "feat/x"),
]


def test_long_task_does_not_take_short_branch_tasks_commits():
    r = assign([T61, T66], BOARD, NOW)
    assert ids(r, "t-0061") == ["y1", "y2"] and ids(r, "t-0066") == ["x1", "x2", "x3"]
    info = branch_info([T61, T66], BOARD, NOW)
    assert info["t-0066"] == {"repo": "dms/dms-be", "branch": "feat/x", "source": "inferred"}
    assert info["t-0061"]["branch"] == "feat/y"


def test_unknown_branch_commits_follow_the_window_for_everyone():
    commits = BOARD + [bc("m1", "2026-11-01T14:00:00+05:30", None)]
    r = assign([T61, T66], commits, NOW)
    assert "m1" in ids(r, "t-0061") and "m1" in ids(r, "t-0066")


def test_inferred_conflict_goes_to_larger_share():
    # both want feat/x; for t-0066 it's 3 of 3, for t-0061 3 of 5 -> t-0066 wins, t-0061 falls back to feat/y
    assert branch_info([T61, T66], BOARD, NOW)["t-0061"] == {"repo": "dms/dms-be", "branch": "feat/y", "source": "inferred"}


def test_stored_branch_beats_inferred():
    t61 = dict(T61, branch="feat/x", branch_repo="dms/dms-be", branch_source="auto")
    r = assign([t61, T66], BOARD, NOW)
    assert ids(r, "t-0061") == ["x1", "x2", "x3", "y1", "y2"] and ids(r, "t-0066") == []   # feat/y: claimed by nobody else


def test_stored_auto_branch_without_commits_is_ignored_for_inference():
    t66 = dict(T66, branch="feat/gone", branch_repo="dms/dms-be", branch_source="auto")
    assert branch_info([T61, t66], BOARD, NOW)["t-0066"]["branch"] == "feat/x"


def test_manual_none_means_dates_only():
    t66 = dict(T66, branch=None, branch_source="manual")
    info = branch_info([T61, t66], BOARD, NOW)
    assert info["t-0066"] is None
    r = assign([T61, t66], BOARD, NOW)
    assert ids(r, "t-0066") == []   # its window commits are on feat/x, which t-0061 now infers and claims
    assert ids(r, "t-0061") == ["x1", "x2", "x3", "y1", "y2"]   # feat/x is its branch now; feat/y nobody else claims


def test_branch_reuse_months_later_is_bounded_by_the_window():
    t66 = dict(T66, branch="feat/x", branch_repo="dms/dms-be", branch_source="manual")
    later = bc("x9", "2027-02-01T10:00:00+05:30", "feat/x")
    r = assign([t66], BOARD + [later], datetime(2027, 3, 1, tzinfo=IST))
    assert "x9" not in ids(r, "t-0066")


def test_plan_only_task_stays_empty():
    plan = task("t-0070", "2026-11-01T09:00:00+05:30", "2026-11-01T21:00:00+05:30")   # wrote a plan, no commits of its own
    r = assign([plan, T66], BOARD, NOW)
    assert ids(r, "t-0070") == [] and ids(r, "t-0066") == ["x1", "x2", "x3"]


def test_never_started_task_claims_nothing():
    todo = task("t-0080", "2026-10-01T09:00:00+05:30", None, status="todo", branch="feat/x", branch_repo="dms/dms-be",
                branch_source="auto")
    r = assign([todo, T61], BOARD, NOW)
    assert ids(r, "t-0080") == [] and ids(r, "t-0061") == ["x1", "x2", "x3", "y1", "y2"]


def test_moves_override_everything():
    other = task("t-0090", "2025-01-01T00:00:00+05:30", "2025-01-02T00:00:00+05:30", project="beta", repo="b")
    moves = {"dms/dms-be:x1": ["t-0090"], "dms/dms-be:x2": ["t-0061", "t-0090"], "dms/dms-be:x3": []}
    r = assign([T61, T66, other], BOARD, NOW, moves)
    assert ids(r, "t-0066") == [] and ids(r, "t-0090") == ["x1", "x2"] and ids(r, "t-0061") == ["x2", "y1", "y2"]
