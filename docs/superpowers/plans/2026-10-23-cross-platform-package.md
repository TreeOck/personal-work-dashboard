# Cross-platform Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the flat-script tracker into an installable `personal_tracker` package that runs on macOS and Windows, with data in a per-user folder, without changing any command's or the dashboard's behaviour.

**Architecture:** Move the root scripts into `src/personal_tracker/` with logic unchanged; isolate everything OS-specific in `files.py` (lock, atomic UTF-8 JSON), `paths.py` (data folder), `server.py` (detach, browser) and `schedule.py` (launchd / schtasks). One `tracker` entry point (`cli.py`) replaces `bin/tracker`, `todo.py`'s argparse and `refresh.sh`.

**Tech Stack:** Python ≥3.11 stdlib only (+ `tzdata` on Windows), setuptools via `pyproject.toml`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-23-cross-platform-package-design.md`

## Global Constraints

- `requires-python = ">=3.11"`; dependencies: only `tzdata; sys_platform == "win32"`.
- Version `0.8.0`, declared **only** in `pyproject.toml`; read via `importlib.metadata.version("personal-work-dashboard")`.
- Data folder: `TRACKER_HOME` env var, else `Path.home() / ".personal-tracker"`.
- Every text file open: `encoding="utf-8"`. Every subprocess with text: `encoding="utf-8", errors="replace"`. Never `shell=True`.
- Stored `repo_path` always uses `/`.
- Existing command names, flags, output formats (`fmt()` lines, printed ids) and `todo.json` fields stay exactly as today.
- Edit-server security checks (Host, Origin, token, body limit, `--` before user text) stay exactly as today.
- Commits: per CLAUDE.md §6 — show the message, get explicit approval, body lists tests run; docs in the same commit as their code; no attribution lines. Commit as `82602425+TreeOck@users.noreply.github.com` (repo config already set).
- Work only in `/Users/adin/Valiance/personal-tracker-dashboard/.worktrees/cross-platform`. Never touch the live checkout until Task 9.
- Test command: `.venv/bin/python -m pytest tests -q` (venv is Homebrew Python 3.12; Task 1 adds `pip install -e .`).

## Review Focus

1. **Non-ASCII data on Windows** (Hindi, emoji, `→` in titles/notes/commit subjects) must round-trip byte-exact — Task 1 `test_unicode_round_trip`, run by CI on Windows (Task 8).
2. **Repo root with spaces and non-ASCII** (`my repos/प्रोजेक्ट`) must scan, and `repo_path` must use `/` — Task 3 `test_scan_real_repo_with_spaces_and_unicode`.
3. **Two `tracker` processes writing at once** must not lose a write on any OS — Task 1 `test_concurrent_adds_lose_nothing` (2 processes × 15 adds → 30 unique ids).
4. **Upgrading while an old-version server runs** must replace it, not silently reuse it — Task 4 `test_version_mismatch_replaces_server`.
5. **Summariser installed as a Windows `.cmd` shim** must be found — Task 3 `test_summariser_resolved_via_which` (fake command on PATH: `.cmd` on Windows, executable script elsewhere).

---

### Task 1: Package skeleton, data folder, cross-platform file I/O

**Files:**
- Create: `pyproject.toml`, `src/personal_tracker/__init__.py`, `src/personal_tracker/__main__.py`, `src/personal_tracker/errors.py`, `src/personal_tracker/paths.py`, `src/personal_tracker/files.py`
- Test: `tests/test_files.py`, `tests/test_paths.py`

**Interfaces:**
- Produces:
  - `personal_tracker.__version__: str`
  - `errors.TrackerError(Exception)` — message shown to the user by `cli.main`, exit 1; `errors.DataError(TrackerError)`
  - `paths.home() -> Path` (env `TRACKER_HOME` else `~/.personal-tracker`; does not create it); `paths.file(name: str) -> Path` = `home() / name`
  - `files.read_json(path: Path, default=None)` — `default` if missing; on bad JSON raises `DataError(f"{path}: {reason}")`
  - `files.write_json(path: Path, obj, indent=1)` — UTF-8, `ensure_ascii=False`, tmp + `os.replace` retried 10× / 0.05 s on `PermissionError`, then re-raised
  - `files.lock(path: Path)` — context manager; exclusive; POSIX `fcntl.flock`, Windows `msvcrt.locking(fd, LK_LOCK, 1)` at offset 0 in a retry loop on `OSError`
  - `files.write_text(path: Path, text: str)` — same atomic replace, UTF-8

- [ ] **Step 1: Write `pyproject.toml`** — setuptools, `src` layout, name `personal-work-dashboard`, version `0.8.0`, `requires-python >=3.11`, deps per Global Constraints, `[project.scripts] tracker = "personal_tracker.cli:main"`, `[project.optional-dependencies] test = ["pytest"]`, package data `templates/*.html`, `data/*.json`. Run `.venv/bin/pip install -e '.[test]'` → succeeds.
- [ ] **Step 2: Write failing tests** in `tests/test_paths.py` and `tests/test_files.py`:
  - `test_home_uses_env(monkeypatch, tmp_path)`: `TRACKER_HOME=tmp_path/"a b"` → `paths.home() == tmp_path/"a b"`; unset → `Path.home()/".personal-tracker"`.
  - `test_unicode_round_trip(tmp_path)`: `write_json` then `read_json` of `{"t": "हिंदी दस्तावेज़ → ✅ 🚀"}` equal; raw bytes decode as UTF-8 and contain `हिंदी` (not `\u` escapes).
  - `test_read_json_missing_and_bad(tmp_path)`: missing → default; file `"{"` → `DataError` whose message contains the path.
  - `test_write_json_retries_permission_error(monkeypatch, tmp_path)`: patch `os.replace` to raise `PermissionError` twice then delegate → file written; always raising → `PermissionError` raised and the original file unchanged.
  - `test_concurrent_adds_lose_nothing(tmp_path)`: helper script run as 2 subprocesses, each 15× `with lock(L): d=read_json(F,{"n":[]}); d["n"].append(x); write_json(F,d)` → final list length 30, all unique.
- [ ] **Step 3: Run** `.venv/bin/python -m pytest tests/test_files.py tests/test_paths.py -q` → FAIL (import errors).
- [ ] **Step 4: Implement** `errors.py`, `paths.py`, `files.py`, `__init__.py` (`__version__` via `importlib.metadata`), `__main__.py` (calls `cli.main()`; `cli` arrives in Task 2 — until then `__main__` may import lazily).
- [ ] **Step 5: Run** same command → PASS. Full suite still 57 passed (old flat scripts untouched so far).
- [ ] **Step 6: Commit** (approval): "Add package skeleton and cross-platform file helpers".

### Task 2: Move modules into the package; one `tracker` CLI

**Files:**
- Move (`git mv`): `todo.py links.py scan.py summarise.py build.py inks.py server.py config.py` → `src/personal_tracker/`; `template.html` → `src/personal_tracker/templates/dashboard.html`
- Create: `src/personal_tracker/cli.py`
- Delete: `bin/tracker`, `refresh.sh` (behaviour moves to `cli.py`; launchd/ removed in Task 6)
- Modify: `tests/conftest.py`, every existing test's imports
- Test: existing suite + `tests/test_cli.py`

**Interfaces:**
- Consumes: `paths.file`, `files.read_json/write_json/write_text/lock` (Task 1)
- Produces:
  - `config.load() -> Config` dataclass `(root: Path, author_emails: list[str], timezone: str | None, summariser: list[str] | None)`; missing file → `TrackerError("no config at <path> -- run: tracker init")`; invalid timezone → `TrackerError("unknown timezone: <name>")`
  - `todo.add(title, project=None, repo=None, plan=None) -> dict`, `todo.set_status(tid, action: Literal["start","done","drop"]) -> dict`, `todo.pause(tid, reason="") -> dict`, `todo.note(tid, text) -> dict`, `todo.list_items(all_=False) -> list[dict]`, `todo.fmt(item) -> str` (unchanged format)
  - `scan.run(days=14, since=None) -> int` (commit count), `summarise.run(backfill_threads=False) -> None`, `build.build() -> list[Path]`
  - `cli.main(argv=None) -> int`; subcommands `add start pause done drop note todo open refresh build scan summarise inks serve desk` + `--version` (later tasks add `init migrate schedule`); `refresh [--quiet]` = scan → summarise → build, appending to `paths.file("refresh.log")`; `open`/no subcommand = `server.open_dashboard()`
- [ ] **Step 1: Rewrite `tests/conftest.py`**: `sandbox` sets `TRACKER_HOME=tmp_path/"home"`, writes `config.json` (root = `tmp_path/"repos"`, `author_emails`, `"timezone": "Asia/Kolkata"`, no summariser), `commits.json`, `tasks.json`; `run(*args)` = `subprocess.run([sys.executable, "-m", "personal_tracker", *args], env=…, capture_output=True, text=True, encoding="utf-8")`; `run.dir` = home folder; `run.items()` reads `home/todo.json`. Port test imports (`from personal_tracker.links import link` etc.). Run suite → FAIL (modules not moved).
- [ ] **Step 2: Add `tests/test_cli.py`**: `test_version` (`--version` stdout == `"tracker 0.8.0"`), `test_no_config_says_run_init` (empty home → exit 1, stderr contains `tracker init`), `test_add_hindi_title` (`add "हिंदी दस्तावेज़ → ✅"` then `todo` stdout contains it).
- [ ] **Step 3: `git mv` the modules and template; implement** `cli.py`, convert `todo.py` main into the functions above, `build.py` import-time code into `build()`, `scan.py`/`summarise.py` mains into `run()`; replace all `HERE` data paths with `paths.file(...)`, template via `importlib.resources.files("personal_tracker") / "templates/dashboard.html"`; replace subprocess calls to sibling scripts with direct calls; `server.py` child command becomes `[sys.executable, "-m", "personal_tracker", *argv]`. Use `files.*` for every JSON read/write and lock.
- [ ] **Step 4: Run** full suite → all ported tests + `test_cli.py` PASS.
- [ ] **Step 5: Commit** (approval): "Move tracker into an installable package with one CLI".

### Task 3: Scan, summarise and page — paths, timezone, summariser

**Files:**
- Modify: `src/personal_tracker/scan.py`, `summarise.py`, `build.py`, `templates/dashboard.html`
- Test: `tests/test_scan.py` (new), `tests/test_summarise.py`, `tests/test_build.py`

**Interfaces:**
- Consumes: `config.load()` (Task 2)
- Produces: `summarise.resolve_command(argv: list[str]) -> list[str] | None` (`shutil.which(argv[0])` → absolute path replacing `argv[0]`, else `None`); build inlines `DATA.timezone` (string or `null`) and `DATA.version`
- [ ] **Step 1: Failing tests:**
  - `test_scan_real_repo_with_spaces_and_unicode(tmp_path)`: `git init` at `root/"my repos"/"प्रोजेक्ट"/"app"` (configure local user.email to the sandbox email), one commit with subject `"Fix → ✅"`; config root = `root/"my repos"`; `scan.run()` → 1 commit with `project == "प्रोजेक्ट"`, `repo_path == "प्रोजेक्ट/app"`, subject `"Fix → ✅"` exactly.
  - `test_scan_without_git(monkeypatch)`: `PATH` empty → `TrackerError("git not found…")`.
  - `test_summariser_resolved_via_which(tmp_path, monkeypatch)`: fake `fakesum` (`.cmd` on Windows, `#!` script elsewhere) on PATH printing `{"tasks": []}`; `resolve_command(["fakesum"])[0]` is its absolute path; `resolve_command(["nope-xyz"]) is None`.
  - `test_no_summariser_configured_is_a_noop(sandbox)`: `summarise` exit 0, tasks.json unchanged, stdout says summaries are off.
  - `test_day_boundary_follows_timezone`: with `timezone="Europe/London"`, a commit at `2026-03-29T00:30:00+00:00` (DST day) is dated `2026-03-29`; with `"Asia/Kolkata"`, a commit at `2026-10-22T20:00:00+00:00` is dated `2026-10-23`.
  - `test_build_inlines_timezone_and_version(sandbox)`: built page contains `"timezone": "Asia/Kolkata"` and `"version": "0.8.0"`.
- [ ] **Step 2: Run** these → FAIL.
- [ ] **Step 3: Implement**: `repo_path = rel.replace(os.sep, "/")`; `git()` checks `shutil.which("git")`; summariser uses `config.summariser` via `resolve_command`, stdin prompt, 900 s timeout, no shell; summarise's `IST` becomes the configured zone (`ZoneInfo(tz)` or local `astimezone()`); page: `const TZ = DATA.timezone || undefined`, drop the literal "IST" suffixes in favour of the zone's short name (`timeZoneName: "short"`), footer shows `v${DATA.version}`.
- [ ] **Step 4: Run** full suite → PASS.
- [ ] **Step 5: Commit** (approval): "Make scanning, summaries and the page OS- and timezone-neutral".

### Task 4: Edit server — data folder, detach, identity, version

**Files:**
- Modify: `src/personal_tracker/server.py`, `docs/api/edit-server.md`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `paths.file`, `__version__`
- Produces: `server.open_dashboard() -> None`, `server.ensure() -> int | None`, `server.serve() -> None`; `GET /api/ping` → `{"app": "tracker", "home": str(paths.home()), "version": __version__}`; `GET /api/version` → `{"version", "environment": "local", "python": platform.python_version()}`
- [ ] **Step 1: Failing tests:** `test_version_endpoint_needs_no_token(live)`; `test_ping_reports_home_and_version(live)`; `test_version_mismatch_replaces_server(sandbox)` — start a fake server on a free port answering ping with `version: "0.0.1"` and the sandbox home, write its `server.json`; `ensure()` (run in a subprocess with the sandbox env) returns a different port and the fake got a stop request or was ignored, with `server.json` now pointing at the new server; `test_stale_server_json_is_ignored(sandbox)` — `server.json` pointing at a closed port → `ensure()` starts a fresh server.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**: state/log/page in `paths.home()`; `running_port()` requires matching `home` **and** `version`; on version mismatch send `SIGTERM` (POSIX) / `taskkill /PID <pid> /F` (Windows) to the pid in `server.json`, then start new; detach per spec §3.4 (Windows: `pythonw.exe` beside `sys.executable` if it exists, `creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW`); open with `webbrowser.open`; read-only fallback opens `paths.file("dashboard.html").as_uri()`. Tests must not rely on `server.json` being deleted on terminate.
- [ ] **Step 4: Run** full suite → PASS. Update `docs/api/edit-server.md` (ping fields, `/api/version`, data-folder paths).
- [ ] **Step 5: Commit** (approval): "Run the edit server from the data folder on any OS".

### Task 5: `tracker init` and `tracker migrate`

**Files:**
- Create: `src/personal_tracker/setup.py` (init + migrate logic)
- Modify: `src/personal_tracker/cli.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Consumes: `paths`, `files`, `config` (Tasks 1–2)
- Produces: `setup.init(root, emails, timezone=None, summariser=None, force=False) -> Path`; `setup.migrate(src: Path, today: date) -> list[str]` (names migrated); CLI `init [--root --email (repeatable) --timezone --summariser "<cmd line>" --no-summariser --force]` (prompts for anything not given when stdin is a TTY), `migrate [--from DIR]`
- [ ] **Step 1: Failing tests:**
  - `test_init_writes_config_and_refuses_overwrite`: non-interactive init → config with given fields; second init → `TrackerError` mentioning `--force`; `--timezone Mars/Base` → `unknown timezone`.
  - `test_migrate_copies_verifies_and_renames(tmp_path)`: old folder with config (no timezone/summariser), todo (3 items, one with Hindi title), tasks, commits, inks → after migrate: new files equal source content, config gained `"timezone": "Asia/Kolkata"` and the Claude summariser argv from the spec, originals renamed `*.migrated-20261023`.
  - `test_migrate_refuses_when_target_has_data`: target already has `todo.json` → `TrackerError`, source files untouched.
  - `test_migrate_partial_failure_leaves_source_intact(monkeypatch)`: make the 3rd copy raise → source files all still present under original names, target holds none of the copied files.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** per spec §3.6 (copy all → verify parse + counts → only then rename; on any error before renaming, delete the copies made). `--from` default: the repo root of the running package (`Path(__file__).parents[2]`) if it contains `config.json`, else error asking for `--from`.
- [ ] **Step 4: Run** full suite → PASS.
- [ ] **Step 5: Commit** (approval): "Add tracker init and tracker migrate".

### Task 6: Daily refresh scheduling

**Files:**
- Create: `src/personal_tracker/schedule.py`
- Modify: `cli.py`; Delete: `launchd/`
- Test: `tests/test_schedule.py`

**Interfaces:**
- Produces: `schedule.launchd_plist(python: str, at: str, home: Path) -> str`; `schedule.schtasks_create_argv(pythonw: str, at: str) -> list[str]`; `schedule.on(at="17:00")`, `schedule.off()`, `schedule.status() -> str`; CLI `schedule on [--at HH:MM] | off | status`
- [ ] **Step 1: Failing tests:** plist contains label `com.personal-work-dashboard.refresh`, `ProgramArguments` = `[python, "-m", "personal_tracker", "refresh", "--quiet"]`, `Hour`/`Minute` from `--at`, `EnvironmentVariables/PATH` starting `~/.local/bin` (expanded) `:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`, log paths in home; schtasks argv == `["schtasks","/Create","/SC","DAILY","/ST","17:00","/TN","PersonalWorkDashboard\\Refresh","/TR", f'"{pythonw}" -m personal_tracker refresh --quiet',"/F"]`; `--at 25:00` / `5pm` → `TrackerError`; on Linux `on` prints a crontab line and changes nothing; `on` twice yields one job (macOS: `bootout` before `bootstrap`, ignoring "not loaded"). OS calls go through one `_run(argv)` helper that tests monkeypatch.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** full suite → PASS.
- [ ] **Step 5: Commit** (approval): "Add tracker schedule for macOS and Windows".

### Task 7: Desk palette into the package

**Files:**
- Move: `desk/src/data/inks.json` → `src/personal_tracker/data/inks.json`
- Modify: `src/personal_tracker/inks.py` (palette via `importlib.resources`, assignments at `paths.file("inks.json")`), `desk/src/data/model.ts` (import path), `desk/vite.config.ts` (write `desk-template.html` to `process.env.TRACKER_HOME ?? ~/.personal-tracker`), `build.py` (desk template from home)
- Test: `tests/test_inks.py`, `cd desk && npx vitest run`
- [ ] **Step 1:** Update `test_inks.py` to the new palette location; run → FAIL. **Step 2:** move + implement. **Step 3:** `pytest` PASS and `cd desk && npx vitest run` PASS (paste counts). **Step 4: Commit** (approval): "Keep the ink palette in the package".

### Task 8: CI, licence, changelog, docs — and the Windows proof

**Files:**
- Create: `.github/workflows/test.yml`, `LICENSE`, `CHANGELOG.md`, `docs/operations/install.md`, `docs/architecture/layout.md`
- Modify: `README.md`, `docs/schema/todo-json.md` (add config schema), `.gitignore`
- [ ] **Step 1:** Workflow: `on: [push, pull_request]`; matrix `os: [ubuntu-latest, macos-latest, windows-latest]` × `python: ["3.11", "3.13"]`, `fail-fast: false`; steps checkout, setup-python, `pip install -e .[test]`, `git config --global user.email/name` (scan tests), `python -m pytest tests -q`.
- [ ] **Step 2:** `LICENSE` = MIT, `Copyright (c) 2026 Aditya Nair`; `CHANGELOG.md` `## 0.8.0 – 2026-10-23` (package, Windows, data folder, init/migrate/schedule, timezone + summariser settings, /api/version); README install for macOS (`brew install pipx && pipx install git+…`) and Windows (python.org 3.11+, `py -m pip install --user pipx`, `pipx install git+…`), then `tracker init`, `tracker schedule on`; operations doc = spec §6 cutover + rollback; architecture doc = package layout + data folder table.
- [ ] **Step 3:** Local suite PASS. **Commit** (approval). **Push** `feat/cross-platform` (approval) and open a PR to `main` (approval). Paste the Actions matrix result per job. Any Windows failure → fix (TDD), commit + push with approval, repeat until all 6 jobs pass.

### Task 9: Merge and cut over this Mac (spec §6)

- [ ] **Step 1:** Merge the PR (approval). In the live checkout, `git pull`.
- [ ] **Step 2:** `tracker todo --all > <scratch>/before.txt`; copy the old plist and symlink target into scratch (rollback).
- [ ] **Step 3:** Stop the old server (pid from live `server.json`); `brew install pipx`; `rm ~/.local/bin/tracker`; `pipx install --editable ~/Valiance/personal-tracker-dashboard` (Python 3.12).
- [ ] **Step 4:** `tracker migrate`; `launchctl bootout gui/$(id -u)/com.valiance.personal-tracker-refresh` + delete its plist; `tracker schedule on --at 17:00`; `tracker schedule status`.
- [ ] **Step 5:** `tracker todo --all > after.txt`; `diff before.txt after.txt` → empty. `tracker` opens the page with "editing"; add a note to t-0056 from the page; `tracker refresh` succeeds (paste `refresh.log` tail).
- [ ] **Step 6:** Ask before updating CLAUDE.md §10 (CLI path) and the tracker memory; `tracker note t-0056` with results.
