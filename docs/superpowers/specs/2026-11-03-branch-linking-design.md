# Step 3: link commits to tasks by branch — design

Tracker v1.0, step 3 (task t-0056). Status: draft for the owner's approval. Version after this step: 0.10.0; the
v1.0.0 tag follows once it is merged.

## 1. Intent

The owner opens a task on the dashboard to see **how much work went into it**: how many commits and what each one
says. Today a task gets every commit in its repo between `start` and `done` (minus pauses), so when two tasks in the
same repo are open at the same time, the longer one swallows the shorter one's commits and both show them. The owner
wants each commit counted for the task it really belongs to, **automatically**, with a way to correct the tracker by
hand from the dashboard when it gets one wrong.

### Evidence (owner's real data, 2026-11-03: 72 tasks, 571 commits)
- 129 commits are linked to two or more tasks. Worst: t-0061 "Analyse DMS integration into KM Navy" (5 days open in
  `dms-be`) also shows all 21 commits of t-0066 "Figma API gaps", which ran inside that window on its own branch.
  Same pattern: t-0019/t-0046, t-0051/t-0053, t-0037/t-0038/t-0049.
- 566 of 571 commits are on a feature branch (`feat/…`, `feature/…`, `docs/…`); the owner works on branches.
- The scanner's existing `branches` field (branches *containing* a commit, capped at 6) is useless for this: 475
  commits list the same 6 later branches.
- `dms-be` merges fast-forward (linear `main`, no merge commits), so once a branch is merged and deleted, git history
  no longer says which branch a commit was made on.
- Git's per-branch reflog (`.git/logs/refs/heads/<branch>`, on by default) lists exactly the commits made on that
  branch (`commit: <subject>`, `commit (amend): …`), including commits made from other worktrees. It disappears when
  the branch is deleted, and expires after 90 days by default.

## 2. Goals
1. **Automatic, correct-enough linking.** A commit goes to the task whose branch it was made on. "Correct enough": the
   count and the commit descriptions are what the owner reads; an occasional stray commit is acceptable, one task
   absorbing another task's branch is not.
2. **Hands-off.** Nobody types branch names. The branch is recorded by the tracker itself when a task is started, and
   commits' branches are learned by the scanner.
