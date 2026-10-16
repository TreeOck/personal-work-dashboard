# Personal Work Dashboard

A local day / week / month view of your own git commits across every repo in a folder. Commits are grouped into tasks with short written summaries, and there is a "Current" board for work in progress.

- The dashboard is one self-contained HTML file. It works offline and needs no server.
- Summaries for new commits are written by `claude -p` (Claude Code's non-interactive mode) with no tools enabled. Its JSON output is validated before it's saved.
- Everything stays on your machine. Your data files are gitignored.

## Requirements

- macOS (uses `open` and launchd); Python 3.9+
- [Claude Code](https://claude.com/claude-code), logged in. Only needed for automatic summaries.

## Setup

```bash
cp config.example.json config.json        # set "root" (folder with your repos) and every email you commit as
echo '{"tasks": []}' > tasks.json
python3 scan.py --since 2026-09-01        # first scan: pick how far back to go
./refresh.sh                              # summarise and build dashboard.html
ln -s "$PWD/bin/tracker" ~/.local/bin/tracker   # optional CLI (any directory on your PATH)
```

Daily refresh at 17:00 via launchd. It runs on wake if the Mac was asleep, and it can reach the Keychain where Claude Code keeps its login, which cron cannot:

```bash
sed "s|__DIR__|$PWD|g" launchd/refresh.plist.example > ~/Library/LaunchAgents/com.personal-work-dashboard.refresh.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.personal-work-dashboard.refresh.plist
```

## Using it

```bash
tracker                      # open the dashboard
tracker refresh              # rescan git, summarise, rebuild, open
tracker add "Title" -p myproject -r my-repo [--plan path]   # prints an id, e.g. t-0007
tracker start t-0007 | tracker done t-0007 | tracker drop t-0007
tracker note t-0007 "tests passing"
tracker todo [--all]
```

- **Views:** Current (board), Day (one day), Week and Month. Use ◀ ▶ (or `←` `→`) to move between periods; the Day view skips days with no commits. The numbers cover the period on screen, show the change against the previous period, and follow the project filter and search.
- **Threads:** related tasks across days are grouped into threads (e.g. "Billing: invoice export"). The Week and Month views list threads, and the Month view adds the top 5 as Highlights. Threads are assigned automatically by the summariser.
- **To-do ↔ commits:** a to-do task is linked to the commits in its repo (or whole project if no repo) made between `tracker start` and `tracker done`. `tracker done` rescans git first, so recent commits count.
- **Copy standup / Copy report:** standup text (Yesterday / Today / Blockers) or a Markdown report of the period on screen.
- **Current board:** In progress and To do at the top; finished tasks below as one-line rows grouped by day (today and yesterday open, older days folded).
- **Details panel:** click any card or row, on any view, to open a side panel with all of its notes, start/finish times, the plan, every commit and (for summarised tasks) the other tasks in its thread. `Esc` closes it.
- **Month heatmap:** hover over a day to see its tasks, then click to open it in the Day view (on touch screens, tap once to preview and again to open).
- **Keys:** `c` `d` `w` `m` switch views, `←` `→` change period, `/` search, `Esc` close / clear. Search matches task ids too: typing `t-0027` shows that card (from any view), and while searching the Done log covers every finished task, not just the last 7 days.
- A *project* is a top-level folder under `root`, and a *repo* is a git repo inside it, up to 3 levels deep.

To have Claude Code keep the Current board in sync, add a rule to your `~/.claude/CLAUDE.md` telling it to run `tracker add` / `start` / `done` when work starts and ends.

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

`build.py` writes `desk.html` next to `dashboard.html` whenever `desk-template.html` exists, so the 5pm refresh keeps it current.
Project inks: `python3 inks.py list` / `python3 inks.py set <project> <ink-id>` (palette in `desk/src/data/inks.json`).
Assets are CC0 from Poly Haven, pinned with checksums in `desk/assets.lock.json`; fonts are Caveat (OFL) and Special Elite (Apache 2.0).
Desk tests: `cd desk && npx vitest run`.

## How it works

| File | Role |
|---|---|
| `scan.py` | Reads commits by your emails on local and remote branches (14-day lookback by default) and merges them into `commits.json`. Older history is kept. |
| `summarise.py` | Sends commits that no task covers yet to `claude -p --model sonnet` and asks for JSON. It checks that every commit appears exactly once, with the right date and project, then appends to `tasks.json`. On failure nothing is written, and the commits show as "unsummarised". |
| `links.py` | Works out which commits belong to each to-do task (computed on every build). |
| `todo.py` | The current-tasks list (`todo.json`). Each change takes a file lock, writes atomically and rebuilds the page. |
| `build.py` | Inlines the JSON into `template.html` and writes `dashboard.html`. Builds are serialised so the page is never stale. |
| `refresh.sh` | scan, then summarise, then build. Logs to `refresh.log`. |

`python3 summarise.py --backfill-threads` gives a thread to any task without one (used once, when upgrading older data).

Tests: `python3 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/python -m pytest tests`

`tasks.json` is plain JSON, so you can edit summaries by hand and run `python3 build.py`. Days are grouped in IST (`Asia/Kolkata`); the timezone is set in `template.html` and `summarise.py`.
