# Personal Work Dashboard

A local day / week / month view of your own git commits across every repo in a folder. Commits are grouped into tasks with short written summaries, and there is a "Current" board for work in progress that you can edit from the page.

- The dashboard is one self-contained HTML file in your data folder. It works offline; opening it through `tracker` also lets you edit tasks.
- Summaries for new commits come from a command you choose (Claude Code's `claude -p` by default, with no tools enabled). Its JSON output is validated before it's saved, and with no summariser configured the commits just stay "unsummarised".
- Everything stays on your machine.
- Runs on macOS and Windows (CI also runs the tests on Linux). Python 3.11 or newer.

## Install

You need Python 3.11+ and git. [pipx](https://pipx.pypa.io) keeps the tool in its own environment and puts `tracker` on your PATH.

**macOS**
```bash
brew install pipx && pipx ensurepath
pipx install git+https://github.com/TreeOck/personal-work-dashboard
```

**Windows** (PowerShell; install Python from python.org with "Add python.exe to PATH" ticked, and [Git for Windows](https://git-scm.com/download/win))
```powershell
py -m pip install --user pipx
py -m pipx ensurepath          # then open a new terminal
pipx install git+https://github.com/TreeOck/personal-work-dashboard
```

**Linux**: `pipx install git+https://github.com/TreeOck/personal-work-dashboard`, then use `cron` for the daily refresh (below).

For development: `git clone` the repo and `pipx install --editable .` (or `pip install -e ".[test]"` in a virtualenv).

## First run

```bash
tracker init                  # asks for the folder holding your repos and the email(s) you commit as
tracker scan --days 30        # first scan: choose how far back to go
tracker                       # opens the dashboard
tracker schedule on           # optional: refresh every day at 17:00 (--at HH:MM to change)
```

`tracker init` can also take everything as flags (`--root`, `--email` (repeatable), `--timezone`, `--summariser "<command>"` or `--no-summariser`), and refuses to overwrite an existing config without `--force`.

Daily refresh: `tracker schedule on|off|status` uses launchd on macOS (it runs on wake if the Mac was asleep, and can reach the Keychain where Claude Code keeps its login, which cron cannot) and Task Scheduler on Windows. On Linux it prints a crontab line to add with `crontab -e`.

Coming from the old script layout (`todo.py`, `refresh.sh`, data next to the code)? Run `tracker migrate`; see `docs/operations/install.md`.

## Using it

```bash
tracker                      # open the dashboard (editable: see below)
tracker refresh              # rescan git, summarise, rebuild, open (--quiet: no output, no browser)
tracker add "Title" -p myproject -r my-repo [--plan path]   # prints an id, e.g. t-0007
tracker start t-0007 | tracker done t-0007 | tracker drop t-0007
tracker pause t-0007 "waiting on review"     # reason optional; `tracker start t-0007` resumes
tracker note t-0007 "tests passing"
tracker todo [--all]
tracker --version
```

Other commands: `scan [--days N] [--since DATE]`, `summarise [--backfill-threads]`, `build`, `serve` (edit server in the foreground), `desk`, `inks`, `init`, `migrate`, `schedule`.

- **Views:** Current (board), Day (one day), Week and Month. Use ◀ ▶ (or `←` `→`) to move between periods; the Day view skips days with no commits. The numbers cover the period on screen, show the change against the previous period, and follow the project filter and search.
- **Threads:** related tasks across days are grouped into threads (e.g. "Billing: invoice export"). The Week and Month views list threads, and the Month view adds the top 5 as Highlights. Threads are assigned automatically by the summariser.
- **To-do ↔ commits:** a to-do task is linked to the commits in its repo (or whole project if no repo) made between `tracker start` and `tracker done`. `tracker done` rescans git first, so recent commits count.
- **Copy standup / Copy report:** standup text (Yesterday / Today / Blockers) or a Markdown report of the period on screen.
- **Current board:** In progress and To do at the top, then a Paused shelf (each card shows why it was paused), then finished tasks as one-line rows grouped by day (today and yesterday open, older days folded).
- **Pausing:** for work put aside after it started. A paused task stays on the board and in `tracker todo`, isn't listed in standup "Today", and commits made while it's paused aren't linked to it.
- **Editing from the page:** `tracker` opens the dashboard through a small local server (127.0.0.1 only), so you can type a new task in the box at the top of Current (`n` focuses it) and, in a task's details panel, start / pause (with a reason) / resume / mark done / drop / reopen it or add a note. Every change runs the `tracker` command, exactly like the CLI. Opened as a plain file, the page is read-only. Details: `docs/api/edit-server.md`.
- **Details panel:** click any card or row, on any view, to open a side panel with all of its notes, start/finish times, the plan, every commit and (for summarised tasks) the other tasks in its thread. `Esc` closes it.
- **Month heatmap:** hover over a day to see its tasks, then click to open it in the Day view (on touch screens, tap once to preview and again to open).
- **Keys:** `c` `d` `w` `m` switch views, `←` `→` change period, `/` search, `n` new task (when editable), `Esc` close / clear. Search matches task ids too: typing `t-0027` shows that card (from any view), and while searching the Done log covers every finished task, not just the last 7 days.
- A *project* is a top-level folder under `root`, and a *repo* is a git repo inside it, up to 3 levels deep.

To have an AI agent keep the Current board in sync, add a rule to its instructions telling it to run `tracker add` / `start` / `pause` / `done` when work starts, stops and ends (see `docs/operations/install.md`).

## 3D desk (optional showpiece)

A photoreal desk view of the same data, built with three.js, where everything behaves like the real thing: in-progress tasks as clipped stacks of index cards on a leather mat, to-dos as sticky-note pads, this week's finished work as a stack in the done tray, one pen per project in its own ink, today's calendar, and a daily tally pad.

**Using it:** hover to see what things are; click a task, sticky note, the calendar or the notepad to bring it up close.
Clicking a task picks it up to read: the clip comes off and is left on the mat. `Space` or a click on the right half thumbs the top card under the stack (a click on the left half goes back, as does `Shift`+`Space`, bringing the bottom card back up), and one more `Space` after the last card restores the order. A sticky pad is picked up the same way, and its notes flip up over the glued edge. The tally pad stays on the desk and its pages flip over the binding. The calendar (`5`) shows today; `Space` flips back through the past week over its wire coil, `Shift`+`Space` comes forward, and clicking a page opens the Day binder at that date. The done tray (`3`) holds a typed sheet for each task finished this week, newest on top: lift it out and read it like the cards. Click a binder to read it: it slides out of the stack and opens at today, this week or this month; `←` `→` go between periods, `Space` turns single leaves, `Home` comes back to now, and it goes back on top of the stack. `←` `→` go to the neighbouring task; `Esc`, right-click or clicking the empty desk puts things back.

Performance: page textures are sized to your screen and loaded before anything moves; while something moves, big screens render at a lower internal resolution (back to full the moment it stops). Open `desk.html?bench` to measure: after about 15 seconds the tab title shows frame and texture timings, which is how Safari was profiled.
The notepad is a daily tally pad: today on top; `Space` flips back through the last 14 days.
Keys: `1` tasks · `2` sticky notes · `5` calendar · `6` notepad · `0` overview. More than 6 tasks (or 8 sticky notes) pile up; click the pile to fan it out. Respects "Reduce motion".

```bash
cd desk && npm install && npm run assets && npm run build   # once, and after desk code changes
tracker desk            # open it (tracker desk refresh: rescan git first)
```

`npm run build` writes `desk-template.html` into your data folder, and `tracker build` (run by every task change and by the daily refresh) writes `desk.html` next to `dashboard.html` whenever that template exists.
Project inks: `tracker inks list` / `tracker inks set <project> <ink-id>` (palette in `src/personal_tracker/data/inks.json`).
Assets are CC0 from Poly Haven, pinned with checksums in `desk/assets.lock.json`; fonts are Caveat (OFL) and Special Elite (Apache 2.0).
Desk tests: `cd desk && npx vitest run`. The desk isn't part of the pip/pipx install; it needs a clone of the repo and Node.

## Settings and data

Everything lives in one folder: `$TRACKER_HOME`, else `~/.personal-tracker` (`%USERPROFILE%\.personal-tracker` on Windows).

| File | What |
|---|---|
| `config.json` | Your settings (below) |
| `todo.json` | Current tasks (fields in `docs/schema/todo-json.md`) |
| `tasks.json` | Summarised work, plain JSON: edit by hand, then `tracker build` |
| `commits.json` | Scanned commits; older history is kept |
| `inks.json` | Project → ink for the desk |
| `dashboard.html`, `desk.html` | Built pages |
| `server.json`, `*.log`, `*.lock` | Runtime files |

`config.json`:

```json
{"root": "~/code", "author_emails": ["you@example.com"], "timezone": "Europe/London",
 "summariser": ["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence"]}
```

- `root`: the folder with your repos. A *project* is a top-level folder under it, and a *repo* is a git repo inside it, up to 3 levels deep.
- `author_emails`: every email you commit as.
- `timezone`: IANA name used for day boundaries. Leave it out (or `null`) to use this computer's timezone.
- `summariser`: the command and its arguments. It receives the prompt on stdin and must print JSON (UTF-8). `null` turns summaries off.

## How it works

| Module (`src/personal_tracker/`) | Role |
|---|---|
| `cli.py` | The `tracker` command |
| `scan.py` | Reads commits by your emails on local and remote branches (14-day lookback by default) and merges them into `commits.json`. |
| `summarise.py` | Sends commits that no task covers yet to your summariser and asks for JSON. It checks that every commit appears exactly once, with the right date and project, then appends to `tasks.json`. On failure nothing is written, and the commits show as "unsummarised". `--backfill-threads` gives a thread to any task without one. |
| `links.py` | Works out which commits belong to each to-do task (computed on every build). |
| `todo.py` | The current-tasks list. Each change takes a file lock, writes atomically and rebuilds the page. |
| `server.py` | Local edit server: serves the dashboard with a per-run token and turns its edits into `tracker` calls (`docs/api/edit-server.md`). |
| `build.py` | Inlines the JSON into `templates/dashboard.html` and writes `dashboard.html` (and `desk.html`). Builds are serialised so the page is never stale. |
| `files.py`, `paths.py` | UTF-8 JSON with atomic replace, one lock for every OS, the data folder. |
| `setup.py`, `schedule.py` | `init` / `migrate`, and the daily refresh. |

More: `docs/architecture/layout.md`.

Tests: `pip install -e ".[test]"` then `python -m pytest tests`. CI runs them on Windows, macOS and Linux (`.github/workflows/test.yml`).

## Licence

MIT, see `LICENSE`.
