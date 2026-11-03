# Agent setup: the tracker for Claude Code, Cursor and Antigravity (v1 step 2 of 3)

Status: draft, awaiting approval · Branch: `feat/agent-setup` · Tracker: t-0056 · Target version: 0.9.0

## 1. Intent

The owner's tracker stays in sync on its own because Claude Code follows the rules in the owner's `~/.claude/CLAUDE.md` §10 and runs the `tracker` command. This step gives **colleagues** the same experience with the agent they use: **Claude Code (in the terminal), Cursor and Antigravity**. When a colleague's agent starts real work it checks the board, reuses or adds a task, starts it, notes milestones, pauses work that is put aside, and marks it done once verified, without being asked. Their daily commit summaries can be written by their own tool if they choose.

**Success:** a colleague installs the tracker (v0.8.0 flow: `pipx install …`, `tracker init`), runs `tracker setup <tool>` once, and from then on their agent keeps the board in sync with no further involvement (at most one "Allow" click in Cursor).

**Goals**
- `tracker setup claude-code | cursor | antigravity` and `--remove`.
- A built-in MCP server (`tracker mcp`) for Cursor and Antigravity.
- One source of truth for the rules text, kept equivalent to §10.
- Optional summaries via the colleague's own tool, asked during setup (owner's decision: option b).
- macOS and Windows.

**Non-goals (a later patch):** Codex, Copilot, Gemini CLI, other tools; Cursor rules written into repos; anything touching repos at all; team/enterprise admin settings.

**Anti-goals (a failure even if it works):**
- Overwriting or reformatting a colleague's existing config or rules content.
- Using a colleague's AI quota for summaries without them saying yes.
- An approval prompt on every tracker call.
- Anything that needs the colleague to understand MCP.

## 2. What was verified (2026-11-03, on the owner's Mac, Cursor + Antigravity installed for this test)

A throwaway stdlib MCP server (`~/tracker-step2-test/spike/`, logs every message) was registered in both apps against a scratch tracker; a demo project held an `AGENTS.md` rule. Evidence: `~/tracker-step2-test/results/`.

| | Cursor (app + `agent` CLI 2026.10.22) | Antigravity (app + `agy` CLI 1.4.12) |
|---|---|---|
| Global MCP config | `~/.cursor/mcp.json` (did not exist; created) | `~/.gemini/config/mcp_config.json` (existed, 0 bytes) |
| Config shape that worked | `{"mcpServers": {"<name>": {"command": "<abs path>", "args": [...]}}}` | same |
| Server cwd at start | `/`, `~` or the project (varies) | `/` |
| Client sends `roots` capability | yes | yes |
| Agent followed a rule unprompted | yes: todo → add → start → note → done, both requests | yes, same sequence |
| Approvals | asked once ("Allow / Always allow / Reject"); plain Allow was never asked again, also in a new chat. Stored internally (`state.vscdb`), not in a file | asked once per tool (this time / conversation / project / always / no). "Always" stored in `~/.gemini/config/config.json` → `userSettings.globalPermissionGrants.allow` as `mcp(server/tool)`. **Replacing them with `mcp(tracker-test/*)` gave zero prompts in a new conversation.** |
| Global rules file | none (User Rules live in the settings UI only, per docs) | `~/.gemini/AGENTS.md` / `GEMINI.md` (per docs; project `AGENTS.md` verified) |
| Headless summaries | `agent -p --mode ask --trust --output-format text` with the prompt **on stdin**: clean JSON, Hindi intact, exit 0, 6–9 s. `-p` alone "has access to all tools, including write and shell"; `--mode ask` is read-only | `agy -p="<prompt>"` works (default mode; `--mode plan` produced no output after a denied tool call); plain stdin is **not** read. `--input-format stream-json --output-format stream-json` with `{"event":"user","message":{"content":"..."}}` on stdin works, answer in the `result` event's `result.response`, status `SUCCESS`; a 53,089-char prompt worked (beyond Windows' ~32k command-line limit) |
| Sign-in for headless | `agent login` (browser) | interactive `agy` once |

Claude Code: the owner's `~/.claude/settings.json` uses `permissions.allow` entries like `Bash(kubectl get:*)`; rules come from `~/.claude/CLAUDE.md`.

## 3. Current state (code, v0.8.0)

