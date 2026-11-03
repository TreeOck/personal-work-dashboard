# Agent Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let colleagues' Claude Code, Cursor and Antigravity keep the tracker in sync on their own: a built-in MCP server (`tracker mcp`), `tracker setup <tool> [--remove]`, and optional summaries through the colleague's own tool.

**Architecture:** Three new modules: `locate.py` (workspace path → project/repo), `mcp_server.py` (stdio JSON-RPC over `todo.*`), `agent_setup.py` (per-tool, additive, reversible edits of other apps' files plus the summaries question). `summarise.ask` gains an input mode for `agy`. Everything else is unchanged.

**Tech Stack:** Python ≥3.11 standard library only; pytest; GitHub Actions (Windows, macOS, Linux).

**Spec:** `docs/superpowers/specs/2026-11-03-agent-setup-design.md`

## Global Constraints

- No new dependencies. Version `0.9.0` (only in `pyproject.toml`).
- MCP: JSON-RPC 2.0, one JSON object per line; supported protocol versions `2025-11-25`, `2025-06-18`, `2025-03-26`; reply with the client's if supported, else `2025-11-25`. Never write anything but protocol messages to stdout. Server name in every app config: `tracker`.
- Tool names: `tracker_todo`, `tracker_add`, `tracker_start`, `tracker_note`, `tracker_pause`, `tracker_done`, `tracker_drop`.
- Antigravity grant: `mcp(tracker/*)` in `~/.gemini/config/config.json` → `userSettings.globalPermissionGrants.allow`. Claude Code grant: `Bash(tracker:*)` in `~/.claude/settings.json` → `permissions.allow`.
- Files: `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.cursor/mcp.json`, `~/.gemini/config/mcp_config.json`, `~/.gemini/config/config.json`, `~/.gemini/AGENTS.md`, all via `Path.home()`.
- Rules block markers (exact): `<!-- personal-work-dashboard:begin (managed by tracker setup) -->` and `<!-- personal-work-dashboard:end -->`.
- Setup only adds or replaces **its own** key/block/list entry. JSON files keep every other key and value in order; whitespace is normalised to `indent=2` when setup writes (refinement of the spec's "byte-for-byte", which holds for text files). `--remove` writes back the pre-setup backup bytes when what remains equals that backup's content, else removes only its own entries; a file setup created is deleted again when nothing else is in it. Backups: `<data>/setup-backups/<YYYYmmdd-HHMMSS>/<tool>/<file name>` before a file is first changed in a run. State: `<data>/setup-state.json`.
- Summaries question (owner's choice b): `Use <Tool> to write your daily summaries? It uses your <Tool> account's quota. [Y/n] `; Enter = yes; no usable terminal (EOF or not a TTY) = unchanged unless `--summaries`.
- Summariser presets: claude-code `setup.CLAUDE_SUMMARISER` (stdin); cursor `["agent", "-p", "--mode", "ask", "--trust", "--output-format", "text"]` (stdin); antigravity `["agy", "--input-format", "stream-json", "--output-format", "stream-json", "--print-timeout", "600s"]` (`agy-stream-json`). Program resolved to an absolute path at setup.
- All commits: show message, get approval (CLAUDE.md §6); docs in the same commit; no attribution lines. Work only in this worktree; test command `.venv/bin/python -m pytest tests -q` (create `.venv` with Homebrew python3.12 and `pip install -e '.[test]'` first).

## Review Focus

1. **A colleague's existing MCP servers, grants and rules** must survive setup and `--remove` unchanged → Task 4 `test_other_entries_survive_setup_and_remove`.
2. **Antigravity open during setup** must not have the app overwrite our grant silently → Task 5 `test_antigravity_running_refuses_without_force`.
3. **Workspace paths with spaces, non-ASCII, symlinks or outside the root** → Task 1 `test_project_repo_for_edge_paths`.
4. **Summaries chosen but the CLI is missing or signed out** must not switch summaries on → Task 6 `test_summaries_not_enabled_when_check_call_fails`.
5. **Garbage or unexpected input to the MCP server** (blank line, invalid JSON, a notification, unknown method) must not kill it or print noise → Task 2 `test_server_survives_bad_input`.

---

### Task 1: Workspace path → project/repo, and `tracker add --path`

**Files:** Create `src/personal_tracker/locate.py`; modify `cli.py` (add `--path` to `add`); test `tests/test_locate.py`.

**Interfaces:** Produces `locate.project_repo_for(path: str | Path, root: Path) -> tuple[str | None, str | None]`: resolves both paths; if `path` is not under `root` → `(None, None)`; project = first path segment under root; repo = name of the deepest folder containing a `.git` entry between root (exclusive) and `path` (inclusive), at most 3 levels below root, else `None`. CLI: `tracker add TITLE --path DIR` fills `project`/`repo` from it unless `-p`/`-r` are given.

- [ ] **Step 1: Failing tests** in `tests/test_locate.py`:
  - `test_project_repo_for_simple`: root/`dms`/`dms-be` (with `.git`), path `…/dms-be/src` → `("dms", "dms-be")`; path `…/dms` (no repo) → `("dms", None)`.
  - `test_project_repo_for_edge_paths`: root `"my repos"`, project `"प्रोजेक्ट"`, repo `"app"` with `.git` → `("प्रोजेक्ट", "app")`; a symlink to the repo resolves the same; path outside root → `(None, None)`; nonexistent path under root → project from the segment, repo `None`.
  - `test_cli_add_with_path(sandbox)`: `add "T" --path <root>/alpha/alpha-be` (with `.git`) → item project `alpha`, repo `alpha-be`; `-p beta --path …` → project `beta`.
- [ ] **Step 2:** Run → FAIL (module missing). **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** (approval): "Derive project and repo from a workspace path".

### Task 2: `tracker mcp` stdio server

**Files:** Create `src/personal_tracker/mcp_server.py`; modify `cli.py` (`mcp` subcommand → `mcp_server.serve(sys.stdin, sys.stdout)`); test `tests/test_mcp_server.py`.

**Interfaces:** Consumes `todo.*`, `locate.project_repo_for`, `config.load`. Produces `mcp_server.handle(msg: dict) -> dict | None` (one request → one reply; notification → `None`), `mcp_server.serve(stdin, stdout) -> None`, `mcp_server.TOOLS: list[dict]` (name, description, `inputSchema`). `tracker_add` schema: `title` (required), `path` (required: "the absolute path of your workspace folder"), `project`, `repo`, `plan`. `tracker_todo`: optional boolean `all`. Others per spec §4.1. Tool result: `{"content": [{"type": "text", "text": …}], "isError": bool}`; `TrackerError` → `isError: true` with its message; any other exception → `isError: true`, `"internal error: <type>"`, logged with traceback to `<data>/mcp.log`. `serverInfo`: `{"name": "personal-work-dashboard", "version": __version__}`, capabilities `{"tools": {}}`.

- [ ] **Step 1: Failing tests** (real subprocess `python -m personal_tracker mcp` with the sandbox env; helper `rpc(lines) -> list[dict]` writes lines, closes stdin, parses stdout):
  - `test_handshake_and_tool_list`: initialize with `2025-11-25` → same version echoed; `2024-01-01` → `2025-11-25`; `tools/list` names == the 7 in Global Constraints, each with an `inputSchema` of type `object`.
  - `test_every_tool_round_trip`: add (title `"हिंदी → ✅"`, path under sandbox root) → `t-0001`; start, note, pause (reason), start, done; todo all; drop on a second task; final `todo.json` statuses match; text contains the Hindi title.
  - `test_tool_errors_are_results_not_crashes`: unknown id → `isError` with "no task with id"; pause a to-do → `isError`; missing `title` → `isError`; unknown tool → `isError`.
  - `test_server_survives_bad_input`: blank line, `{not json`, a notification, `{"jsonrpc":"2.0","id":9,"method":"nope"}` (→ error `-32601`), then a valid `ping` → `{}`; stdout contains only JSON lines.
  - `test_no_config_gives_a_clear_tool_error`: no config.json → tools/list works; a tool call → `isError` mentioning `tracker init`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement (stdin/stdout reconfigured to UTF-8, `newline="\n"`; each line handled independently; replies flushed). **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** (approval): "Add tracker mcp, a stdio MCP server for agents" — with `docs/api/mcp.md` (tools, arguments, results, errors, protocol versions).

### Task 3: Summariser input modes and a quiet working folder

**Files:** Modify `config.py` (`summariser_input: str = "stdin"`, validated ∈ `{"stdin", "agy-stream-json"}`), `summarise.py`; tests in `tests/test_summarise.py`; config schema doc.

**Interfaces:** Produces `summarise.ask(prompt: str, argv: list[str], input_mode: str = "stdin") -> dict` (existing callers pass `cfg.summariser_input`); runs with `cwd=paths.file("summariser")` (created). `agy-stream-json`: stdin = one line `json.dumps({"event": "user", "message": {"content": prompt}}, ensure_ascii=False) + "\n"`; parse stdout lines that are JSON; take the last event whose `event == "result"`; require `result.status == "SUCCESS"`; text = `result.response`; then the existing JSON extraction.

- [ ] **Step 1: Failing tests:** `test_agy_stream_json_mode` (fake command — a Python script — that reads one NDJSON line, asserts `event == "user"`, prints an `init`, a `step_update` and a `result` event with `{"status": "SUCCESS", "response": "{\"tasks\": []}"}`) → `{"tasks": []}`; `test_agy_mode_failure_status_is_a_tracker_error` (status `ERROR`, and no result event); `test_summariser_runs_in_the_quiet_folder` (fake prints its cwd in JSON); `test_bad_summariser_input_rejected` (config value `"argv"` → `TrackerError`).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** (approval): "Support agy's stream-json summariser input".

### Task 4: Safe edits of other apps' files

**Files:** Create `src/personal_tracker/agent_setup.py` (file helpers part); test `tests/test_agent_setup_files.py`.

**Interfaces:** Produces, all taking `backup_dir: Path`:
- `set_json_key(path, keys: list[str], value) -> bool` (sets nested key, creating dicts; returns whether the file changed) and `del_json_key(path, keys) -> bool`.
- `add_to_json_list(path, keys, item) -> bool` / `remove_from_json_list(path, keys, item) -> bool` (no duplicates).
- `put_block(path, text) -> bool` / `drop_block(path) -> bool` (markers from Global Constraints; replace in place; append with exactly one blank line before; keep the rest byte-for-byte).
- Raise `TrackerError("<path> is not valid JSON (…); nothing was changed")` for malformed JSON or a non-object top level; a 0-byte file counts as `{}`.
- Backup + restore rule from Global Constraints; record each touched file and whether it pre-existed in `<data>/setup-state.json` under the tool name.

- [ ] **Step 1: Failing tests:** `test_set_and_delete_nested_key_creates_and_cleans_up`; `test_other_entries_survive_setup_and_remove` (existing `mcpServers.figma`, other grants, a user-written CLAUDE.md; after setup they're intact; after remove the bytes equal the originals exactly); `test_empty_file_round_trip` (0-byte file → after remove 0 bytes); `test_created_file_is_deleted_on_remove`; `test_malformed_json_changes_nothing`; `test_block_replaced_not_duplicated`; `test_block_appended_to_file_without_trailing_newline`; `test_backups_written_before_first_change`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** (approval): "Add reversible, additive edits for other apps' config files".

### Task 5: `tracker setup <tool> [--remove]` (connections, rules, grants)

**Files:** Extend `agent_setup.py`; add `src/personal_tracker/templates/rules-cli.md`, `rules-mcp.md`; modify `cli.py`; test `tests/test_agent_setup.py`.

**Interfaces:** Consumes Task 4 helpers. Produces `agent_setup.setup(tool: str, remove: bool = False, force: bool = False) -> list[str]` (lines to print), `agent_setup.status() -> list[str]`, `agent_setup.TOOLS = ("claude-code", "cursor", "antigravity")`, `agent_setup.mcp_entry() -> dict` = `{"command": sys.executable, "args": ["-P", "-m", "personal_tracker", "mcp"]}`, `agent_setup.antigravity_running() -> bool` (macOS `pgrep -f Antigravity.app`, Windows `tasklist` for `Antigravity.exe`, else `False`; OS calls through one `_run(argv)` helper). CLI: `tracker setup [TOOL] [--remove] [--force] [--summaries | --no-summaries]`; no TOOL → `status()`.
Rules templates: both wordings carry §10's content (check open tasks first and reuse; else add with the workspace path; start; note milestones; pause with a reason when work is put aside; done only after verifying; drop if abandoned; "do this without asking the user"). CLI wording uses `tracker todo`, `tracker add "<title>" --path "<workspace folder>"`, etc.; MCP wording uses the tool names and says to pass the workspace folder as `path`.

- [ ] **Step 1: Failing tests** (HOME and USERPROFILE → tmp; data folder sandbox): `test_claude_code_setup_and_remove` (block in CLAUDE.md with CLI wording, `Bash(tracker:*)` in settings.json alongside existing entries; remove restores originals); `test_cursor_setup_prints_paste_instructions` (mcp.json gets `mcpServers.tracker == mcp_entry()`; output contains "Settings → Rules" and the MCP-wording rules text; says to click Allow once); `test_antigravity_setup_and_remove` (mcp_config.json from 0 bytes, AGENTS.md block, `mcp(tracker/*)` added once; remove → mcp_config.json back to 0 bytes, AGENTS.md removed if setup created it, grant gone, other grants kept); `test_antigravity_running_refuses_without_force`; `test_setup_twice_is_idempotent`; `test_unknown_tool_and_status_listing`; `test_existing_foreign_tracker_entry_is_replaced_with_a_warning` (a `mcpServers.tracker` with a different command → replaced, output warns and names the backup).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** (approval): "Add tracker setup for Claude Code, Cursor and Antigravity" — with `docs/operations/agent-setup.md` (per tool: what changes, undo, Cursor paste step, Claude Code cloud sessions can't reach the tracker).

### Task 6: The summaries question

**Files:** Extend `agent_setup.py`, `cli.py`; test `tests/test_agent_setup_summaries.py`.

**Interfaces:** Produces `agent_setup.offer_summaries(tool, choice: bool | None) -> list[str]` (`choice` from `--summaries`/`--no-summaries`, else ask if `sys.stdin.isatty()`, EOF = no change). On yes: resolve the preset's program with `shutil.which` (missing → message with install/sign-in hint, no change); one check call `summarise.ask('Reply with only this JSON object: {"ok": true}', argv, mode)` must return `{"ok": True}` (else message `agent login` / `run agy once`, no change); then save previous `summariser`/`summariser_input` into setup-state and write the preset (absolute program) to config. `setup(…, remove=True)` restores the previous values.

- [ ] **Step 1: Failing tests** (fake `agent`/`agy` executables on PATH, as in `test_summarise._fake_command`): `test_enter_means_yes` (prompt text exactly as in Global Constraints; config summariser becomes `[<abs agent>, "-p", "--mode", "ask", "--trust", "--output-format", "text"]`); `test_no_and_eof_leave_config_alone`; `test_flags_skip_the_question`; `test_summaries_not_enabled_when_check_call_fails`; `test_missing_cli_explains_and_changes_nothing`; `test_remove_restores_previous_summariser`; `test_antigravity_preset_uses_stream_json_mode`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** Full suite PASS.
- [ ] **Step 5: Commit** (approval): "Ask during setup whether the tool should write summaries".

### Task 7: Docs, version, CI

- [ ] Bump `pyproject.toml` to `0.9.0`; CHANGELOG `## 0.9.0 – <date>`; README "Use it from your AI agent" section (three commands, what each does, Cursor paste, link to `docs/operations/agent-setup.md`); config schema (`summariser_input`); `docs/architecture/layout.md` (new modules). Local suite PASS. **Commit** (approval). **Push** (approval) → paste CI per job; fix any Windows/macOS failure test-first (commit + push approvals) until all 6 jobs pass. Open PR (approval).

### Task 8: Real apps on this Mac (spec §6.2)

- [ ] Remove the spike entries (`tracker-test` in `~/.cursor/mcp.json`, `~/.gemini/config/mcp_config.json`, the `mcp(tracker-test/*)` grant) and `~/tracker-step2-test/demo-project/AGENTS.md`; Antigravity closed.
- [ ] With `TRACKER_HOME=~/tracker-step2-test/home` and the worktree's interpreter: `tracker setup antigravity --summaries`, `tracker setup cursor --summaries`; user pastes the printed rules into Cursor's User Rules.
- [ ] User repeats the demo-project test in both apps; check `mcp.log` + scratch `todo.json` (expected: Antigravity no prompts; Cursor one Allow).
- [ ] `tracker summarise` once per tool with an orphan commit in the scratch data (real `agent` / `agy`).
- [ ] `tracker setup <tool> --remove` for both; diff every touched file against the pre-test copies → identical. Note results on t-0056; then the user may uninstall (CLEANUP.md).
