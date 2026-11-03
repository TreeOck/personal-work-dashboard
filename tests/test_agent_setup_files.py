import json
import os

import pytest

from personal_tracker import agent_setup as a
from personal_tracker.errors import TrackerError

BEGIN, END = "<!-- personal-work-dashboard:begin (managed by tracker setup) -->", "<!-- personal-work-dashboard:end -->"


@pytest.fixture
def bdir():
    return a.new_backup_dir("cursor")


def _state():
    return json.loads((a.paths.file("setup-state.json")).read_text(encoding="utf-8"))


def test_set_and_delete_nested_key_creates_and_cleans_up(tmp_path, bdir):
    f = tmp_path / "sub" / "mcp.json"
    assert a.set_json_key(f, ["mcpServers", "tracker"], {"command": "py"}, bdir) is True
    assert json.loads(f.read_text(encoding="utf-8")) == {"mcpServers": {"tracker": {"command": "py"}}}
    assert a.set_json_key(f, ["mcpServers", "tracker"], {"command": "py"}, bdir) is False   # unchanged
    assert _state()["cursor"]["files"][str(f)]["existed"] is False
    assert a.del_json_key(f, ["mcpServers", "tracker"], bdir) is True
    assert json.loads(f.read_text(encoding="utf-8")) == {}   # empty parents pruned
    assert a.del_json_key(f, ["mcpServers", "tracker"], bdir) is False
    a.finish_remove("cursor")
    assert not f.exists()


def test_other_entries_survive_setup_and_remove(tmp_path, bdir):
    mcp = tmp_path / "mcp.json"
    mcp_orig = b'{\n    "mcpServers": {"figma": {"url": "https://x"}},\n    "z": [1, 2]\n}'
    mcp.write_bytes(mcp_orig)
    cfg = tmp_path / "config.json"
    cfg_orig = '{"userSettings": {"globalPermissionGrants": {"allow": ["mcp(figma/*)"]}, "theme": "dark"}}'.encode()
    cfg.write_bytes(cfg_orig)
    rules = tmp_path / "CLAUDE.md"
    rules_orig = "# Mine\n\nदस्तावेज़ rules\n".encode("utf-8")
    rules.write_bytes(rules_orig)

    a.set_json_key(mcp, ["mcpServers", "tracker"], {"command": "py"}, bdir)
    a.add_to_json_list(cfg, ["userSettings", "globalPermissionGrants", "allow"], "mcp(tracker/*)", bdir)
    a.put_block(rules, "be good", bdir)
    m = json.loads(mcp.read_text(encoding="utf-8"))
    assert list(m) == ["mcpServers", "z"] and list(m["mcpServers"]) == ["figma", "tracker"] and m["z"] == [1, 2]
    c = json.loads(cfg.read_text(encoding="utf-8"))
    assert c["userSettings"]["globalPermissionGrants"]["allow"] == ["mcp(figma/*)", "mcp(tracker/*)"]
    assert c["userSettings"]["theme"] == "dark"
    assert rules.read_bytes().startswith(rules_orig)

    assert a.del_json_key(mcp, ["mcpServers", "tracker"], bdir)
    assert a.remove_from_json_list(cfg, ["userSettings", "globalPermissionGrants", "allow"], "mcp(tracker/*)", bdir)
    assert a.drop_block(rules, bdir)
    a.finish_remove("cursor")
    assert mcp.read_bytes() == mcp_orig and cfg.read_bytes() == cfg_orig and rules.read_bytes() == rules_orig
    assert "cursor" not in _state()


def test_remove_keeps_changes_made_by_someone_else_after_setup(tmp_path, bdir):
    f = tmp_path / "mcp.json"
    f.write_text('{"mcpServers": {}}', encoding="utf-8")
    a.set_json_key(f, ["mcpServers", "tracker"], {"command": "py"}, bdir)
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["mcpServers"]["other"] = {"command": "x"}   # the user added a server meanwhile
    f.write_text(json.dumps(doc), encoding="utf-8")
    a.del_json_key(f, ["mcpServers", "tracker"], bdir)
    a.finish_remove("cursor")
    assert json.loads(f.read_text(encoding="utf-8")) == {"mcpServers": {"other": {"command": "x"}}}


