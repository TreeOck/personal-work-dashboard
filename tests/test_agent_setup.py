import json
import subprocess
import sys

import pytest

from personal_tracker import agent_setup as a
from personal_tracker.errors import TrackerError


@pytest.fixture
def home(tmp_path, monkeypatch, sandbox):
    """A fake user home (HOME / USERPROFILE) and the sandbox data folder; Antigravity is not running."""
    h = tmp_path / "user"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    monkeypatch.setattr(a, "_run", lambda argv: (1, ""))
    return h


def _j(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_claude_code_setup_and_remove(home):
    md = home / ".claude" / "CLAUDE.md"
    settings = home / ".claude" / "settings.json"
    md.parent.mkdir()
    md_orig = b"# My rules\n\nAlways test.\n"
    md.write_bytes(md_orig)
    settings_orig = b'{"permissions": {"allow": ["Bash(kubectl get:*)"]}, "model": "sonnet"}'
    settings.write_bytes(settings_orig)
    out = "\n".join(a.setup("claude-code"))
    text = md.read_text(encoding="utf-8")
    assert text.startswith("# My rules\n\nAlways test.\n\n" + a.BEGIN)
    assert 'tracker add "<short imperative title>" --path' in text and "tracker_add" not in text
    assert _j(settings)["permissions"]["allow"] == ["Bash(kubectl get:*)", "Bash(tracker:*)"]
    assert "CLAUDE.md" in out
    a.setup("claude-code", remove=True)
    assert md.read_bytes() == md_orig and settings.read_bytes() == settings_orig


def test_claude_code_not_installed_still_writes_rules_and_says_so(home, monkeypatch):
    monkeypatch.setattr(a.shutil, "which", lambda name: None)
    out = "\n".join(a.setup("claude-code"))
    assert (home / ".claude" / "CLAUDE.md").exists() and "Claude Code wasn't found" in out


def test_cursor_setup_prints_paste_instructions(home):
    out = "\n".join(a.setup("cursor"))
    assert _j(home / ".cursor" / "mcp.json") == {"mcpServers": {"tracker": a.mcp_entry()}}
    assert {k: a.mcp_entry()[k] for k in ("command", "args")} == {"command": sys.executable, "args": ["-P", "-m", "personal_tracker", "mcp"]}
    assert "Customize → Rules" in out
    assert "tracker_add" in out and "path" in out
    assert "click Run" in out
    a.setup("cursor", remove=True)
    assert not (home / ".cursor" / "mcp.json").exists()


def test_antigravity_setup_and_remove(home):
    cfgdir = home / ".gemini" / "config"
    cfgdir.mkdir(parents=True)
    (cfgdir / "mcp_config.json").write_bytes(b"")
    grants_orig = b'{"userSettings": {"globalPermissionGrants": {"allow": ["mcp(figma/*)"]}, "x": 1}}'
    (cfgdir / "config.json").write_bytes(grants_orig)
    out = "\n".join(a.setup("antigravity"))
    assert _j(cfgdir / "mcp_config.json") == {"mcpServers": {"tracker": a.mcp_entry()}}
    assert _j(cfgdir / "config.json")["userSettings"]["globalPermissionGrants"]["allow"] == ["mcp(figma/*)", "mcp(tracker/*)"]
    agents = (home / ".gemini" / "AGENTS.md").read_text(encoding="utf-8")
    assert "tracker_todo" in agents and a.BEGIN in agents
    assert "AGENTS.md" in out
    a.setup("antigravity")   # twice: the grant is still there once
    assert _j(cfgdir / "config.json")["userSettings"]["globalPermissionGrants"]["allow"].count("mcp(tracker/*)") == 1
    a.setup("antigravity", remove=True)
    assert (cfgdir / "mcp_config.json").read_bytes() == b""
    assert not (home / ".gemini" / "AGENTS.md").exists()
    assert (cfgdir / "config.json").read_bytes() == grants_orig


def test_antigravity_running_refuses_without_force(home, monkeypatch):
    monkeypatch.setattr(a, "_run", lambda argv: (0, "123 /Applications/Antigravity.app/Contents/MacOS/Electron\n"))
    monkeypatch.setattr(a.sys, "platform", "darwin")
    assert a.antigravity_running()
    with pytest.raises(TrackerError, match="quit Antigravity"):
        a.setup("antigravity")
    assert not (home / ".gemini").exists()
    a.setup("antigravity", force=True)
    assert (home / ".gemini" / "config" / "mcp_config.json").exists()


def test_antigravity_running_check_per_os(monkeypatch):
    calls = []
    monkeypatch.setattr(a, "_run", lambda argv: calls.append(argv) or (0, "Antigravity.exe   4242 Console\n"))
    monkeypatch.setattr(a.sys, "platform", "win32")
    assert a.antigravity_running() and calls[-1][0] == "tasklist"
    monkeypatch.setattr(a, "_run", lambda argv: (0, "INFO: No tasks are running which match the specified criteria.\n"))
    assert not a.antigravity_running()
    monkeypatch.setattr(a.sys, "platform", "linux")
    assert not a.antigravity_running()


def test_setup_twice_is_idempotent(home):
    a.setup("claude-code")
    a.setup("cursor")
    first = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
    a.setup("claude-code")
    a.setup("cursor")
    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == first
    assert (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8").count(a.BEGIN) == 1


def test_unknown_tool_and_status_listing(home):
    with pytest.raises(TrackerError, match="claude-code, cursor, antigravity"):
        a.setup("vscode")
    assert a.setup("cursor", remove=True) == ["cursor: nothing to remove"]
    a.setup("cursor")
    st = "\n".join(a.status())
    assert "cursor: set up" in st and "claude-code: not set up" in st and "antigravity: not set up" in st


def test_existing_foreign_tracker_entry_is_replaced_with_a_warning(home):
    f = home / ".cursor" / "mcp.json"
    f.parent.mkdir()
    f.write_text('{"mcpServers": {"tracker": {"command": "/old/python", "args": []}}}', encoding="utf-8")
    out = "\n".join(a.setup("cursor"))
    assert _j(f)["mcpServers"]["tracker"] == a.mcp_entry()
    assert "warning" in out and "/old/python" in out and "setup-backups" in out


def test_malformed_target_changes_nothing_at_all(home):
    cfgdir = home / ".gemini" / "config"
    cfgdir.mkdir(parents=True)
    (cfgdir / "config.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(TrackerError, match="nothing was changed"):
        a.setup("antigravity")
    assert not (cfgdir / "mcp_config.json").exists() and not (home / ".gemini" / "AGENTS.md").exists()


def test_cli_setup(sandbox, tmp_path):
    h = tmp_path / "cli-user"
    h.mkdir()
    env = dict(sandbox.env, HOME=str(h), USERPROFILE=str(h))
    run = lambda *args: subprocess.run([sys.executable, "-m", "personal_tracker", *args], env=env, capture_output=True,
                                       text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    r = run("setup", "cursor", "--no-summaries")
    assert r.returncode == 0, r.stderr
    assert (h / ".cursor" / "mcp.json").exists()
    assert "cursor: set up" in run("setup").stdout
    assert run("setup", "cursor", "--remove").returncode == 0 and not (h / ".cursor" / "mcp.json").exists()
