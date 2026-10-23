import pytest

from personal_tracker.summarise import dedupe_ids, unique_id, validate_backfill, validate_new_tasks

ORPHANS = [
    {"sha": "aaaaaaa111", "date": "2026-10-06T10:00:00+05:30", "project": "alpha"},
    {"sha": "bbbbbbb222", "date": "2026-10-05T20:00:00Z", "project": "alpha"},  # 01:30 IST on 6 Oct
]


def task(**kw):
    t = {"date": "2026-10-06", "project": "alpha", "kind": "feature", "thread": "Versioning", "title": "T",
         "summary": "S", "details": [], "commits": ["aaaaaaa", "bbbbbbb"]}
    t.update(kw)
    return t


def test_valid_output_passes_and_utc_commit_lands_on_ist_day():
    validate_new_tasks([task()], ORPHANS, {})


@pytest.mark.parametrize("bad, msg", [
    (dict(kind="chore"), "bad kind"),
    (dict(title=""), "missing title"),
    (dict(thread="  "), "missing thread"),
    (dict(commits=[]), "bad details/commits"),
    (dict(commits=["aaaaaaa"]), "coverage mismatch"),
    (dict(commits=["aaaaaaa", "bbbbbbb", "aaaaaaa"]), "coverage mismatch"),
    (dict(commits=["aaaaaaa", "zzzzzzz"]), "unknown sha"),
    (dict(date="2026-10-05"), "date mismatch"),
    (dict(project="beta"), "project mismatch"),
])
def test_bad_output_is_rejected(bad, msg):
    with pytest.raises(ValueError, match=msg):
        validate_new_tasks([task(**bad)], ORPHANS, {})


def test_thread_cannot_cross_projects():
    with pytest.raises(ValueError, match="two projects"):
        validate_new_tasks([task()], ORPHANS, {"Versioning": "beta"})


def test_existing_thread_in_same_project_is_reused():
    validate_new_tasks([task()], ORPHANS, {"Versioning": "alpha"})


TASKS = [{"id": "x1", "project": "alpha"}, {"id": "x2", "project": "beta"}, {"id": "x3", "project": "alpha", "thread": "Old"}]


def test_backfill_must_cover_exactly_the_tasks_without_thread():
    validate_backfill({"x1": "A", "x2": "B"}, TASKS, {"Old": "alpha"})
    with pytest.raises(ValueError, match="ids mismatch"):
        validate_backfill({"x1": "A"}, TASKS, {"Old": "alpha"})
    with pytest.raises(ValueError, match="ids mismatch"):
        validate_backfill({"x1": "A", "x2": "B", "x3": "C"}, TASKS, {"Old": "alpha"})


def test_backfill_rejects_empty_and_cross_project_threads():
    with pytest.raises(ValueError, match="empty thread"):
        validate_backfill({"x1": "", "x2": "B"}, TASKS, {})
    with pytest.raises(ValueError, match="two projects"):
        validate_backfill({"x1": "Same", "x2": "Same"}, TASKS, {})
    with pytest.raises(ValueError, match="two projects"):
        validate_backfill({"x1": "A", "x2": "Old"}, TASKS, {"Old": "alpha"})


def test_unique_id_skips_taken():
    taken = {"auto-d-p-1", "auto-d-p-2"}
    assert unique_id("auto-d-p", taken) == "auto-d-p-3"
    assert "auto-d-p-3" in taken


def test_dedupe_ids_renames_only_later_duplicates():
    doc = {"tasks": [{"id": "auto-d-p-1"}, {"id": "auto-d-p-1"}, {"id": "auto-d-p-2"}]}
    assert dedupe_ids(doc) == 1
    ids = [t["id"] for t in doc["tasks"]]
    assert ids[0] == "auto-d-p-1" and len(set(ids)) == 3
