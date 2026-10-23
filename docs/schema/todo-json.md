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

Transitions: `pause` only from `in_progress` (pausing a paused task prints "already paused").
`links.py` links commits made between `started_at` and `closed_at` (or now), **except** those inside
`pauses` or after `paused_at`.

Migration: none needed. Items written before pausing existed have no `paused_at` / `pauses`; every reader uses `.get`.

## `config.json`

In the data folder (`$TRACKER_HOME`, default `~/.personal-tracker`). Written by `tracker init`; read by every command.

| Field | Type | Notes |
|---|---|---|
| `root` | string | Folder containing your git repos; `~` is expanded when read |
| `author_emails` | list of strings | At least one; every email you commit as |
| `timezone` | IANA name or `null` | Day boundaries (Python) and display (page). `null` = this computer's zone. Invalid names are rejected |
| `summariser` | list of strings or `null` | Command + arguments; prompt on stdin, JSON on stdout. Resolved with `shutil.which`. `null` = no summaries |

Migration: `tracker migrate` copies an old checkout's `config.json`, adding `"timezone": "Asia/Kolkata"` and the Claude summariser when the keys are missing (what the old scripts did implicitly).