def test_empty_file_round_trip(tmp_path, bdir):
    f = tmp_path / "mcp_config.json"
    f.write_bytes(b"")
    a.set_json_key(f, ["mcpServers", "tracker"], {"command": "py"}, bdir)
    assert json.loads(f.read_text(encoding="utf-8"))["mcpServers"]["tracker"] == {"command": "py"}
    a.del_json_key(f, ["mcpServers", "tracker"], bdir)
    a.finish_remove("cursor")
    assert f.exists() and f.read_bytes() == b""


def test_created_file_is_deleted_on_remove(tmp_path, bdir):
    f = tmp_path / "AGENTS.md"
    a.put_block(f, "rules here", bdir)
    assert f.read_text(encoding="utf-8") == "%s\nrules here\n%s\n" % (BEGIN, END)
    a.drop_block(f, bdir)
    a.finish_remove("cursor")
    assert not f.exists()


@pytest.mark.parametrize("content", [b"{not json", b"[1, 2]", b'"text"'])
def test_malformed_json_changes_nothing(tmp_path, bdir, content):
    f = tmp_path / "mcp.json"
    f.write_bytes(content)
    with pytest.raises(TrackerError, match="nothing was changed"):
        a.set_json_key(f, ["mcpServers", "tracker"], {}, bdir)
    with pytest.raises(TrackerError, match="nothing was changed"):
        a.add_to_json_list(f, ["allow"], "x", bdir)
    assert f.read_bytes() == content
    assert not bdir.exists()


def test_wrong_shape_inside_json_changes_nothing(tmp_path, bdir):
    f = tmp_path / "config.json"
    f.write_text('{"userSettings": "oops", "allow": "notalist"}', encoding="utf-8")
    with pytest.raises(TrackerError, match="nothing was changed"):
        a.add_to_json_list(f, ["userSettings", "grants"], "x", bdir)
    with pytest.raises(TrackerError, match="nothing was changed"):
        a.add_to_json_list(f, ["allow"], "x", bdir)


def test_block_replaced_not_duplicated(tmp_path, bdir):
    f = tmp_path / "CLAUDE.md"
    f.write_text("top\n\n%s\nold, edited by hand\n%s\n\nbottom\n" % (BEGIN, END), encoding="utf-8")
    assert a.put_block(f, "new", bdir) is True
    assert f.read_text(encoding="utf-8") == "top\n\n%s\nnew\n%s\n\nbottom\n" % (BEGIN, END)
    assert a.put_block(f, "new", bdir) is False


def test_block_appended_to_file_without_trailing_newline(tmp_path, bdir):
    f = tmp_path / "CLAUDE.md"
    f.write_bytes(b"line one")
    a.put_block(f, "r", bdir)
    assert f.read_text(encoding="utf-8") == "line one\n\n%s\nr\n%s\n" % (BEGIN, END)
    a.drop_block(f, bdir)
    a.finish_remove("cursor")
    assert f.read_bytes() == b"line one"


def test_backups_written_before_first_change(tmp_path, bdir):
    f = tmp_path / "mcp.json"
    f.write_bytes(b'{"a": 1}')
    a.set_json_key(f, ["b"], 2, bdir)
    a.set_json_key(f, ["c"], 3, bdir)   # second change in the same run keeps the first backup
    assert (bdir / "mcp.json").read_bytes() == b'{"a": 1}'
    assert _state()["cursor"]["files"][str(f)] == {"existed": True, "backup": str(bdir / "mcp.json")}
    later = a.new_backup_dir("cursor")
    a.set_json_key(f, ["d"], 4, later)   # a later setup run doesn't replace the record of the original
    assert _state()["cursor"]["files"][str(f)]["backup"] == str(bdir / "mcp.json")


def test_finish_remove_skips_files_deleted_since(tmp_path, bdir):
    f = tmp_path / "mcp.json"
    f.write_text("{}", encoding="utf-8")
    a.set_json_key(f, ["x"], 1, bdir)
    os.remove(f)
    a.finish_remove("cursor")
    assert not f.exists() and "cursor" not in _state()
