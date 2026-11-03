"""`tracker setup <tool>`: connect Claude Code, Cursor or Antigravity to the tracker by editing their own files.

Every edit is additive and reversible: setup only adds or replaces its own key, list entry or marked block, keeps a
copy of each file before its first change (<data>/setup-backups/<time>/<tool>/), and records what it touched in
<data>/setup-state.json so `--remove` can put things back. See docs/operations/agent-setup.md."""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from importlib import resources
from pathlib import Path

from . import files, paths, procs, setup as init_setup, summarise
from .errors import TrackerError

BEGIN = "<!-- personal-work-dashboard:begin (managed by tracker setup) -->"
END = "<!-- personal-work-dashboard:end -->"


# ---- setup-state.json and backups ---------------------------------------------------------------------------------

def _state_path():
    return paths.file("setup-state.json")


def load_state():
    return files.read_json(_state_path(), {}) or {}


def save_state(state):
    paths.home().mkdir(parents=True, exist_ok=True)
    files.write_json(_state_path(), state, indent=2)


def new_backup_dir(tool):
    """Where this run keeps its copies; the folder's name is the tool, which is how the helpers know whose edit it is."""
    return paths.file("setup-backups") / datetime.now().strftime("%Y%m%d-%H%M%S") / tool


def _before_change(path, backup_dir):
    """Copy the file into this run's backups before its first change, and remember the very first copy in the state."""
    path = Path(path)
    backup = backup_dir / path.name
    existed = path.exists()
    if existed and not backup.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, backup)
    state = load_state()
    recorded = state.setdefault(backup_dir.name, {}).setdefault("files", {})
    if str(path) not in recorded:
        recorded[str(path)] = {"existed": existed, "backup": str(backup) if existed else None}
        save_state(state)


