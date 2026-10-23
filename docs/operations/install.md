# Install, upgrade and move from the script layout

## Requirements
Python 3.11+, git, and a browser. [Claude Code](https://claude.com/claude-code) only if you want the default summariser.

## Install
See the README for macOS / Windows / Linux. Short form: `pipx install git+https://github.com/TreeOck/personal-work-dashboard`, then `tracker init`, `tracker scan --days 30`, `tracker`.

- **Upgrade:** `pipx upgrade personal-work-dashboard`. The next `tracker` run notices that the running edit server has an older version and replaces it.
- **Uninstall:** `tracker schedule off`, then `pipx uninstall personal-work-dashboard`. Your data stays in the data folder (`~/.personal-tracker`, or `$TRACKER_HOME`); delete it by hand if you want it gone.
- **Where things are:** `tracker schedule status` shows the daily job; `server.log` and `refresh.log` are in the data folder.

## Moving from the script layout (one-off cutover)

For an install that still runs `todo.py` / `refresh.sh` / `bin/tracker` from a checkout with the data next to the code. **Do step 0 before you update the checkout:** updating deletes `bin/tracker`, `todo.py` and `refresh.sh`, so the old `tracker` command, the old daily job and the old edit server stop working the moment it does. Then go in this order and quickly: until step 3 finishes, anything that still calls the old `tracker` writes the old `todo.json`.

```bash
cd <your checkout>

# 0. before updating the checkout (needs the OLD tracker; keeps a baseline and a rollback copy)
tracker todo --all > ~/tracker-before.txt
cp ~/Library/LaunchAgents/com.valiance.personal-tracker-refresh.plist ~/tracker-old.plist   # macOS
[ -f server.json ] && kill $(python3 -c "import json; print(json.load(open('server.json'))['pid'])")   # old edit server, if running

# 1. update the checkout, then replace the old command
git pull                                          # to a version that includes the package
rm ~/.local/bin/tracker                           # the old symlink to bin/tracker (now dangling)
brew install pipx && pipx ensurepath
pipx install --editable . --python /opt/homebrew/bin/python3.12

# 2. move the data (copies, verifies, then renames the originals to *.migrated-YYYYMMDD)
tracker migrate

# 3. replace the old daily job
launchctl bootout gui/$(id -u)/com.valiance.personal-tracker-refresh
rm ~/Library/LaunchAgents/com.valiance.personal-tracker-refresh.plist
tracker schedule on --at 17:00

# 4. check
tracker todo --all | diff - ~/tracker-before.txt   # no output = identical
tracker summarise                                 # first real run of your summariser with the prompt on stdin
(cd desk && npm run build)                        # rebuild the 3D desk into the new data folder (migrate doesn't move it)
tracker                                           # page opens with the green "editing" dot
```

The `*.migrated-*` files left next to the code are git-ignored (they hold your emails and task history).

On Windows there is no old layout to move; install and run `tracker init`.

### Roll back
```bash
tracker schedule off && pipx uninstall personal-work-dashboard
cd <your checkout> && git checkout 048819e        # the last commit before the package move
for f in *.migrated-*; do mv "$f" "${f%.migrated-*}"; done
cp ~/.personal-tracker/todo.json todo.json        # only if you made changes after migrating
ln -s "$PWD/bin/tracker" ~/.local/bin/tracker
cp ~/tracker-old.plist ~/Library/LaunchAgents/com.valiance.personal-tracker-refresh.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.valiance.personal-tracker-refresh.plist
```

## Keeping the Current board in sync with an AI agent
Any agent that can run shell commands can use the tracker. Put this in its instructions file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, Cursor or Copilot rules):

> Record work on the personal tracker with the `tracker` command. When work starts: run `tracker todo` first (reuse an open task's id), otherwise `tracker add "<title>" -p <project> -r <repo>` then `tracker start <id>`. Add milestones with `tracker note <id> "<text>"`. If work is put aside: `tracker pause <id> "<reason>"` (paused tasks still count as open; `tracker start <id>` resumes). When it's verified: `tracker done <id>`; if abandoned: `tracker drop <id>`.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| Page says "read-only · run tracker to edit" | It was opened as a file. Run `tracker` instead. |
| "stale page: reload it" | The page came from an earlier edit-server run. Reload it. |
| "The tracker server isn't running" | The server stopped (12 h idle, or a reboot). Run `tracker` again. |
| Commits stay "unsummarised" | No `summariser` in `config.json`, or its command isn't on PATH (`tracker refresh` prints why; also see `refresh.log`). |
| `no config at ... -- run: tracker init` | First run, or `TRACKER_HOME` points somewhere else. |
| Windows: the daily job uses the wrong data folder | Task Scheduler doesn't see a `TRACKER_HOME` set only in your shell; set it for your user with `setx TRACKER_HOME <folder>`. |
