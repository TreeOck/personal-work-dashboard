# Edit server (`server.py`)

Lets `dashboard.html` change `todo.json`. Python standard library only, bound to `127.0.0.1`.
`tracker` (or `tracker open` / `tracker refresh`) starts it, or reuses a running one, and opens
`http://127.0.0.1:47615/`. If port 47615 is taken it uses any free port. The live port and pid are in
`server.json` (gitignored); the log is `server.log`. It exits after 12 hours with no requests.

Opened as a plain file (`dashboard.html`), the page is read-only and shows "read-only · run tracker to edit".

## Security

| Check | Why |
|---|---|
| Binds `127.0.0.1` only | Not reachable from the network |
| `Host` must be `127.0.0.1:<port>` or `localhost:<port>` (all routes) | Blocks DNS-rebinding pages |
| `Origin` must equal `http://<Host>` (POST) | Blocks other sites posting to it |
| `X-Tracker-Token` must match (POST) | Random per run; written into the page as `<meta name="tracker-token">` when served. A page from an older run gets 403 "stale page: reload it" |
| Body ≤ 16 KB; fields validated; `todo.py` run with an argv list and `--` | No shell, and user text can't become a CLI flag |

## Routes

### `GET /` (also `/dashboard.html`)
`dashboard.html` with the token meta tag added. `Cache-Control: no-store`. 500 if the page isn't built yet.

### `GET /api/ping`
`200 {"app": "tracker", "dir": "<folder>"}`. `tracker` uses it to tell its own server from anything else on the port.

### `POST /api/todo`
Headers: `Content-Type: application/json`, `X-Tracker-Token`, same-origin `Origin`.

| `action` | Other fields | Runs |
|---|---|---|
| `add` | `title` (required, ≤300), `project`, `repo` (optional, `[A-Za-z0-9._-]`) | `todo.py add [-p] [-r] -- title` |
| `start` | `id` | `todo.py start -- id` (also resumes a paused task and reopens a closed one) |
| `pause` | `id`, `text` (optional reason, ≤2000) | `todo.py pause -- id [reason]` |
| `done` / `drop` | `id` | `todo.py done|drop -- id` |
| `note` | `id`, `text` (required, ≤2000) | `todo.py note -- id text` |

`id` must match `t-` followed by 4 or more digits. `todo.py` takes its file lock, writes and rebuilds the page
before the response returns, so the page simply reloads.

| Status | Body | When |
|---|---|---|
| 200 | `{"ok": true, "out": "<todo.py stdout>", "warning": "<stderr>" or null}` | Done. For `add`, `out` is the new id |
| 400 | `{"error": "..."}` | Bad JSON, unknown action, failed validation, or `todo.py` refused (e.g. pausing a to-do) |
| 403 | `{"error": "..."}` | Host, Origin or token check failed |
| 404 | `{"error": "no task with id t-0999 ..."}` | Unknown id (or unknown path) |
| 413 | `{"error": "request too large"}` | Body over 16 KB |
| 500 | `{"error": "todo.py timed out"}` | `todo.py` ran longer than 180 s |