3. **Correct by hand from the details panel** (owner's choice: both):
   - **Task branch:** shows the branch the tracker chose; can be changed to another branch of that repo, or to "none
     (use the dates)". The branch's commits follow.
   - **Per commit "Move to…":** assign a commit to another task, to several tasks, or to no task.
   - Hand corrections always win over the automatic rule, including after later scans and rebuilds.
4. **History relinks too:** finished tasks are relinked by the new rule (t-0061 corrects itself), as far as the
   branch information still exists.
5. Every hand correction has a matching `tracker` command and MCP tool, like the other edits (the page edits through
   the edit server, which runs the CLI).

## 3. Non-goals
- Perfect attribution of old history whose branches were deleted before the scanner recorded them.
- Squash/rebase-merge forensics, GitHub API lookups, or reading PR metadata.
- Changing how the summariser groups commits into daily tasks (`tasks.json`); this is only about to-do ↔ commit links.

## 4. Anti-goals (a failure even if it "works")
- Plan-only or investigation tasks with no git work gaining commits they didn't make.
- A rescan or rebuild undoing a correction the owner made by hand.
- Requiring the owner (or an agent) to name branches for the normal case.
- A details panel that looks bolted on: the new controls must match the existing panel (fonts, colours, light/dark,
  the existing action buttons). The mockup shown in brainstorming was a wireframe, not the look.

## 5. Design (decided)

### 5.1 Learning which branch a commit was made on (scanner)
- Each commit in `commits.json` gains `branch`: the branch it was made on, or `null` when unknown.
- Sources, best first: (1) the branch reflogs of the repo (`commit` / `commit (amend)` / `cherry-pick` entries name
  the branch the commit was made on); (2) failing that, a branch that contains the commit while the default branch
  does not (the commit is unique to that branch right now); (3) otherwise `null`.
- **Remembered:** once a commit has a `branch`, later scans keep it (the scanner today replaces a commit's record on
  every scan; `branch` must be carried over). This is what makes fast-forward merges and deleted branches harmless as
  long as a scan ran while the branch existed; scans run daily and on every `tracker done`.
- The default branch is `main`, else `master`, else whatever `origin/HEAD` points to.

### 5.2 Recording a task's branch (automatic)
- A task gains `branch` (string or null) and `branch_source` (`"auto"` or `"manual"`).
- When a task is started (`tracker start`, the page, or `tracker_start`), if it has a repo and no manual branch, the
  tracker records the branch currently checked out **in that repo's folder**, if it isn't the default branch.
  (Agents work in worktrees: the checked-out branch of the main folder may differ from the agent's. So `tracker_add`
  / `tracker add --path` also record the branch checked out in the given path, which is the agent's actual folder;
  `tracker_start` gains an optional `path` for the same reason.)
- If no branch was recorded at start, the linker infers one: the non-default branch holding most of the task's
  window-commits in its repo, provided no other task has claimed that branch (§5.3).

### 5.3 The linking rule
For each task, in order:
1. **Manual moves** win: a commit moved by hand goes only where the owner put it.
2. **Branch tasks:** a task with a branch gets that branch's commits (by the commits' remembered `branch`) made
   between its start and close, minus pauses (the existing window rule still bounds it, so a branch reused months
   later doesn't pull in old work). Two open tasks on the same branch share its commits.
3. **Window tasks** (no branch, or the commit's branch is unknown): today's rule, **but** commits whose `branch`
   belongs to another task's branch are excluded. That is what stops t-0061 taking t-0066's commits.
4. Plan-only tasks still get nothing if nothing matches; a task without a project still gets nothing.

### 5.4 Hand corrections
- `tracker branch <id> <branch|--none|--auto>`: set the task's branch (manual), use dates only, or go back to
  automatic.
- `tracker move <sha> <id>… | --none | --auto`: put a commit on these tasks, on no task, or back to automatic.
  Stored in todo.json (moves keyed by repo path + full sha) so they survive rescans.
- Edit-server actions and MCP tools mirror them (`tracker_branch`, `tracker_move`).
- Details panel: the branch control lists the repo's branches seen in `commits.json` around the task's dates, with
  commit counts; each commit row gets "Move to…" with a task picker (open tasks and recent closed ones in the same
  project first). Read-only when the page is opened as a plain file, like the other edits.

### 5.5 Backfill
- The first scan after upgrading fills `branch` for every commit it can (reflogs reach back up to 90 days on branches
  that still exist). Tasks get no stored `branch` retroactively; finished tasks are relinked through §5.2's inference
  at build time, so history improves without editing todo.json.

### 5.6 Rules settled after the builder check (Claude's calls; they refine §5.2–5.4)
1. **Unknown-branch commits.** A commit whose `branch` is null (made on the default branch, or never seen on a branch)
   follows the date-window rule for *every* task whose window covers it, branch task or not. Direct-to-default commits
   are rare (5 of 571), and this keeps old history whose branches are gone from vanishing.
2. **What a claim is.** A task claims its branch, stored or inferred, **only inside its own window** (start to
   close, minus pauses). Window tasks lose a commit only if it is on a branch claimed by another task whose window
   covers that commit. A dropped task claims like any other started task; a never-started task claims nothing.
3. **Inference conflicts.** Each task's candidate is the non-default branch with the most commits in its window. If
   several tasks want the same branch for overlapping commits, the branch goes to the task for which those commits
   are the largest **share** of its window commits (t-0066: 21 of 21; t-0061: 21 of many, so t-0066 wins). The loser
   tries its next candidate, else uses the window rule. Stored branches (auto or manual) beat inferred ones.
4. **Recording at start.** Record the checked-out branch only if it isn't the default branch and no other open task
   (in progress or paused) already holds it, which covers "plan written before `git checkout -b`". The first recorded
   auto branch is kept: resuming, reopening or starting again doesn't overwrite it. `add --path` records it too.
   An auto branch with no commits in the task's window by the time it is linked is ignored in favour of inference.
5. **CLI start in a worktree.** `tracker start` gains `--path` (same as `tracker_start`'s `path`); without it the repo's
   main folder is used (the page's buttons do that). `templates/rules-cli.md` and `rules-mcp.md` tell agents to pass
   their workspace folder to start as well; `tracker setup` rewrites the block on the next run.
6. **Tasks without a repo.** A task's branch is stored with its repo: `branch` plus `branch_repo` (repo path under the
   root). For a task with a repo, `branch_repo` is that repo. For a whole-project task, `tracker branch` takes
   `--repo` when the branch name exists in more than one repo of the project, and refuses with the list otherwise.
7. **Hand moves bypass every check:** project, repo, window, status. The "Move to…" picker lists the same project's
   tasks first (open, then recently closed) but can reach any task.

## 6. Constraints
- Standard library only; Python ≥ 3.11; Windows / macOS / Linux (CI). Git calls go through `scan.git` (no console
  window on Windows).
- Data files stay backward compatible: new fields are optional, every reader uses `.get`; no migration step.
- Docs updated in the same commits: `docs/schema/todo-json.md` (task `branch`, `branch_source`, moves; commit `branch`),
  `docs/api/edit-server.md`, `docs/api/mcp.md`, README, CHANGELOG. Version 0.10.0.
- Scan time must stay reasonable on the owner's ~10 repos (today a refresh takes about a minute).

## 7. Edge cases
| Case | Behaviour |
|---|---|
| Commit made directly on the default branch | `branch` null → window rule |
| Same branch name reused later for other work | the task window bounds it (rule 2) |
| Two tasks started on the same branch | they share its commits (count shows on both) |
| Branch renamed | reflog follows the rename; older commits keep the old name; owner can fix by hand |
| Detached HEAD / rebase in progress at start | no branch recorded → inference |
| Amended / rebased commits | new sha; reflog names its branch; the old sha drops out of the log as today |
| Task without repo (whole project) | branch recording skipped; inference may still pick a branch in any repo of the project |
| Repo folder moved or deleted | branch stays as recorded; linking uses commits.json only |
| Manual move to a task that is later dropped | the move stands; the commit shows on the dropped task |
| Sha prefix ambiguous in `tracker move` | error listing the matches |

## 8. Testing
- Unit (pytest, real temporary git repos): reflog attribution incl. amend and a commit made from a second worktree;
  branch remembered after fast-forward merge and branch deletion; default-branch detection; start records the
  checked-out branch (main folder and a worktree path); the t-0061/t-0066 overlap reproduced and fixed; window tasks
  exclude claimed branches; plan-only tasks stay empty; manual branch / moves survive rescan and rebuild; CLI, edit
  server and MCP actions; Windows path separators.
- Real data (before/after on a copy of the owner's data folder): count of commits linked to 2+ tasks (129 today)
  and per-task counts for t-0061, t-0066, t-0019, t-0046; the owner spot-checks a few tasks on the page.
- Page: the new controls checked in the browser in light and dark themes (as with the pause feature).

## 9. Left to the builder
Exact reflog parsing, how inference breaks ties, the task-picker ordering, control wording and styling within the
existing panel, whether `branches` (containing) is kept or dropped from `commits.json`.
