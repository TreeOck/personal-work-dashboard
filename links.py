"""Link current-tasks (todo.json items) to the commits made while they were open."""
from datetime import datetime


def _dt(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))  # py3.9 can't parse "Z"


def window(item, now):
    """(start, end) datetimes the item was being worked on, or None if never started.
    Items from before `started_at` existed fall back to created_at."""
    if item["status"] == "todo":
        return None
    start = _dt(item.get("started_at") or item["created_at"])
    end = _dt(item["closed_at"]) if item.get("closed_at") else now
    return start, end


def link(item, commits, now):
    """Commits in the item's repo (or whole project if no repo) inside its window, minus any pauses."""
    w = window(item, now)
    if w is None or not item.get("project"):
        return []
    start, end = w
    gaps = [(_dt(p["from"]), _dt(p["to"])) for p in item.get("pauses", [])]
    if item.get("paused_at"):
        gaps.append((_dt(item["paused_at"]), end))
    return [c for c in commits
            if c["project"] == item["project"]
            and (not item.get("repo") or c["repo"] == item["repo"])
            and start <= _dt(c["date"]) <= end
            and not any(g0 < _dt(c["date"]) < g1 for g0, g1 in gaps)]
