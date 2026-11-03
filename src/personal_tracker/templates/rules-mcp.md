## Work tracker

Keep the user's work tracker in sync with the `tracker` MCP tools. Do this on your own, without asking the user.

- **When work starts** (a plan or spec is written, a task list is created, or you begin implementing a request): call `tracker_todo` first, and if an open task matches this work, reuse its id. Otherwise call `tracker_add` with a short imperative `title` and `path` set to the absolute path of your workspace folder (it returns the new id, e.g. `t-0007`), then `tracker_start` once you are actually working on it.
- One task per user-level piece of work (a feature, a fix, an investigation), not per sub-step. Questions, explanations and read-only exploration don't get a task.
- **While working:** `tracker_note` for notable progress (plan approved, tests passing, PR opened).
- **When work is put aside** (the user switches to other work, or it is blocked on someone else): `tracker_pause` with a `reason`. Paused tasks still count as open; `tracker_start` resumes one.
- **When it ends:** `tracker_done` only after the work is verified (tests run, checked working); `tracker_drop` if it was abandoned or superseded. Mention the task id in your final summary.
