# MCP server (`tracker mcp`)

`tracker mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server over **stdio**. AI apps (Cursor,
Antigravity, …) start it themselves; `tracker setup <tool>` writes the app config that does that (see
[agent-setup.md](../operations/agent-setup.md)). It is the same `todo.*` code the CLI and the edit server use, so
every change takes the file lock and rebuilds the dashboard.

## Transport

- JSON-RPC 2.0, one JSON object per line, UTF-8, `\n` line endings, on stdin/stdout. The server exits when stdin closes.
- **Only protocol messages are written to stdout.** Warnings and crashes go to `<data folder>/mcp.log` (rolled over
  to `mcp.log.1` past 1 MB).
- The command an app runs: `<absolute python> -P -m personal_tracker mcp` (no PATH or working-folder dependence).

## Methods

| Method | Result |
|---|---|
| `initialize` | `protocolVersion`: the client's if it is `2025-11-25`, `2025-06-18` or `2025-03-26`, else `2025-11-25`; `capabilities: {"tools": {}}`; `serverInfo: {"name": "personal-work-dashboard", "version": <package version>}` |
| `ping` | `{}` |
| `tools/list` | `{"tools": [...]}` (below) |
| `tools/call` | `{"content": [{"type": "text", "text": ...}], "isError": bool}` |
| any notification (no `id`) | no reply |

Protocol errors: unparseable line → `-32700` (id `null`); not an object / no `method` → `-32600`; unknown method →
`-32601`; `tools/call` without a tool name → `-32602`; a bug while handling → `-32603`. The server keeps reading after
every error.

## Tools

| Tool | Arguments | Text on success |
|---|---|---|
| `tracker_todo` | `all` (boolean, optional: include done/dropped) | one line per task (`tracker todo` format), or `no open tasks` |
| `tracker_add` | `title` (string, required), `path` (string, required: the agent's workspace folder), `project`, `repo`, `plan` (strings, optional) | first line the new id (`t-0007`), then the task line; a note if `path` is outside the configured root |
| `tracker_start` / `tracker_done` / `tracker_drop` | `id` (string, required) | the task line, or `already <status>: …` |
| `tracker_pause` | `id` (required), `reason` (optional; saved as a `Paused: …` note) | the task line, or `already paused: …` |
| `tracker_note` | `id`, `text` (both required) | the task line |

**Project and repo come from `path`** (the server's own working folder is unreliable: apps start it in `/`, `~` or the
project): project = the first folder under the configured root, repo = the first git repo at most 3 levels below the
root (the scanner's rule). `project` / `repo` arguments override them. A path outside the root gives a task with no
project.

## Tool errors

Failures are tool results with `isError: true`, never protocol errors and never tracebacks:

- the tracker's own messages, e.g. `no task with id t-0999 (run: tracker todo --all)`,
  `can only pause a task that's in progress (t-0001 is todo)`, `no config at … -- run: tracker init`;
- argument problems: `missing required argument: title`, `argument text must be a string`, `unknown tool: <name>`;
- anything unexpected: `internal error: <ExceptionType> (details in <data folder>/mcp.log)`; the traceback is in the log.

Warnings the tracker prints (e.g. a project folder that doesn't exist) are appended to the result text and logged.
