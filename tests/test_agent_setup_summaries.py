import json
import os

import pytest

from personal_tracker import agent_setup as a
import stat
import sys

PROMPT = "Use Cursor to write your daily summaries? It uses your Cursor account's quota. [Y/n] "
AGENT_OK = "import sys, json\nsys.stdin.read()\nprint(json.dumps({'ok': True}))\n"
AGENT_SIGNED_OUT = "import sys\nsys.stdin.read()\nsys.stderr.write('not logged in')\nsys.exit(1)\n"
AGY_OK = """import sys, json
m = json.loads(sys.stdin.readline())
assert m["event"] == "user", m
print(json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": json.dumps({"ok": True})}}))
"""


def _fake_command(bindir, name, body):
    """An executable `name` on PATH that runs the Python `body` (a .cmd shim on Windows, a sh script elsewhere)."""
    script = bindir / (name + "_impl.py")
    script.write_text(body, encoding="utf-8")
    if sys.platform == "win32":
        path = bindir / (name + ".cmd")
        path.write_text('@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, script), encoding="utf-8")
    else:
        path = bindir / name
        path.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def env(sandbox, tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("TRACKER_HOME", str(sandbox.dir))
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    monkeypatch.setattr(a, "_run", lambda argv: (1, ""))
    env = type("Env", (), {})()
    env.bin = bindir
    env.cfg = lambda: json.loads((sandbox.dir / "config.json").read_text(encoding="utf-8"))
    return env


def _tty(monkeypatch, answer):
    asked = []
    monkeypatch.setattr(a.sys.stdin, "isatty", lambda: True, raising=False)

    def fake_input(prompt):
        asked.append(prompt)
        if answer is EOFError:
            raise EOFError
        return answer
    monkeypatch.setattr("builtins.input", fake_input)
    return asked


def test_enter_means_yes(env, monkeypatch):
    fake = _fake_command(env.bin, "agent", AGENT_OK)
    asked = _tty(monkeypatch, "")
    out = "\n".join(a.offer_summaries("cursor", None))
    assert asked == [PROMPT]
    cfg = env.cfg()
    assert os.path.samefile(cfg["summariser"][0], fake)
    assert cfg["summariser"][1:] == ["-p", "--mode", "ask", "--trust", "--output-format", "text"]
    assert cfg["summariser_input"] == "stdin"
    assert "summaries" in out


@pytest.mark.parametrize("answer", ["n", "No", EOFError])
def test_no_and_eof_leave_config_alone(env, monkeypatch, answer):
    _fake_command(env.bin, "agent", AGENT_OK)
    before = env.cfg()
    _tty(monkeypatch, answer)
    a.offer_summaries("cursor", None)
    assert env.cfg() == before


def test_no_terminal_leaves_config_alone(env, monkeypatch):
    _fake_command(env.bin, "agent", AGENT_OK)
    before = env.cfg()
    monkeypatch.setattr(a.sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr("builtins.input", lambda p: pytest.fail("must not ask"))
    assert a.offer_summaries("cursor", None) == []
    assert env.cfg() == before


def test_flags_skip_the_question(env, monkeypatch):
    _fake_command(env.bin, "agent", AGENT_OK)
    monkeypatch.setattr("builtins.input", lambda p: pytest.fail("must not ask"))
    before = env.cfg()
    assert a.offer_summaries("cursor", False) == []
    assert env.cfg() == before
    a.offer_summaries("cursor", True)
    assert env.cfg()["summariser"][1] == "-p"


def test_summaries_not_enabled_when_check_call_fails(env):
    _fake_command(env.bin, "agent", AGENT_SIGNED_OUT)
    before = env.cfg()
    out = "\n".join(a.offer_summaries("cursor", True))
    assert env.cfg() == before
    assert "agent login" in out and "not switched on" in out


def test_missing_cli_explains_and_changes_nothing(env, monkeypatch):
    monkeypatch.setattr(a.shutil, "which", lambda name: None)
    before = env.cfg()
    out = "\n".join(a.offer_summaries("antigravity", True))
    assert env.cfg() == before
    assert "agy" in out and "not found" in out


def test_remove_restores_previous_summariser(env):
    cfg = env.cfg()
    cfg["summariser"] = ["claude", "-p"]
    (a.paths.file("config.json")).write_text(json.dumps(cfg), encoding="utf-8")
    _fake_command(env.bin, "agent", AGENT_OK)
    a.setup("cursor")
    a.offer_summaries("cursor", True)
    assert env.cfg()["summariser"][1:3] == ["-p", "--mode"]
    a.setup("cursor", remove=True)
    after = env.cfg()
    assert after["summariser"] == ["claude", "-p"] and "summariser_input" not in after


def test_antigravity_preset_uses_stream_json_mode(env):
    fake = _fake_command(env.bin, "agy", AGY_OK)
    a.offer_summaries("antigravity", True)
    cfg = env.cfg()
    assert os.path.samefile(cfg["summariser"][0], fake)
    assert cfg["summariser"][1:] == ["--input-format", "stream-json", "--output-format", "stream-json", "--print-timeout", "600s"]
    assert cfg["summariser_input"] == "agy-stream-json"
