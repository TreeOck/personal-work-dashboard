# Cross-platform package (v1 step 1 of 3)

Status: draft, awaiting approval · Branch: `feat/cross-platform` · Tracker: t-0056

v1.0.0 = this step + step 2 (MCP server + rules snippet for any agent) + step 3 (branch-based commit linking).
Each step has its own spec, branch and merge; the tag comes after step 3.

## 1. Goal

Run the tracker on **macOS and Windows** (Linux works too and is tested in CI, but gets no scheduler)
from an installed package, with data in one per-user folder, without changing what any command
or the dashboard does today.

Out of scope here: MCP and agent rules (step 2), branch linking (step 3), packaging the 3D desk,
a Linux scheduler, PyPI publishing.

## 2. Current state (read from the code, 2026-10-23)

Flat scripts in the repo root, each finding its files via `HERE = dirname(__file__)`:
`todo.py` (CLI + logic, `fcntl` lock, runs `build.py`/`scan.py` as subprocesses), `build.py`
(work at import time, `fcntl` lock), `scan.py`, `summarise.py` (`claude -p --model sonnet`, IST
hard-coded), `links.py`, `inks.py` (palette under `desk/src/data/`), `server.py` (macOS `open`,
`start_new_session`), `config.py` (exits if `config.json` missing), `bin/tracker` (bash),
`refresh.sh` (bash), launchd plist `com.valiance.personal-tracker-refresh` → `refresh.sh`.
`template.html` hard-codes `TZ = "Asia/Kolkata"`.

| # | Breaks off-Mac / in a package | Where |
|---|---|---|
| 1 | `fcntl` (Unix only) | todo.py, build.py |
| 2 | 24 `open()` calls without `encoding=` → cp1252 on Windows; existing data has `→`, Hindi | all |
| 3 | `repo_path` joined with `os.sep` → `dms\dms-be` breaks commit keys | scan.py |
| 4 | `zoneinfo` needs `tzdata` on Windows | summarise.py |
| 5 | IST hard-coded | summarise.py, template.html |
| 6 | bash wrapper, `refresh.sh`, launchd, macOS `open` | bin/, server.py |
| 7 | `start_new_session` (POSIX); console window flash | server.py |
| 8 | data next to code | everywhere |
| 9 | `build.py` runs on import; subprocess calls to sibling scripts | build.py, todo.py |
| 10 | npm CLIs (`claude`, `gemini`, `codex`) are `.cmd` shims on Windows; `subprocess.run(["claude"])` without a shell may not find them | summarise.py |

## 3. Design

### 3.1 Package

```
pyproject.toml                    name "personal-work-dashboard", version "0.8.0" (the only place),
                                  requires-python ">=3.11", deps: tzdata; sys_platform == "win32"
                                  [project.scripts] tracker = "personal_tracker.cli:main"
src/personal_tracker/
  __init__.py   __version__ from importlib.metadata
  __main__.py   python -m personal_tracker  (same as `tracker`)
  cli.py        argparse: add start pause done drop note todo | open refresh build scan summarise
                | init migrate schedule serve | inks | --version
  paths.py      data folder + file names
  config.py     load/validate; friendly error pointing at `tracker init`
  files.py      read_json / write_json_atomic (UTF-8, Windows replace retry) + exclusive lock
  todo.py  links.py  scan.py  summarise.py  build.py  inks.py  server.py  schedule.py
  templates/dashboard.html
  data/inks.json                  palette (moved from desk/src/data; desk imports it from here)
desk/                             unchanged except the palette import path and its build output
tests/  .github/workflows/test.yml  LICENSE (MIT, Copyright (c) 2026 Aditya Nair)  CHANGELOG.md
```
Removed: root `*.py`, `bin/tracker`, `refresh.sh`, `launchd/`. Logic moves as-is; only I/O,
paths, locking and process handling change. `build.py`'s import-time work becomes `build()`;
`todo.py` raises `TrackerError` instead of `sys.exit`, and calls `scan()`/`build()` in-process.
The edit server keeps running each action as a child process (`python -m personal_tracker …`)
so a crash can't take the server down and the CLI path stays identical.

