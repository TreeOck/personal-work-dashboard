# Branch Linking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Link each commit to the to-do task whose branch it was made on (automatically, with hand corrections from the dashboard), so overlapping tasks in one repo stop sharing each other's commits.

**Architecture:** The scanner learns and remembers each commit's `branch` (reflog first). Tasks record their branch at add/start. `links.py` changes from per-task `link()` to a whole-board `assign()` that applies manual moves, branch claims, inference and the window rule. Hand corrections are new `todo` functions exposed through the CLI, the edit server, MCP and the details panel.

**Tech Stack:** Python ≥3.11 standard library; git CLI; pytest; vanilla JS in `templates/dashboard.html`.

**Spec:** `docs/superpowers/specs/2026-11-03-branch-linking-design.md` (§5.6 settles the rules; it wins over §5.2–5.4 wording)

## Global Constraints

- No new dependencies. Version `0.10.0` (only in `pyproject.toml`; tests that pin the version move with it).
- New data fields are optional; every reader uses `.get`; no migration step. Docs in the same commit as their code.
- Git calls only through `scan.git(repo, *args)`. Commit keys are `"<repo_path>:<full sha>"` (the format `build.py` already uses for `linked`).
- Default branch: `main`, else `master`, else the branch `origin/HEAD` points to; branch names compared without `origin/`.
- Hand corrections always win over the automatic rule, across scans and builds.
- All commits: show message (pre-approval for this plan may be given by the owner); no attribution lines. Test command `.venv/bin/python -m pytest tests -q` (create `.venv` with Homebrew python3.12, `pip install -e '.[test]'`). Never run `tracker`/`tracker refresh` against the owner's data folder.

## Review Focus

1. **The owner's headline case** (a long window task overlapping a short branch task in the same repo) must split correctly → Task 2 `test_long_task_does_not_take_short_branch_tasks_commits` (t-0061/t-0066 shape).
2. **Starting a task before `git checkout -b`** (previous task's branch still checked out) must not make both tasks share that branch → Task 3 `test_start_skips_a_branch_another_open_task_holds`.
3. **A rescan after the branch was merged fast-forward and deleted** must keep the commits' branch → Task 1 `test_branch_remembered_after_ff_merge_and_delete`.
4. **Manual corrections vs a later scan/build** must survive → Task 4 `test_manual_branch_and_moves_survive_rescan_and_rebuild`.
5. **Huge repos / many branches** must not make a refresh crawl → Task 1 `test_scan_runs_one_reflog_read_per_branch` (no per-commit git call added).

---

### Task 1: Scanner learns and remembers each commit's branch

**Files:** Modify `src/personal_tracker/scan.py`; test `tests/test_branches.py`; schema doc (commit `branch`).

**Interfaces:** Produces `scan.default_branch(repo) -> str | None`; `scan.made_on(repo, default) -> dict[str, str]` (full sha → branch, from `git reflog show --format=%H%x1f%gs refs/heads/<b>` for every local branch except the default, keeping entries whose subject starts with `commit`, `commit (amend)`, `cherry-pick`; plus, for shas not found there, local branches where the commit is in `git rev-list <default>..<b>`); each scanned commit gets `"branch": str | None`; `run()` carries an existing non-null `branch` over when it re-records a commit.

- [ ] **Step 1: Failing tests** (helper makes real repos in tmp with `git init -b main`, configured user):
  - `test_reflog_names_the_branch_incl_amend_and_second_worktree`: commits on `feat/a` (one amended), one on `feat/b` made from `git worktree add` → `made_on` maps each to its branch; a commit on `main` is absent.
  - `test_unique_to_branch_fallback`: branch created by `git branch feat/c <sha>` + commits via `git update-ref` (no reflog entries) → branch from `main..feat/c`.
  - `test_branch_remembered_after_ff_merge_and_delete`: scan, `git merge --ff-only feat/a`, `git branch -d feat/a`, scan again → commits keep `branch == "feat/a"`.
  - `test_default_branch_detection`: `main`; a repo with only `master`; a repo with `origin/HEAD → develop`.
  - `test_scan_runs_one_reflog_read_per_branch`: monkeypatch `scan.git` to count calls with `"reflog"` → equals the number of non-default branches, independent of commit count.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** "Remember which branch each commit was made on".

### Task 2: Whole-board linking by branch

**Files:** Modify `src/personal_tracker/links.py`, `build.py`; test `tests/test_links.py` (existing tests keep passing or are updated where the spec changes behaviour, each such change named in the commit).

**Interfaces:** Produces `links.assign(items: list[dict], commits: list[dict], now: datetime, moves: dict[str, list[str]] | None = None) -> dict[str, list[dict]]` (task id → its commits, date order) and `links.effective_branch(item, commits, now, claimed) -> tuple[str, str] | None` ((repo_path, branch)). `build.py` sets `it["linked"]` from `assign(...)` and `it["branch_effective"] = {"repo": …, "branch": …, "source": "manual"|"auto"|"inferred"} | None`. Item fields read: `branch`, `branch_repo`, `branch_source`. `moves` = todo.json top-level `"moves"`: key `"<repo_path>:<sha>"` → list of task ids (empty list = no task).
  Algorithm (spec §5.3 + §5.6):
  1. In-scope commits per task = same project, same repo if the task has one, inside window minus pauses (existing `window()` and gaps).
  2. Branch per task: manual (`branch_source == "manual"`, branch null = dates only) → stored auto if it has ≥1 in-scope commit → inferred: candidates = non-default `(repo_path, branch)` of in-scope commits by count; contested candidates (another task wants the same branch for overlapping commits) go to the task where they are the larger share of its in-scope commits; the loser tries its next candidate; stored beats inferred. Iterate to a fixed point (bounded by task count).
  3. Commit `c` goes to task T if `key(c)` is in `moves` → only the listed tasks; else if in T's scope and (T has branch b: `c.branch == b` on T's branch repo, or `c.branch` is null) or (T has none: `c.branch` is null, or no *other* task claims `c.branch` with a window covering `c`).