`todo.py` exposes `add(title, project, repo, plan)`, `set_status(tid, start|done|drop)`, `pause(tid, reason)`, `note(tid, text)`, `list_items(all_)`, `fmt(item)`, all raising `TrackerError` with one-line messages and taking the file lock; build/scan output is already swallowed inside them. `config.Config` has `root`, `author_emails`, `timezone`, `summariser` (argv; prompt on stdin). `summarise.ask(prompt, argv)` runs the summariser. `cli.py` dispatches subcommands; `setup.py` holds `init`/`migrate`. Data folder: `paths.home()`.

## 4. Design

### 4.1 `tracker mcp` (stdio MCP server, standard library only)
- JSON-RPC 2.0, one message per line on stdin/stdout. Handles `initialize` (both apps requested protocol version `2025-11-25` in the test; answer with the client's version if it is `2025-11-25`, `2025-06-18` or `2025-03-26`, else `2025-11-25`), `notifications/initialized`, `tools/list`, `tools/call`, `ping`; unknown request methods → error `-32601`; notifications are never answered. **Nothing but protocol messages is ever written to stdout**; logs go to `<data folder>/mcp.log`.
- Tools (names and descriptions are part of the product; descriptions state *when* to use each):
  - `tracker_todo` (optional `all`): open tasks, the same lines as `tracker todo`.
  - `tracker_add` (`title`, `path`, optional `project`, `repo`, `plan`): prints the new id.
  - `tracker_start`, `tracker_done`, `tracker_drop` (`id`).
  - `tracker_pause` (`id`, optional `reason`).
  - `tracker_note` (`id`, `text`).
- **Project and repo from the workspace path.** The server's cwd is unreliable (§2), so `tracker_add` takes `path`, the agent's workspace folder. Project = first folder under the configured root; repo = the git repo containing `path` (up to 3 levels, as the scanner does). Explicit `project`/`repo` override. A path outside the root gives no project, with a hint in the result.
- Results: `content` text plus `isError` true with the `TrackerError` message on failure; never a traceback. Calls run in-process through `todo.*`.
- Windows: binary-safe UTF-8 stdin/stdout, `\n` line endings.

### 4.2 `tracker setup <tool> [--remove] [--summaries | --no-summaries]`
Every change is **additive and reversible**: our own key or marked block only, everything else left byte-for-byte as it was, files written atomically, a copy of each file's previous content kept in `<data folder>/setup-backups/` before the first change. Re-running setup updates in place (no duplicates). Malformed JSON in a target file → stop with a clear message, change nothing. The MCP `command` is the absolute path of the running interpreter with `-P -m personal_tracker mcp` (GUI apps don't share the shell's PATH).

| | Claude Code | Cursor | Antigravity |
|---|---|---|---|
| Rules | marked block in `~/.claude/CLAUDE.md` (CLI wording) | printed, with "paste into Settings → Rules → User Rules" (owner's decision) | marked block in `~/.gemini/AGENTS.md` (MCP wording) |
| Connection | none (uses the `tracker` command) | `mcpServers.tracker` in `~/.cursor/mcp.json` | `mcpServers.tracker` in `~/.gemini/config/mcp_config.json` (empty file = `{}`) |
| No prompts | `Bash(tracker:*)` in `~/.claude/settings.json` `permissions.allow` | not possible from a file; setup says "click Allow the first time" | `mcp(tracker/*)` in `~/.gemini/config/config.json` → `userSettings.globalPermissionGrants.allow` |
| Summaries (asked) | `claude -p …` (current default) | `agent -p --mode ask --trust --output-format text`, prompt on stdin | `agy` stream-json adapter (4.3) |

- **Antigravity running:** the app may rewrite `config.json` while open. Setup checks for a running Antigravity and asks the colleague to quit it first (or `--force`).
- **Summaries (owner's decision b):** setup asks "Use <tool> to write your daily summaries? It uses your <tool> account's quota. [Y/n]". Enter = yes. No usable terminal (scripts/agents) = leave summaries unchanged unless `--summaries` is passed. Before enabling, setup checks the CLI exists and is signed in (one tiny test call); if not, it explains how (`agent login` / run `agy` once) and leaves summaries as they were. `--remove` puts back the summariser that was configured before setup.
- **Rules text:** one packaged template with two wordings (CLI commands for Claude Code; tool names for Cursor/Antigravity), content equivalent to §10 incl. "pass your workspace folder as `path`". The CLI gains `tracker add --path <folder>` (same project/repo derivation as the MCP tool) so the Claude Code wording doesn't need the colleague's folder layout spelled out.
- **Summariser command** is stored with its program resolved to an absolute path at setup time, so the scheduled job doesn't depend on PATH (Windows installs `agy` in `%LOCALAPPDATA%\agy\bin`).
- **The owner** already has §10 in `~/.claude/CLAUDE.md`; `setup claude-code` is for colleagues (running it would add a second, equivalent block).
- `tracker setup` with no tool lists the three and their state (installed / not).

### 4.3 Summariser input modes
Config gains optional `summariser_input`: `"stdin"` (default, today's behaviour) or `"agy-stream-json"`. The latter writes one `{"event":"user","message":{"content": prompt}}` line, reads stream-json events, requires a `result` event with `status` `SUCCESS`, and takes `result.response` as the text; anything else is a `TrackerError`. The summariser runs from an empty folder inside the data folder so a read-only agent has nothing to look at.

### 4.4 Version and docs
Version 0.9.0. README (agents section), `docs/operations/agent-setup.md` (per tool: what setup changes, how to undo, Cursor paste step), `docs/api/mcp.md` (tools, arguments, results, errors), config schema (`summariser_input`), CHANGELOG.

## 5. Edge cases
| Case | Behaviour |
|---|---|
| Target config file missing / empty / malformed JSON / not a JSON object | create / treat as `{}` / stop, change nothing / stop |
| Existing server or grant named `tracker` that we didn't write | replace only our key; warn if its content differs |
| Rules file has our block already / has it edited by the user / no trailing newline | replace block in place / replace (block is ours) / append cleanly |
| `--remove` when nothing installed / files deleted since | no-op with a message / skip missing files |
| Setup run twice, or for two tools | idempotent; independent |
| Antigravity open during setup | ask to quit, unless `--force` |
| MCP: malformed line, unknown tool, missing args, unicode, huge text, unknown id, invalid transition | JSON-RPC error or `isError` result; server keeps running |
| MCP: two clients at once (Cursor + Antigravity) | separate processes; the existing file lock serialises writes |
| `path` outside root / missing / nonexistent | task without project, hint in the result |
| Summariser CLI missing / signed out / quota exhausted / hangs | setup refuses to enable it; at refresh time it is a logged `TrackerError` and the page still builds (v0.8 behaviour) |
| Windows: `%USERPROFILE%` paths, `.cmd` shims, `pythonw` | paths from `Path.home()`; command resolved with `shutil.which`; interpreter path absolute |
| Colleague without Claude Code runs `setup claude-code` | still writes rules (harmless), says Claude Code wasn't found |

## 6. Testing (CLAUDE.md §4)
1. **Unit (pytest, CI on Windows/macOS/Linux):** MCP protocol over real pipes (handshake, list, every tool, errors, unicode, malformed input, no stray stdout); path → project/repo; every setup row for missing/empty/malformed/existing files, idempotency, `--remove` restoring the exact previous bytes; summariser prompt flows (Y/Enter/n/no terminal/flags); the `agy-stream-json` adapter against a fake command.
2. **Real apps on this Mac, before they are uninstalled:** remove the spike's config entries and the demo project's `AGENTS.md` first, so only what setup writes is in play. Then `tracker setup cursor` and `tracker setup antigravity` against a scratch data folder; paste the printed rules into Cursor's User Rules; repeat the demo-project test. This proves the machine-wide routes the spike didn't: Antigravity reading `~/.gemini/AGENTS.md`, and Cursor following pasted User Rules. Expected: no prompts in Antigravity, one Allow in Cursor. Then one real summary each through `agent` and `agy`; then `--remove` and check the files match their backups.
3. Docker/sandbox: n/a.

## 7. Left to the builder
Module layout, exact tool descriptions and rules wording (within §4.1/§4.2), backup file naming, how the "is Antigravity running" check is done per OS, `mcp.log` rotation.

## 8. Cleanup after testing
`~/tracker-step2-test/CLEANUP.md` lists everything the test setup and the two installs changed; it is worked through when the owner uninstalls Cursor and Antigravity.
