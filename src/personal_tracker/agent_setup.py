"""`tracker setup <tool>`: connect Claude Code, Cursor or Antigravity to the tracker by editing their own files.

Every edit is additive and reversible: setup only adds or replaces its own key, list entry or marked block, keeps a
copy of each file before its first change (<data>/setup-backups/<time>/<tool>/), and records what it touched in
<data>/setup-state.json so `--remove` can put things back. See docs/operations/agent-setup.md."""
import json
import shutil
from datetime import datetime
from pathlib import Path

from . import files, paths
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
