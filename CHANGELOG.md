# Changelog

Versions follow `pyproject.toml` (the only place the version is written), with semantic versioning from 1.0.

## 1.1.0 – 2026-11-26

### Added
- Theme menu in the header: **Auto** (follow the OS), **Light**, **Ink**, and six popular editor palettes: **Dracula**, **Nord**, **Catppuccin Mocha**, **Tokyo Night**, **Gruvbox**, **Rosé Pine**. The choice is remembered in the browser (`localStorage["theme"]`) and applied before the page paints, so there is no light flash. Palette colours come from each theme's own repository (source noted above each CSS block); the in-between shades (chip fill, heatmap steps, paused-card tint) are blends of that palette's colours. Dracula's and Nord's comment greys were lightened for muted text so every theme meets WCAG AA contrast.
- **Ink** (warm charcoal with cream text, the light theme's paper look in the dark) replaces the old cool blue-grey dark theme as the default when the OS is dark.
- Dark themes set `color-scheme: dark`, so native controls (the project dropdown, scrollbars) are dark too.
- Week view: a day-by-day heatmap (Mon–Sun) above the project bars, shaded by commits relative to the week's busiest day. Like the Month heatmap, hover shows the day's tasks and clicking opens it in the Day view.

## 1.0.3 – 2026-11-26

### Fixed
- `tracker scan` now rebuilds the dashboard, and `tracker` builds it if it doesn't exist yet. Before, following the setup steps (`tracker init`, `tracker scan`, `tracker`) opened "dashboard.html not built yet", and a rescan didn't show on the page until something else rebuilt it.

### Added
- Several root folders: `tracker init --root ~/code --root ~/OneDrive/Work` (or `"roots": [...]` in `config.json`; the interactive question takes several separated by `;`). Every repo under any of them is scanned once.

## 1.0.2 – 2026-11-26

### Fixed
- Before the first `tracker scan` (no `commits.json` yet), adding or changing a task no longer prints "warning: dashboard rebuild failed"; the dashboard is built empty and its header says "no commits scanned yet (run: tracker scan)". Agents connected right after `tracker init` no longer get that warning in every tool result.

## 1.0.1 – 2026-11-26

Published on PyPI: `pipx install personal-work-dashboard`. No code changes.

### Added
- Package details for PyPI (licence, author, links, classifiers); README links work on the PyPI page.
- `.github/workflows/publish.yml`: publishing a GitHub release uploads that version to PyPI (trusted publishing). See `docs/operations/releasing.md`.

## 1.0.0 – 2026-11-20

First stable release. No code changes since 0.10.0; this marks the three v1.0 steps as done:
- **Any OS:** installable Python package for macOS, Windows and Linux (0.8.0).
- **Any agent:** `tracker mcp` and `tracker setup` for Claude Code, Cursor and Antigravity (0.9.0).
- **Right commits on the right task:** linking by the branch each commit was made on, with corrections from the dashboard (0.10.0).

## 0.10.0 – 2026-11-19

Commits are linked to the task whose branch they were made on.

### Added
- The scanner remembers the branch each commit was made on (`branch` in `commits.json`): from branch reflogs, then each checkout's HEAD reflog (so branches merged fast-forward and deleted still count), then branches that hold the commit while the default branch doesn't.
- Tasks record their branch when added with `--path` or started (`tracker start <id> --path <folder>`, `tracker_start` `path`), unless another open task already holds it.
- Corrections: `tracker branch` / `tracker move`, edit-server actions `branch` / `move`, MCP tools `tracker_branch` / `tracker_move`, and in the details panel a branch picker and "Move…" on each commit.

### Changed
- Linking (`links.assign`) works across the whole board: a task gets its window's commits on its own branch, of unknown branch, or on branches no other task claims; overlapping tasks in one repo no longer share each other's commits (on the owner's data: commits linked to 2+ tasks 192 → 60).
- Agent rules ask agents to pass their workspace folder when starting a task.

## 0.9.0 – 2026-11-03

AI tools other than Claude can keep the tracker in sync.

### Added
- `tracker mcp`: a stdio MCP server with seven tools (`tracker_todo`, `tracker_add`, `tracker_start`, `tracker_note`, `tracker_pause`, `tracker_done`, `tracker_drop`); `tracker_add` works out project and repo from the agent's workspace folder. See `docs/api/mcp.md`.
- `tracker setup claude-code | cursor | antigravity [--remove]`: writes the rules, the MCP connection and the no-prompt permissions into that tool's own files, backed up first and fully undoable; asks whether the tool should also write the daily summaries. See `docs/operations/agent-setup.md`.
- `tracker add --path <folder>`: project and repo from a folder.
- Config `summariser_input` (`"stdin"` or `"agy-stream-json"` for Antigravity's `agy`).

### Changed
- The summariser runs in an empty folder inside the data folder (`summariser/`).
- A summariser that times out is stopped together with every program it started (on Windows the `.cmd` shims of `agent` / `agy` otherwise left the real program running and the timeout never returned).

## 0.8.0 – 2026-10-23

First installable version: the scripts are now a Python package that runs on macOS and Windows (Linux is tested in CI).

### Added
- `tracker` is a package command (`pipx install git+https://github.com/TreeOck/personal-work-dashboard`); `tracker --version`, and the version in the dashboard header.
- `tracker init` (first-run config), `tracker migrate` (move data from the old script layout), `tracker schedule on|off|status` (daily refresh via launchd on macOS, Task Scheduler on Windows, a crontab line on Linux).
- Config settings `timezone` (IANA name for day boundaries; default: this computer's) and `summariser` (any command that reads a prompt on stdin and prints JSON; default Claude; none = no summaries).
- Edit server: `GET /api/version`; `/api/ping` now reports `home` and `version`, and a server from an older version is replaced.
- GitHub Actions: the tests run on Windows, macOS and Linux.
- MIT licence.

### Changed
- Data lives in `~/.personal-tracker` (`%USERPROFILE%\.personal-tracker` on Windows), or `$TRACKER_HOME`, instead of next to the code.
- All data files are read and written as UTF-8 with a lock that works on both OS families; repo paths are stored with `/`.
- The dashboard shows times in the configured timezone, labelled by the browser (for example `GMT+5:30` instead of `IST`).
- The 3D desk build writes `desk-template.html` into the data folder; its ink palette moved to `src/personal_tracker/data/inks.json`.
- Python 3.11 or newer is required (was 3.9).

### Removed
- `bin/tracker`, `refresh.sh`, `launchd/` and `config.example.json` (replaced by the package command, `tracker refresh`, `tracker schedule` and `tracker init`).

### Earlier work (kept in git history)
Pause status and editing tasks from the dashboard (`tracker pause`, local edit server), the 3D desk, threads, standup and report copy.
