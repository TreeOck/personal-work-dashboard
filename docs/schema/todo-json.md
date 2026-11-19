# `todo.json`

`{"items": [Item, ...]}`, written only by `todo.py` (under `todo.json.lock`, atomically).

| Field | Type | Notes |
|---|---|---|
| `id` | string | `t-0001`, … never reused |
| `title` | string | non-empty |
| `project`, `repo` | string or null | folder under the root / git repo inside it; null repo = whole project |
| `plan` | string or null | absolute path |
| `status` | `todo` · `in_progress` · `paused` · `done` · `dropped` | |
| `created_at`, `updated_at` | ISO 8601 with offset | |
| `started_at` | ISO or null | first `start` only; resuming or reopening keeps it |
| `closed_at` | ISO or null | set by `done`/`drop`, cleared by `start` |
| `paused_at` | ISO or null | **new** — set while `paused` |
| `pauses` | list of `{"from", "to"}` | **new** — each finished pause, closed by `start`, `done` or `drop` |
| `notes` | list of `{"at", "text"}` | `pause` with a reason adds `"Paused: <reason>"` |
| `branch`, `branch_repo` | string or null | **new (0.10.0)** — the git branch the task is worked on and its repo path under the root |
| `branch_source` | `"auto"` · `"manual"` · absent | `auto`: recorded by `add --path` / `start` (the branch checked out in the given folder, else the repo's folder), only if it isn't the default branch, no other open task holds it, and (when another task is open in the same repo) the branch has no commits of its own yet; never overwritten by later starts. `manual`: set with `tracker branch` (`branch` null = no branch: only commits in its dates that no other task claims) |

Transitions: `pause` only from `in_progress` (pausing a paused task prints "already paused").
**Linking (`links.assign`, run at every build; 0.10.0).** A task's *window* is `started_at`…`closed_at` (or now)
minus `pauses` and anything after `paused_at`, in its project (and repo, if set). Each task has a *branch*: set by
hand (`branch_source: "manual"`), recorded automatically (`"auto"`, used only if it has commits in the window), or
inferred: the branch holding most of its window commits; when several tasks want the same branch for the same
commits it goes to the task for which they are the largest share (tie: the shorter window), and the others try
their next branch. A task gets the commits in its window that are on its branch, of unknown branch, or on a branch no
other task claims at that time. Commits listed in `moves` go only to the tasks listed there. The build writes each
task's `linked` (`"<repo_path>:<sha>"` keys) and `branch_effective` (`{"repo", "branch", "source":
"manual"|"auto"|"inferred"}` or null) into the page data; neither is stored in `todo.json`.

Top-level `"moves"` (optional): `{"<repo_path>:<full sha>": ["t-0001", ...]}`, the owner's hand corrections; an
empty list means "no task".

Migration: none needed. Items written before pausing existed have no `paused_at` / `pauses`; every reader uses `.get`.

## `config.json`

In the data folder (`$TRACKER_HOME`, default `~/.personal-tracker`). Written by `tracker init`; read by every command.

| Field | Type | Notes |
|---|---|---|
| `root` | string | Folder containing your git repos; `~` is expanded when read |
| `author_emails` | list of strings | At least one; every email you commit as |
| `timezone` | IANA name or `null` | Day boundaries (Python) and display (page). `null` = this computer's zone. Invalid names are rejected |
| `summariser` | list of strings or `null` | Command + arguments; prompt on stdin (UTF-8), JSON on stdout (UTF-8). Resolved with `shutil.which`. `null` = no summaries. Runs with its working folder set to the empty `<data folder>/summariser/` |
| `summariser_input` | string, optional | How the prompt reaches the summariser: `"stdin"` (default) or `"agy-stream-json"` (Antigravity's `agy`: one `{"event":"user","message":{"content":…}}` line on stdin; the answer is the last `result` event's `result.response`, which must have `status` `"SUCCESS"`). Anything else is an error |

Migration: `tracker migrate` copies an old checkout's `config.json`, adding `"timezone": "Asia/Kolkata"` and the Claude summariser when the keys are missing (what the old scripts did implicitly).

## `commits.json`

`{"generated_at", "since", "author_pattern", "commits": [Commit, ...]}`, written by `tracker scan` (merged by repo path
and sha, so older history is kept).

| Field | Type | Notes |
|---|---|---|
| `sha`, `author`, `email`, `date`, `subject`, `body` | strings | from `git log`; `date` ISO 8601 with offset |
| `files`, `ins`, `del` | list / ints | changed paths and line counts |
| `project`, `repo`, `repo_path` | strings | first folder under the root / repo folder name / repo path under the root with `/` |
| `branches` | list of strings | up to 6 branches that *contain* the commit (later branches contain older commits too) |
| `branch` | string or null | **new (0.10.0)** — the branch the commit was **made on**: from that branch's reflog (`commit`, `commit (amend)`, `cherry-pick` entries), else each checkout's HEAD reflog read in order (the branch last checked out; this remembers branches deleted since, for git's 90-day reflog window), else a branch that has it while the default branch (`main`, `master`, or `origin/HEAD`'s) doesn't; null for commits made on the default branch or never seen on a branch. Once set it is kept by later scans, so fast-forward merges and deleted branches don't lose it |
