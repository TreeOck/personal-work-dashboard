# Changelog

Versions follow `pyproject.toml` (the only place the version is written). Before 1.0 anything may still change.

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