### 3.2 Data folder

`TRACKER_HOME` if set, else `~/.personal-tracker` (Windows: `%USERPROFILE%\.personal-tracker`).
Holds: `config.json todo.json tasks.json commits.json inks.json dashboard.html desk.html
desk-template.html server.json *.log *.lock`. Created on first `init`/`migrate`.

### 3.3 Config

```json
{"root": "~/Valiance", "author_emails": ["…"], "timezone": "Asia/Kolkata",
 "summariser": ["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence"]}
```
- `timezone`: IANA name used for day boundaries (Python) and display (page). Empty/missing = the
  computer's local time (page: browser default; Python: `astimezone()`).
- `summariser`: argv of any command that takes the prompt on stdin and prints JSON. Resolved with
  `shutil.which` (finds `.cmd`/`.exe` on Windows). `null`/missing = no summaries; commits stay
  "unsummarised", nothing fails.
- `tracker init`: asks root, emails, timezone (pre-filled from the OS where it can be detected),
  summariser (pre-filled with the Claude command if `claude` is on PATH). Flags for each so it can
  run non-interactively. Refuses to overwrite an existing config without `--force`.

### 3.4 Cross-platform pieces

- **Lock** (`files.lock(path)`): POSIX `fcntl.flock`; Windows `msvcrt.locking` on byte 0 after
  `seek(0)`, retrying `LK_LOCK` until acquired. Same lock files as today.
- **Atomic write**: write `*.tmp` (UTF-8) → `os.replace`, retried up to 10× / 50 ms on
  `PermissionError` (Windows: file briefly held by a reader or antivirus).
- **All text I/O** UTF-8; git/summariser subprocesses `encoding="utf-8", errors="replace"`.
- **`repo_path`** stored with `/`. On read, existing commits.json already uses `/` (Mac data).
- **Browser**: `webbrowser.open`.
- **Server detach**: POSIX `start_new_session=True`; Windows `pythonw.exe` if present +
  `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`.
- **Server identity**: `/api/ping` returns `{"app","home","version"}`; reuse only when `home`
  matches *and* versions match (an old server after an upgrade is stopped via its pid and replaced).
- **Version** (§7): `GET /api/version` → `{"version","environment":"local","python"}`, no auth,
  no disk access. `tracker --version`; page footer shows it. No git sha/build time: a pip install
  has neither; the version string is the single source of truth.

### 3.5 Scheduling (`tracker schedule on [--at HH:MM] | off | status`)

- macOS: LaunchAgent `com.personal-work-dashboard.refresh` running
  `<python> -m personal_tracker refresh --quiet`, `EnvironmentVariables.PATH` including
  `~/.local/bin:/opt/homebrew/bin:/usr/local/bin` (so `claude` is found), logs in the data folder.
  Stays on launchd: cron can't reach the Keychain where Claude Code keeps its login.
- Windows: `schtasks /Create /SC DAILY /ST HH:MM /TN "PersonalWorkDashboard\Refresh" /F` running
  `pythonw -m personal_tracker refresh --quiet`.
- Linux: prints a crontab line to add by hand.
- `refresh` = scan → summarise (if configured) → build, appending to `refresh.log`; replaces
  `refresh.sh`.

### 3.6 Migration (`tracker migrate [--from DIR]`)

