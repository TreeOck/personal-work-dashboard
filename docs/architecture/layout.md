# Layout

## Package (`src/personal_tracker/`)
```
cli.py        the `tracker` command (argparse); every subcommand lands here
todo.py       current-tasks list: add / start / pause / done / drop / note  (locks, atomic writes, rebuild)
scan.py       git -> commits.json            summarise.py   commits -> tasks.json via the configured summariser
links.py      commits <-> to-do tasks        build.py       JSON -> dashboard.html / desk.html
inks.py       project -> ink colours         server.py      local edit server (see docs/api/edit-server.md)
setup.py      init / migrate                 schedule.py    daily refresh (launchd / Task Scheduler / cron line)
config.py     config.json -> Config          files.py       UTF-8 JSON, atomic replace, exclusive lock
paths.py      the data folder                errors.py      TrackerError (shown as one line, exit 1)
templates/dashboard.html     data/inks.json (ink palette, also imported by the desk)
```
Outside the package: `desk/` (3D desk, TypeScript/three.js, optional, built with `npm run build` into the data folder), `tests/`, `docs/`.

## Data folder
`$TRACKER_HOME`, else `~/.personal-tracker` (Windows: `%USERPROFILE%\.personal-tracker`). Files are listed in the README. The CLI never writes outside it, except `tracker schedule` (LaunchAgent / scheduled task) and `tracker migrate` (renames the old files it moved).

## Processes
- `tracker <command>`: one short process; it takes `todo.json.lock` for edits and `build.lock` for builds.
- Edit server: one background process per data folder and version (`server.json` holds its pid and port). It never edits files itself: each request runs `python -m personal_tracker <command>`, so the CLI's lock, git rescan and rebuild apply.
- Daily refresh: the OS scheduler runs `tracker refresh --quiet` (scan, summarise, build; log in `refresh.log`).

## Where the OS differences live
| Concern | Where | macOS / Linux | Windows |
|---|---|---|---|
| File lock | `files.lock` | `fcntl.flock` | `msvcrt.locking` on byte 0, retried |
| Atomic write | `files.write_text` | `os.replace` | same, retried on `PermissionError` |
| Text encoding | everywhere | UTF-8 | UTF-8 (never the code page) |
| Repo paths in data | `scan.rel_posix` | `/` | `/` |
| Open a page | `webbrowser` | default browser | default browser |
| Detach the server | `server.detach_kwargs` | new session | `pythonw.exe`, `DETACHED_PROCESS`, no console window |
| Stop a server | `server.terminate` | SIGTERM | `taskkill /F` |
| Find the summariser | `summarise.resolve_command` | `shutil.which` | `shutil.which` (finds `.cmd` / `.exe`) |
| Daily job | `schedule.py` | LaunchAgent (Linux: crontab line) | `schtasks` |
