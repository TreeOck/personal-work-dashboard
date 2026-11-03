# Connecting your AI tool (`tracker setup`)

`tracker setup <tool>` makes an AI coding tool keep your Current board in sync by itself: it adds a task when work
starts, notes milestones, pauses, and marks it done. Supported: `claude-code`, `cursor`, `antigravity`. Run
`tracker init` first (the tracker needs its config).

```
tracker setup                     # which tools are set up
tracker setup antigravity         # set one up (asks whether it should also write your daily summaries)
tracker setup cursor --remove     # undo
```

Options: `--remove` (undo), `--force` (don't refuse while Antigravity is open), `--summaries` / `--no-summaries`
(answer the summaries question up front; without a terminal, e.g. from a script, summaries are left as they are
unless `--summaries` is given).

## What setup changes

Setup only adds or replaces **its own** entries. Everything else in these files is kept: JSON files keep their
indentation, `\u` escapes, line endings and final newline; text files keep every other byte and their line endings
(CRLF stays CRLF). Before a file's first change it is copied to
`<data folder>/setup-backups/<YYYYmmdd-HHMMSS>/<tool>/`, and `<data folder>/setup-state.json` records which files were
touched and which entries setup added. Each run is rehearsed in memory first: if any file is malformed JSON, has an
unexpected shape, isn't UTF-8, or has the begin marker without the end marker, setup stops and **nothing** is written.

| | Claude Code | Cursor | Antigravity |
|---|---|---|---|
| Rules (when to add/start/note/pause/done) | block in `~/.claude/CLAUDE.md` using `tracker` commands | **printed: you paste it** into Cursor → Settings → Rules → User Rules | block in `~/.gemini/AGENTS.md` using the MCP tools |
| Connection | none (it runs the `tracker` command) | `mcpServers.tracker` in `~/.cursor/mcp.json` | `mcpServers.tracker` in `~/.gemini/config/mcp_config.json` |
| No permission prompts | `Bash(tracker:*)` in `~/.claude/settings.json` → `permissions.allow` | can't be set from a file: Cursor asks once, click **Allow** | `mcp(tracker/*)` in `~/.gemini/config/config.json` → `userSettings.globalPermissionGrants.allow` |
| Summaries (if you say yes) | `claude -p --model sonnet …` | `agent -p --mode ask --trust --output-format text` | `agy` with stream-json input |

The rules blocks sit between `<!-- personal-work-dashboard:begin (managed by tracker setup) -->` and
`<!-- personal-work-dashboard:end -->`; running setup again replaces the block (edits inside it are overwritten).

The connection is `<this Python> -P -m personal_tracker mcp` by absolute path, because desktop apps don't see your
shell's PATH. If you reinstall the tracker with a different Python, run setup again. When `TRACKER_HOME` is set, the entry also
passes it on (`"env": {"TRACKER_HOME": …}`), since the apps don't see your shell's environment. An existing `tracker`
server entry that points somewhere else is replaced, with a warning; `--remove` puts it back.

### Notes per tool

- **Claude Code:** the terminal, the IDE extensions and the desktop app's local sessions all read `~/.claude`. Cloud
  sessions run on another machine and can't reach your tracker. If you already have tracker rules in your
  `CLAUDE.md` (the owner does), don't run `setup claude-code`: it would add a second, equivalent block.
- **Cursor:** paste the printed rules once. The first time an agent calls a tracker tool Cursor asks
  "Allow / Always allow / Reject"; plain Allow is remembered.
- **Antigravity:** quit the app (all windows) before setup or `--remove`; while it runs it may rewrite
  `config.json` and drop the grant. Setup refuses while it's open unless you pass `--force`.

## Summaries

Setup asks `Use <Tool> to write your daily summaries? It uses your <Tool> account's quota. [Y/n]` (Enter = yes).
On yes it checks that the tool's command exists and is signed in with one tiny request; if that fails it says how
to fix it (`agent login` for Cursor, run `agy` once for Antigravity, `claude` for Claude Code) and leaves the
summariser as it was. On success it writes `summariser` (program as an absolute path) and `summariser_input` to
`config.json`; `--remove` puts the previous values back if this tool's summariser is still the one in use (if you
or another tool's setup changed it since, it is left alone; setups of two tools undo independently).

## Undo

`tracker setup <tool> --remove` removes only the entries setup added (a grant you already had stays) and puts back
a server entry it replaced. A file that is then the same as before setup gets its
original bytes back; a file setup created that holds nothing else is deleted; a file you (or the app) changed since
keeps those changes. Files deleted since setup are skipped. The backups stay in `setup-backups/` until you delete
them.

## Checking it works

- `tracker setup` lists what's set up.
- Ask the agent to do a small task in a project folder under your root. A task should appear on the board.
- The MCP server logs to `<data folder>/mcp.log`; see [../api/mcp.md](../api/mcp.md) for the protocol and tools.
