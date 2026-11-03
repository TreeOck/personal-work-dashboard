"""Regression tests for the final-review findings (reversibility of setup on a colleague's machine)."""
import json
import os
import time

import pytest

from personal_tracker import agent_setup as a
from personal_tracker.errors import TrackerError
from test_agent_setup_summaries import AGENT_OK, AGY_OK, _fake_command


@pytest.fixture
def bindir(tmp_path):
    d = tmp_path / "bin"
    d.mkdir()
    return d


@pytest.fixture
def home(tmp_path, monkeypatch, sandbox, bindir):
    h = tmp_path / "user"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(a, "_run", lambda argv: (1, ""))
    return h


def test_remove_keeps_a_grant_the_user_already_had(home):
    s = home / ".claude" / "settings.json"
    s.parent.mkdir()
    orig = '{\n    "permissions": {\n        "allow": ["Bash(tracker:*)", "Bash(ls:*)"]\n    },\n    "name": "é"\n}\n'.encode()
    s.write_bytes(orig)
    a.setup("claude-code")
    a.setup("claude-code", remove=True)
    assert s.read_bytes() == orig


def test_foreign_tracker_server_is_put_back_on_remove(home):
    f = home / ".gemini" / "config" / "mcp_config.json"
    f.parent.mkdir(parents=True)
    f.write_text('{"mcpServers": {"tracker": {"command": "jira-mcp"}, "other": {"command": "x"}}}', encoding="utf-8")
    a.setup("antigravity")
    a.setup("antigravity")   # a rerun must not forget the original
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["mcpServers"]["new"] = {"command": "y"}   # changed since, so remove can't simply restore the backup
    f.write_text(json.dumps(doc), encoding="utf-8")
    a.setup("antigravity", remove=True)
    assert json.loads(f.read_text(encoding="utf-8"))["mcpServers"] == {"tracker": {"command": "jira-mcp"}, "other": {"command": "x"}, "new": {"command": "y"}}


def test_crlf_rules_file_round_trip(home):
    md = home / ".claude" / "CLAUDE.md"
    md.parent.mkdir()
    orig = b"# Mine\r\nline two\r\n"
    md.write_bytes(orig)
    a.setup("claude-code")
    data = md.read_bytes()
    assert data.startswith(orig) and b"\n" not in data.replace(b"\r\n", b"")
    a.setup("claude-code", remove=True)
    assert md.read_bytes() == orig


def test_json_style_is_kept(home):
    f = home / ".cursor" / "mcp.json"
    f.parent.mkdir()
    f.write_text('{\n    "mcpServers": {\n        "figma": {"url": "caf\\u00e9"}\n    }\n}', encoding="utf-8")
    a.setup("cursor")
    text = f.read_text(encoding="utf-8")
    assert '\n    "mcpServers": {\n        "figma"' in text and "\\u00e9" in text and not text.endswith("\n")


def test_two_tools_summaries_are_independent(home, bindir):
    cfg_path = a.paths.file("config.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["summariser"] = ["claude", "-p"]
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    _fake_command(bindir, "agent", AGENT_OK)
    _fake_command(bindir, "agy", AGY_OK)
    current = lambda: json.loads(cfg_path.read_text(encoding="utf-8"))
    a.setup("cursor"); a.offer_summaries("cursor", True)
    a.setup("antigravity"); a.offer_summaries("antigravity", True)
    a.setup("cursor", remove=True)
    assert current()["summariser_input"] == "agy-stream-json"   # antigravity's is still in use: left alone
    a.setup("antigravity", remove=True)
    assert current()["summariser"] == ["claude", "-p"] and "summariser_input" not in current()


def test_hand_edited_summariser_is_not_overwritten_on_remove(home, bindir):
    _fake_command(bindir, "agent", AGENT_OK)
    a.setup("cursor"); a.offer_summaries("cursor", True)
    cfg_path = a.paths.file("config.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["summariser"] = ["my-own"]
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    out = "\n".join(a.setup("cursor", remove=True))
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["summariser"] == ["my-own"] and "left" in out


def test_shape_error_writes_nothing(home):
    c = home / ".gemini" / "config" / "config.json"
    c.parent.mkdir(parents=True)
    c.write_text('{"userSettings": {"globalPermissionGrants": {"allow": "oops"}}}', encoding="utf-8")
    with pytest.raises(TrackerError, match="nothing was changed"):
        a.setup("antigravity")
    assert sorted(p.name for p in c.parent.iterdir()) == ["config.json"]
    assert not (home / ".gemini" / "AGENTS.md").exists()


def test_non_utf8_rules_file_is_a_clear_error_and_nothing_is_written(home):
    (home / ".gemini").mkdir()
    (home / ".gemini" / "AGENTS.md").write_bytes(b"caf\xe9\n")
    with pytest.raises(TrackerError, match="UTF-8.*nothing was changed"):
        a.setup("antigravity")
    assert not (home / ".gemini" / "config").exists()


def test_begin_marker_without_end_refuses(home):
    md = home / ".claude" / "CLAUDE.md"
    md.parent.mkdir()
    md.write_text("top\n%s\nmine, keep me\n" % a.BEGIN, encoding="utf-8")
    with pytest.raises(TrackerError, match="end marker"):
        a.setup("claude-code")
    assert md.read_text(encoding="utf-8") == "top\n%s\nmine, keep me\n" % a.BEGIN


def test_mcp_entry_carries_the_data_folder(home, monkeypatch):
    assert a.mcp_entry()["env"] == {"TRACKER_HOME": str(a.paths.home().resolve())}
    monkeypatch.delenv("TRACKER_HOME")
    assert "env" not in a.mcp_entry()


def test_sign_in_check_has_a_short_timeout(home, bindir, monkeypatch):
    _fake_command(bindir, "agent", "import time\ntime.sleep(30)\n")
    monkeypatch.setattr(a, "CHECK_TIMEOUT", 1)
    t = time.monotonic()
    out = "\n".join(a.offer_summaries("cursor", True))
    assert time.monotonic() - t < 15 and "not switched on" in out and "timed out" in out
