## Work tracker

Keep the user's work tracker in sync with the `tracker` command. Do this on your own, without asking the user.

- **When work starts** (a plan or spec is written, a task list is created, or you begin implementing a request): run `tracker todo` first, and if an open task matches this work, reuse its id. Otherwise run `tracker add "<short imperative title>" --path "<your workspace folder>"` (it prints the new id, e.g. `t-0007`), then `tracker start <id>` once you are actually working on it.
- One task per user-level piece of work (a feature, a fix, an investigation), not per sub-step. Questions, explanations and read-only exploration don't get a task.
- **While working:** `tracker note <id> "<milestone>"` for notable progress (plan approved, tests passing, PR opened).
- **When work is put aside** (the user switches to other work, or it is blocked on someone else): `tracker pause <id> "<reason>"`. Paused tasks still count as open; `tracker start <id>` resumes one.
- **When it ends:** `tracker done <id>` only after the work is verified (tests run, checked working); `tracker drop <id>` if it was abandoned or superseded. Mention the task id in your final summary.
- Don't run `tracker` on its own or `tracker refresh`: they open the user's browser.