- [ ] **Step 1: Failing tests:** `test_long_task_does_not_take_short_branch_tasks_commits` (T61 5-day window, T66 1-day inside it; T66's 3 commits on `feat/x`, T61's 2 on `feat/y` → T61 gets 2, T66 gets 3); `test_unknown_branch_commits_follow_the_window_for_everyone`; `test_inferred_conflict_goes_to_larger_share`; `test_stored_branch_beats_inferred`; `test_branch_reuse_months_later_is_bounded_by_the_window`; `test_plan_only_task_stays_empty`; `test_never_started_task_claims_nothing`; `test_moves_override_everything` (to another project's task, to two tasks, to none); `test_build_writes_linked_and_branch_effective`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** "Link commits to tasks by the branch they were made on" (schema doc: `branch_effective`, linking rule).

### Task 3: Record the task's branch at add and start

**Files:** Modify `locate.py`, `todo.py`, `cli.py`, `mcp_server.py`, `templates/rules-cli.md`, `rules-mcp.md`; tests `tests/test_locate.py`, `tests/test_todo.py`, `tests/test_mcp_server.py`.

**Interfaces:** Consumes `scan.default_branch`. Produces `locate.current_branch(path) -> tuple[str, str] | None` ((repo_path relative to root, branch) of the repo containing `path`; None when detached, default branch, or not under root); `todo.add(title, project=None, repo=None, plan=None, path=None)`; `todo.set_status(tid, action, path=None)`. Recording rule (§5.6.4): only if the item has no `branch_source`, the branch isn't held (stored `branch`) by another `in_progress`/`paused` item, then `branch`, `branch_repo`, `branch_source = "auto"`; never overwritten by later starts. Without `path`, `start` uses `<root>/<repo path>` of the item. CLI: `add --path` passes path; `start --path DIR`. MCP: `tracker_start` gains optional `path`; `tracker_add` passes its `path`. Rules: both wordings tell the agent to pass its workspace folder when starting.

- [ ] **Step 1: Failing tests:** `test_current_branch_main_folder_and_worktree` (worktree path → its own branch; default → None; detached → None); `test_start_records_branch_once`; `test_start_skips_a_branch_another_open_task_holds`; `test_add_with_path_records_branch`; `test_cli_start_path_and_mcp_start_path`; `test_rules_tell_agents_to_pass_the_folder_on_start`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** "Record a task's branch when it is added or started" (docs: schema `branch`, `branch_repo`, `branch_source`; mcp.md; agent rules).

### Task 4: Hand corrections (CLI, edit server, MCP)

**Files:** Modify `todo.py`, `cli.py`, `server.py`, `mcp_server.py`; tests `tests/test_corrections.py`; docs `docs/api/edit-server.md`, `docs/api/mcp.md`, schema.

**Interfaces:** Produces `todo.set_branch(tid, branch: str | None | "auto", repo: str | None = None) -> dict` (manual; `None` = dates only; `"auto"` clears `branch_source`/`branch`/`branch_repo`); for a task without a repo, `repo` is required when the name exists in more than one repo of the project in commits.json, else `TrackerError` listing them; `todo.move(sha_or_prefix, target: list[str] | None | "auto") -> str` (resolves the prefix against commits.json, ambiguous → `TrackerError` listing matches, unknown task ids → error; stores `moves[key]`; `"auto"` deletes the key; returns the key). CLI: `tracker branch ID (BRANCH [--repo R] | --none | --auto)`, `tracker move SHA (ID... | --none | --auto)`. Edit server actions `branch` (`id`, `branch` | `none` | `auto`, optional `repo`) and `move` (`sha`, `ids` list | `none` | `auto`) with the same validation style as today (branch names: `^[\w./-]+$`, sha `^[0-9a-f]{4,40}$`). MCP tools `tracker_branch`, `tracker_move` with descriptions saying they are corrections, rarely needed.

- [ ] **Step 1: Failing tests:** `test_set_branch_manual_none_auto`; `test_branch_for_no_repo_task_needs_repo_when_ambiguous`; `test_move_prefix_resolution_and_errors`; `test_manual_branch_and_moves_survive_rescan_and_rebuild`; `test_server_branch_and_move_actions_validated`; `test_mcp_branch_and_move_tools`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** "Let the owner correct a task's branch and commits".

### Task 5: Details panel controls

**Files:** Modify `templates/dashboard.html`, `build.py` (embed per-repo branch list: `DATA.branches = {repo_path: [{branch, first, last, count}]}` from commits.json); test `tests/test_build.py`.

**Interfaces:** Consumes `branch_effective`, `linked`, edit-server `branch`/`move`. In the details panel (editable mode only): a branch control next to the task's meta (current branch + source label; choices: branches of the task's repo whose commits overlap the task's dates ±7 days with counts, "None (use the dates)", "Automatic"); each commit row gets "Move to…" opening a task picker (same project first: open, then closed in the last 30 days; then a search box over all tasks; "No task", "Automatic"). Styling reuses existing `.btn`, `.acts`, panel tokens; works in light and dark.

- [ ] **Step 1: Failing test:** `test_build_embeds_branch_list_per_repo`. **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Suite PASS.
- [ ] **Step 5: Browser check** (Playwright, scratch data folder with the Task 2 fixture shape, served by `tracker serve` under `TRACKER_HOME`): change a branch and move a commit in light and dark; screenshots read; console has no errors.
- [ ] **Step 6: Commit** "Add branch and move controls to the details panel".

### Task 6: Real data, docs, version, PR

- [ ] Copy `~/.personal-tracker` to a scratch folder (read-only use of the original); run scan + build there with the new code; report before/after: commits linked to 2+ tasks (129 before), linked counts for t-0061, t-0066, t-0019, t-0046, t-0051, t-0053; show the owner.
- [ ] Bump `0.10.0`; CHANGELOG; README (linking explained, the two corrections); layout doc. Suite PASS. **Commit**, **push** (approval), PR (approval). After merge: `git pull` + `pipx install --force --editable …` (version bump), check `/api/version`.