def _write(path, text, backup_dir):
    path = Path(path)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    _before_change(path, backup_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    files.write_text(path, text)
    return True


# ---- JSON files ---------------------------------------------------------------------------------------------------

def _parse(text, path):
    """A JSON object from the file's text; an empty file counts as {}."""
    if not text.strip():
        return {}
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise TrackerError("%s is not valid JSON (%s); nothing was changed" % (path, e)) from e
    if not isinstance(doc, dict):
        raise TrackerError("%s is not valid JSON for this (top level is a %s, not an object); nothing was changed"
                           % (path, type(doc).__name__))
    return doc


def _read_json(path):
    path = Path(path)
    return _parse(path.read_text(encoding="utf-8") if path.exists() else "", path)


def _dump(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _parent(doc, keys, path, create):
    """The dict holding keys[-1], creating missing dicts on the way when `create`; None when it isn't there."""
    node = doc
    for k in keys[:-1]:
        if k not in node:
            if not create:
                return None
            node[k] = {}
        node = node[k]
        if not isinstance(node, dict):
            raise TrackerError("%s: %s is not an object; nothing was changed" % (path, ".".join(keys[:keys.index(k) + 1])))
    return node


def _prune(doc, keys):
    """Drop the dicts along `keys` that are empty now, deepest first."""
    for depth in range(len(keys) - 1, 0, -1):
        node = doc
        for k in keys[:depth - 1]:
            node = node[k]
        if node.get(keys[depth - 1]) == {}:
            del node[keys[depth - 1]]


def _pruned(obj):
    """obj without empty objects anywhere (for 'is what's left the same as before setup?')."""
    if isinstance(obj, dict):
        out = {k: _pruned(v) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v != {}}
    return obj


def set_json_key(path, keys, value, backup_dir):
    doc = _read_json(path)
    parent = _parent(doc, keys, path, True)
    if keys[-1] in parent and parent[keys[-1]] == value:
        return False   # already there: don't even reformat the file
    parent[keys[-1]] = value
    return _write(path, _dump(doc), backup_dir)


def del_json_key(path, keys, backup_dir):
    if not Path(path).exists():
        return False
    doc = _read_json(path)
    parent = _parent(doc, keys, path, False)
    if parent is None or keys[-1] not in parent:
        return False
    del parent[keys[-1]]
    _prune(doc, keys)
    return _write(path, _dump(doc), backup_dir)


def add_to_json_list(path, keys, item, backup_dir):
    doc = _read_json(path)
    parent = _parent(doc, keys, path, True)
    lst = parent.setdefault(keys[-1], [])
    if not isinstance(lst, list):
        raise TrackerError("%s: %s is not a list; nothing was changed" % (path, ".".join(keys)))
    if item in lst:
        return False
    lst.append(item)
    return _write(path, _dump(doc), backup_dir)


def remove_from_json_list(path, keys, item, backup_dir):
    if not Path(path).exists():
        return False
    doc = _read_json(path)
    parent = _parent(doc, keys, path, False)
    lst = parent.get(keys[-1]) if parent is not None else None
    if not isinstance(lst, list) or item not in lst:
        return False
    lst[:] = [x for x in lst if x != item]
    if not lst:
        del parent[keys[-1]]
        _prune(doc, keys)
    return _write(path, _dump(doc), backup_dir)


# ---- marked text blocks -------------------------------------------------------------------------------------------

def _block(text):
    return "%s\n%s\n%s" % (BEGIN, text.strip("\n"), END)


def _span(content):
    start = content.find(BEGIN)
    if start < 0:
        return None
    end = content.find(END, start)
    return (start, end + len(END)) if end >= 0 else None


def put_block(path, text, backup_dir):
    """Our block replaces the old one in place, or is appended after one blank line."""
    path = Path(path)
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    span = _span(content)
    if span:
        new = content[:span[0]] + _block(text) + content[span[1]:]
    elif content.strip():
        new = content.rstrip("\n") + "\n\n" + _block(text) + "\n"
    else:
        new = _block(text) + "\n"
    return _write(path, new, backup_dir)


def drop_block(path, backup_dir):
    path = Path(path)
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    span = _span(content)
    if not span:
        return False
    before, after = content[:span[0]], content[span[1]:]
    after = after[1:] if after.startswith("\n") else after
    if after.strip():
        new = before.rstrip("\n") + "\n\n" + after.lstrip("\n") if before.strip() else after.lstrip("\n")
    else:
        new = before.rstrip("\n") + "\n" if before.strip() else ""
    return _write(path, new, backup_dir)


# ---- after --remove -----------------------------------------------------------------------------------------------

def _same_as_backup(path, current, backup_text):
    if path.suffix == ".json":
        try:
            return _pruned(_parse(current, path)) == _pruned(_parse(backup_text, path))
        except TrackerError:
            return False
    return current.rstrip() == backup_text.rstrip()


def finish_remove(tool):
    """After our entries are gone: a file that is now what it was before setup gets its original bytes back; a file
    setup created and that holds nothing else is deleted. Returns lines to print."""
    state = load_state()
    out = []
    for name, rec in state.get(tool, {}).get("files", {}).items():
        path = Path(name)
        if not path.exists():
            continue
        current = path.read_text(encoding="utf-8")
        if not rec["existed"]:
            empty = not current.strip() or path.suffix == ".json" and _pruned(_parse(current, path)) == {}
            if empty:
                path.unlink()
                out.append("deleted %s (setup had created it)" % path)
            continue
        backup = Path(rec["backup"])
        if backup.exists():
            original = backup.read_bytes()
            if _same_as_backup(path, current, original.decode("utf-8")):
                if current.encode("utf-8") != original:
                    files.write_text(path, original.decode("utf-8"))
                out.append("restored %s" % path)
                continue
        out.append("removed our entries from %s (other changes made since setup are kept)" % path)
    state.pop(tool, None)
    save_state(state)
    return out


# ---- the three tools ----------------------------------------------------------------------------------------------

TOOLS = ("claude-code", "cursor", "antigravity")
SERVER = "tracker"
CLAUDE_GRANT = "Bash(tracker:*)"
ANTIGRAVITY_GRANT = "mcp(tracker/*)"
GRANTS_KEYS = ["userSettings", "globalPermissionGrants", "allow"]


def _paths():
    h = Path.home()
    return {"claude_md": h / ".claude" / "CLAUDE.md", "claude_settings": h / ".claude" / "settings.json",
            "cursor_mcp": h / ".cursor" / "mcp.json",
            "ag_mcp": h / ".gemini" / "config" / "mcp_config.json", "ag_config": h / ".gemini" / "config" / "config.json",
            "ag_rules": h / ".gemini" / "AGENTS.md"}


def mcp_entry():
    """How an app starts the server: this interpreter by absolute path (GUI apps don't get the shell's PATH);
    -P so the app's working folder can't shadow the package."""
    return {"command": sys.executable, "args": ["-P", "-m", "personal_tracker", "mcp"]}


def rules(wording):
    """The rules text: wording "cli" (tracker commands) or "mcp" (tool names)."""
    return resources.files("personal_tracker").joinpath("templates/rules-%s.md" % wording).read_text(encoding="utf-8")


def _run(argv):
    """(returncode, stdout) of a quick OS command; (1, "") when it can't run."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                           **procs.no_window())
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return r.returncode, r.stdout


def antigravity_running():
    if sys.platform == "darwin":
        return _run(["pgrep", "-f", "Antigravity.app"])[0] == 0
    if sys.platform == "win32":
        return "antigravity.exe" in _run(["tasklist", "/FI", "IMAGENAME eq Antigravity.exe", "/NH"])[1].lower()
    return False


def _server_entry(path):
    return _read_json(path).get("mcpServers", {}).get(SERVER) if path.exists() else None


def _connect(path, bdir, out):
    old = _server_entry(path)
    if old is not None and old != mcp_entry():
        out.append("warning: replaced an existing \"%s\" server in %s: %s (a copy of the file is in %s)"
                   % (SERVER, path, json.dumps(old, ensure_ascii=False), bdir / path.name))
    if set_json_key(path, ["mcpServers", SERVER], mcp_entry(), bdir):
        out.append("connected the tracker in %s" % path)


def _check_json(*targets):
    for path in targets:
        _read_json(path)   # malformed or not an object: stop before anything is written


def setup(tool, remove=False, force=False):
    """Set up (or with remove=True undo) one tool. Returns lines to print."""
    if tool not in TOOLS:
        raise TrackerError("unknown tool %s; choose one of: %s" % (tool, ", ".join(TOOLS)))
    if tool == "antigravity" and not force and antigravity_running():
        raise TrackerError("Antigravity is open and may overwrite its settings while running: quit Antigravity "
                           "(all windows) and run this again, or pass --force")
    p, bdir, out = _paths(), new_backup_dir(tool), []
    if remove:
        if tool not in load_state():
            return ["%s: nothing to remove" % tool]
        if tool == "claude-code":
            drop_block(p["claude_md"], bdir)
            remove_from_json_list(p["claude_settings"], ["permissions", "allow"], CLAUDE_GRANT, bdir)
        elif tool == "cursor":
            del_json_key(p["cursor_mcp"], ["mcpServers", SERVER], bdir)
        else:
            del_json_key(p["ag_mcp"], ["mcpServers", SERVER], bdir)
            remove_from_json_list(p["ag_config"], GRANTS_KEYS, ANTIGRAVITY_GRANT, bdir)
            drop_block(p["ag_rules"], bdir)
        return _restore_summariser(tool) + finish_remove(tool) + ["%s: removed" % tool]

    if tool == "claude-code":
        _check_json(p["claude_settings"])
        if put_block(p["claude_md"], rules("cli"), bdir):
            out.append("wrote the tracker rules into %s" % p["claude_md"])
        if add_to_json_list(p["claude_settings"], ["permissions", "allow"], CLAUDE_GRANT, bdir):
            out.append("allowed the tracker command without prompts (%s in %s)" % (CLAUDE_GRANT, p["claude_settings"]))
        if shutil.which("claude") is None:
            out.append("note: Claude Code wasn't found on this computer; the rules were written anyway and take effect once it is installed")
        out.append("Claude Code in the terminal, the IDE extensions and the desktop app's local sessions use these. "
                   "Cloud sessions run elsewhere and can't reach this computer's tracker.")
    elif tool == "cursor":
        _check_json(p["cursor_mcp"])
        _connect(p["cursor_mcp"], bdir, out)
        out += ["", "One step left (Cursor keeps its global rules in its settings, not in a file):",
                "open Cursor → Settings → Rules → User Rules, and paste this text:", "",
                rules("mcp").rstrip("\n"), "",
                "The first time an agent uses the tracker, Cursor asks once: click Allow (it remembers)."]
    else:
        _check_json(p["ag_mcp"], p["ag_config"])
        _connect(p["ag_mcp"], bdir, out)
        if add_to_json_list(p["ag_config"], GRANTS_KEYS, ANTIGRAVITY_GRANT, bdir):
            out.append("allowed the tracker tools without prompts (%s in %s)" % (ANTIGRAVITY_GRANT, p["ag_config"]))
        if put_block(p["ag_rules"], rules("mcp"), bdir):
            out.append("wrote the tracker rules into %s" % p["ag_rules"])
    if not out:
        out.append("%s: already set up, nothing changed" % tool)
    return ["%s: set up" % tool] + out + ["Undo with: tracker setup %s --remove" % tool]


def _is_set_up(tool):
    p = _paths()
    try:
        if tool == "claude-code":
            return p["claude_md"].exists() and _span(p["claude_md"].read_text(encoding="utf-8")) is not None
        return _server_entry(p["cursor_mcp"] if tool == "cursor" else p["ag_mcp"]) is not None
    except TrackerError:
        return False


def status():
    lines = ["%s: %s" % (t, "set up" if _is_set_up(t) else "not set up") for t in TOOLS]
    return lines + ["", "Set one up with: tracker setup <%s>   (undo: --remove)" % "|".join(TOOLS)]


# ---- summaries ----------------------------------------------------------------------------------------------------

NAMES = {"claude-code": "Claude Code", "cursor": "Cursor", "antigravity": "Antigravity"}
SUMMARISERS = {   # tool -> (argv, summariser_input)
    "claude-code": (init_setup.CLAUDE_SUMMARISER, "stdin"),
    "cursor": (["agent", "-p", "--mode", "ask", "--trust", "--output-format", "text"], "stdin"),
    "antigravity": (["agy", "--input-format", "stream-json", "--output-format", "stream-json", "--print-timeout", "600s"],
                    "agy-stream-json"),
}
SIGN_IN = {"claude-code": "run claude once in a terminal and sign in",
           "cursor": "sign in with: agent login",
           "antigravity": "run agy once in a terminal and sign in"}
CHECK_PROMPT = 'Reply with only this JSON object: {"ok": true}'


def _want_summaries(tool, choice):
    if choice is not None:
        return choice
    if not sys.stdin.isatty():
        return False   # scripts and agents: leave summaries as they are
    name = NAMES[tool]
    try:
        ans = input("Use %s to write your daily summaries? It uses your %s account's quota. [Y/n] " % (name, name))
    except EOFError:
        return False
    return ans.strip().lower() in ("", "y", "yes")


def offer_summaries(tool, choice):
    """Ask (or take --summaries / --no-summaries) whether `tool` should write the daily summaries; on yes, check its
    command works and is signed in, then point config.json at it. Returns lines to print."""
    if not _want_summaries(tool, choice):
        return []
    argv, mode = SUMMARISERS[tool]
    retry = "then run: tracker setup %s --summaries" % tool
    exe = shutil.which(argv[0])
    if exe is None:
        return ["summaries not switched on: the %s command '%s' was not found (install %s's command-line agent, %s)"
                % (NAMES[tool], argv[0], NAMES[tool], retry)]
    cmd = [exe, *argv[1:]]
    try:
        ok = summarise.ask(CHECK_PROMPT, cmd, mode) == {"ok": True}
        problem = "it didn't give the expected answer"
    except TrackerError as e:
        ok, problem = False, str(e)[:300]
    if not ok:
        return ["summaries not switched on: a test request to %s failed (%s)." % (argv[0], problem),
                "If you aren't signed in, %s; %s" % (SIGN_IN[tool], retry)]
    path = paths.file("config.json")
    raw = files.read_json(path)
    state = load_state()
    saved = state.setdefault(tool, {})
    if "summariser" not in saved:   # the value from before the first setup is what --remove puts back
        saved["summariser"] = {"summariser": raw.get("summariser"), "summariser_input": raw.get("summariser_input")}
        save_state(state)
    raw["summariser"], raw["summariser_input"] = cmd, mode
    files.write_json(path, raw)
    return ["daily summaries will be written by %s (%s)" % (NAMES[tool], " ".join(cmd))]


def _restore_summariser(tool):
    saved = load_state().get(tool, {}).get("summariser")
    if saved is None:
        return []
    path = paths.file("config.json")
    raw = files.read_json(path)
    if raw is None:
        return []
    raw["summariser"] = saved["summariser"]
    if saved["summariser_input"] is None:
        raw.pop("summariser_input", None)
    else:
        raw["summariser_input"] = saved["summariser_input"]
    files.write_json(path, raw)
    return ["summaries: put back the summariser from before setup"]
