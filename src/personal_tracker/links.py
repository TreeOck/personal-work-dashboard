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


# ---- step 3: whole-board linking by branch --------------------------------------------------------------------------

def _key(c):
    return "%s:%s" % (c["repo_path"], c["sha"])


def _bkey(c):
    return (c["repo_path"], c["branch"]) if c.get("branch") and c.get("repo_path") else None


def _stored(item):
    """(repo_path, branch) the task is set to, "none" for a manual dates-only task, or None."""
    if item.get("branch_source") == "manual":
        return (item.get("branch_repo"), item["branch"]) if item.get("branch") else "none"
    if item.get("branch_source") == "auto" and item.get("branch"):
        return (item.get("branch_repo"), item["branch"])
    return None


def _effective(items, scope, now):
    """task id -> ((repo_path, branch), source) or None. Manual and stored-auto branches are fixed (an auto branch
    with no commits in the task's window is ignored); the rest are inferred: each task wants the branch with the most
    of its window commits, and a branch wanted by several tasks for the same commits goes to the task for which they
    are the largest share; losers try their next branch. Stored branches beat inferred ones."""
    eff, wants = {}, {}
    for it in items:
        tid, s = it["id"], _stored(it)
        on = {}
        for c in scope[tid]:
            if _bkey(c):
                on.setdefault(_bkey(c), set()).add(_key(c))
        if s == "none":
            eff[tid] = None
        elif s and it.get("branch_source") == "manual":
            eff[tid] = (s, "manual")
        elif s and s in on:
            eff[tid] = (s, "auto")
        elif on:
            wants[tid] = sorted(on.items(), key=lambda kv: (-len(kv[1]), kv[0]))   # best candidate first
        else:
            eff[tid] = None
    fixed = {tid: e[0] for tid, e in eff.items() if e}

    def held(tid, b, commits_on_b):   # does a fixed task hold this branch for some of these commits?
        return any(fb == b and commits_on_b & {_key(c) for c in scope[ft]} for ft, fb in fixed.items() if ft != tid)

    span = {}
    for it in items:
        w = window(it, now)
        span[it["id"]] = (w[1] - w[0]).total_seconds() if w else 0
    choice = {tid: 0 for tid in wants}
    for _ in range(len(wants) + 1):
        changed = False
        current = {tid: wants[tid][i] for tid, i in choice.items() if i < len(wants[tid])}
        def rank(t, ks):   # larger share of the task's window commits wins; on a tie the shorter (more focused) window
            return (len(ks) / len(scope[t]), -span[t], t)
        for tid, (b, ks) in current.items():
            rivals = [rank(o, oks) for o, (ob, oks) in current.items() if o != tid and ob == b and oks & ks]
            if held(tid, b, ks) or any(r > rank(tid, ks) for r in rivals):
                choice[tid] += 1
                changed = True
                break
        if not changed:
            break
    for tid, i in choice.items():
        eff[tid] = (wants[tid][i][0], "inferred") if i < len(wants[tid]) else None
    return eff


def branch_info(items, commits, now):
    """task id -> {"repo", "branch", "source": "manual"|"auto"|"inferred"} or None (dates only)."""
    scope = {it["id"]: link(it, commits, now) for it in items}
    return {tid: ({"repo": e[0][0], "branch": e[0][1], "source": e[1]} if e else None)
            for tid, e in _effective(items, scope, now).items()}


def assign(items, commits, now, moves=None):
    """task id -> its commits (date order). A commit moved by hand goes only where the owner put it. Otherwise, inside
    a task's window: commits on its own branch, commits of unknown branch, and commits on branches no other task
    claims at that time. So a commit on another task's branch goes to that task only."""
    moves = moves or {}
    scope = {it["id"]: link(it, commits, now) for it in items}
    eff = _effective(items, scope, now)
    claims = {}   # commit key -> ids of tasks whose branch holds it inside their window
    for tid, e in eff.items():
        for c in scope[tid]:
            if e and _bkey(c) == e[0]:
                claims.setdefault(_key(c), set()).add(tid)
    out = {}
    for it in items:
        tid, e, mine = it["id"], eff[it["id"]], []
        for c in scope[tid]:
            if _key(c) in moves:
                continue
            b = _bkey(c)
            if b is None or (e and b == e[0]) or not (claims.get(_key(c), set()) - {tid}):
                mine.append(c)
        out[tid] = mine
    by_key = {_key(c): c for c in commits}
    for k, targets in moves.items():
        for tid in targets:
            if k in by_key and tid in out and by_key[k] not in out[tid]:
                out[tid].append(by_key[k])
    return {tid: sorted(cs, key=lambda c: _dt(c["date"])) for tid, cs in out.items()}