Default `--from` = the repo checkout the package runs from, if it holds `config.json`.
1. Refuse if the data folder already has any of the files below (prints what's there).
2. Copy `config.json todo.json tasks.json commits.json inks.json` (whichever exist).
3. Add `"timezone": "Asia/Kolkata"` and today's Claude `summariser` to the copied config if missing,
   so behaviour is exactly as before.
4. Verify: every copy parses and item counts match the source.
5. Rename each original to `<name>.migrated-YYYYMMDD` so nothing old can keep writing to a live
   copy. Print a summary. Re-running after success refuses at step 1 (idempotent).

### 3.7 Desk (optional, stays in the repo)

`desk/src/data/model.ts` imports the palette from `src/personal_tracker/data/inks.json`;
`vite.config.ts` writes `desk-template.html` into the data folder (`TRACKER_HOME` or default);
`build()` renders `desk.html` when that file exists, as today. `tracker desk` opens it.

## 4. Edge cases

| Case | Behaviour | Test |
|---|---|---|
| No config | Every command except `init`/`migrate`/`--version` says "run `tracker init`", exit 1 | yes |
| Empty / malformed JSON in a data file | Error names the file; nothing written | yes |
| Root missing or has no repos | Scan writes 0 commits, warns | yes (existing) |
| `git` not on PATH | Scan fails with "git not found", exit 1; page still builds from last scan | yes |
| Summariser command missing / non-zero / bad JSON | Same as today: logged, tasks.json untouched | yes |
| Unicode (Hindi, emoji, `→`) in titles, notes, commit subjects, paths | Round-trips byte-exact on all OSes | yes, CI on Windows |
| Paths with spaces / non-ASCII (data folder, root) | Work; argv lists only, never a shell | yes |
| Two `tracker` processes at once | Serialised by the lock; no lost write | yes, CI on Windows |
| `os.replace` hits `PermissionError` | Retried, then a clear error | yes (simulated) |
| Saved server port now used by something else | Ping fails or `home` differs → new server on a free port | yes |
| Old-version server still running after upgrade | Version mismatch → stopped and replaced | yes |
| `server.json` left behind (Windows terminate skips cleanup) | Ignored after a failed ping | yes |
| Timezone invalid | `init`/load rejects with the bad name | yes |
| DST zones (e.g. Europe/London) | Day boundaries follow the zone | yes |
| `migrate` twice / into a non-empty folder | Refuses, changes nothing | yes |
| `migrate` copy fails halfway | Originals untouched (renaming is last); partial copies removed | yes |
| `schedule on` twice | Replaces, never duplicates | yes (command generation) |
| Auth/tenant | N/A: single user, local only; server checks unchanged | existing tests |

## 5. Testing (CLAUDE.md §4)

1. **Unit** (`pytest`): the sandbox fixture sets `TRACKER_HOME` to a temp folder and runs
   `python -m personal_tracker …`. Existing 57 tests are ported; new ones per §4.
   Scheduler tests check the generated plist / `schtasks` argv without installing anything.
2. **CI = the Windows check**: GitHub Actions on `windows-latest`, `macos-latest`,
   `ubuntu-latest` × Python 3.11 and 3.13. Windows counts as verified only when that run passes on
   this branch; I'll paste the actual results. Each push needs approval.
3. **Docker**: N/A (local stdlib tool, no services).
4. **This Mac, after merge**: the cutover below, then `tracker todo --all` equals the pre-cutover
   output, the page opens and an edit works.

## 6. Cutover on this Mac (after merge, once, in order)

1. Record `tracker todo --all` → scratch file.
2. Stop the running edit server (pid in `server.json`).
3. `brew install pipx`; `pipx install --editable ~/Valiance/personal-tracker-dashboard`
   (Homebrew Python 3.12; editable so repo changes apply immediately).
4. Remove the old `~/.local/bin/tracker` symlink (pipx puts its own `tracker` there).
5. `tracker migrate` → data in `~/.personal-tracker`.
6. `launchctl bootout` the old `com.valiance.personal-tracker-refresh`, delete its plist,
   `tracker schedule on --at 17:00`.
7. `tracker todo --all` and diff with step 1 → must be identical. `tracker` opens the page.
8. With your OK: update CLAUDE.md §10 (path to the CLI) and the tracker memory.

Rollback: `pipx uninstall`, rename the `*.migrated-*` files back, re-create the symlink and
re-load the old plist (kept in the scratch folder).

## 7. Docs

README (install per OS, `init`, `schedule`, migrate), `docs/operations/install.md` (cutover +
rollback), `docs/architecture/layout.md` (package + data folder), `docs/schema/todo-json.md`
(unchanged fields; config schema added), `docs/api/edit-server.md` (`/api/version`, ping),
`CHANGELOG.md` (0.8.0), `LICENSE`.
