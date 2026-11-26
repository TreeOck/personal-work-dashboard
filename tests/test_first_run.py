"""Interactive `tracker init` goes on to the first-run steps: scan, daily refresh, connect an AI tool, open the page.
The steps themselves are the same functions as their own commands (tested elsewhere), so they're recorded here."""
import json

import pytest

from personal_tracker import cli
from personal_tracker.errors import TrackerError

CLAUDE = ["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence"]
INIT = ["~/code", "me@example.com", "Asia/Kolkata", "none"]   # root, email, timezone, summariser


@pytest.fixture
def home(monkeypatch, tmp_path):
    h = tmp_path / "home"
    monkeypatch.setenv("TRACKER_HOME", str(h))
    return h


@pytest.fixture
def steps(monkeypatch):
    """Record every step instead of scanning git, loading a LaunchAgent, editing agent files or opening a browser."""
    calls = []
    monkeypatch.setattr(cli.scan, "run", lambda days=14, since=None: calls.append(("scan", days)))
    monkeypatch.setattr(cli.build, "build", lambda: calls.append(("build",)))
    monkeypatch.setattr(cli.schedule, "on", lambda at="17:00": calls.append(("schedule", at)))
    monkeypatch.setattr(cli.agent_setup, "setup", lambda tool, remove=False, force=False: calls.append(("setup", tool)) or ["%s: set up" % tool])
    monkeypatch.setattr(cli.agent_setup, "offer_summaries", lambda tool, choice: calls.append(("summaries", tool, choice)) or [])
    monkeypatch.setattr(cli.server, "open_dashboard", lambda: calls.append(("open",)))
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)
    return calls


def answering(monkeypatch, *answers):
    """A terminal that gives these answers, then end-of-file. Returns the prompts it was asked."""
    queue, prompts = list(answers), []

    def ask(prompt=""):
        prompts.append(prompt)
        if not queue:
            raise EOFError
        a = queue.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", ask)
    return prompts


def names(calls):
    return [c[0] for c in calls]


def test_defaults_run_every_step_in_order(home, steps, monkeypatch, capsys):
    answering(monkeypatch, *INIT, "", "", "")
    assert cli.main(["init"]) == 0
    assert steps == [("scan", 30), ("build",), ("schedule", "17:00"), ("setup", "claude-code"),
                     ("summaries", "claude-code", None), ("build",), ("open",)]
    assert (home / "config.json").exists()


def test_chosen_answers_are_passed_through(home, steps, monkeypatch):
    answering(monkeypatch, *INIT, "90", "09:30", "cursor")
    assert cli.main(["init"]) == 0
    assert ("scan", 90) in steps and ("schedule", "09:30") in steps and ("setup", "cursor") in steps


def test_every_optional_step_can_be_skipped(home, steps, monkeypatch):
    answering(monkeypatch, *INIT, "0", "n", "none")
    assert cli.main(["init"]) == 0
    assert names(steps) == ["build", "open"]   # nothing scanned, scheduled or connected; the empty page still opens


def test_bad_answers_are_asked_again(home, steps, monkeypatch, capsys):
    prompts = answering(monkeypatch, *INIT, "abc", "-5", "99999999", "7", "25:00", "maybe", "09:05", "vim", "Cursor")
    assert cli.main(["init"]) == 0
    assert ("scan", 7) in steps and ("schedule", "09:05") in steps and ("setup", "cursor") in steps
    assert sum("how many days" in p for p in prompts) == 4 and sum("every day" in p for p in prompts) == 3
    out = capsys.readouterr().out
    assert "whole number" in out and "100 years" in out and "time like 09:30" in out and "choose one of" in out


def test_no_claude_on_path_defaults_to_no_tool(home, steps, monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    prompts = answering(monkeypatch, *INIT, "", "", "")
    assert cli.main(["init"]) == 0
    assert "setup" not in names(steps) and prompts[-1].endswith("(none): ")


def test_claude_code_already_summarising_is_not_asked_again(home, steps, monkeypatch):
    answering(monkeypatch, "~/code", "me@example.com", "Asia/Kolkata", "", "0", "n", "")   # blank = Claude, as it's on PATH
    assert cli.main(["init"]) == 0
    assert json.loads((home / "config.json").read_text(encoding="utf-8"))["summariser"] == CLAUDE
    assert ("summaries", "claude-code", False) in steps


def test_a_failed_step_says_how_to_retry_and_the_rest_still_run(home, steps, monkeypatch, capsys):
    def no_git(days=14, since=None):
        raise TrackerError("git not found on PATH")
    monkeypatch.setattr(cli.scan, "run", no_git)
    answering(monkeypatch, *INIT, "", "", "")
    assert cli.main(["init"]) == 0
    out = capsys.readouterr().out
    assert "scan failed: git not found on PATH" in out and "retry later with: tracker scan --days 30" in out
    assert names(steps)[:2] == ["schedule", "setup"] and steps[-1] == ("open",)


def test_end_of_file_midway_stops_and_prints_the_remaining_commands(home, steps, monkeypatch, capsys):
    answering(monkeypatch, *INIT, "14")   # then EOF at the daily-refresh question
    assert cli.main(["init"]) == 0
    assert names(steps) == ["scan", "build"]
    assert "tracker schedule on" in capsys.readouterr().out


def test_ctrl_c_keeps_the_config_and_finished_steps(home, steps, monkeypatch, capsys):
    answering(monkeypatch, *INIT, "", KeyboardInterrupt())
    assert cli.main(["init"]) == 0
    assert names(steps) == ["scan", "build"] and (home / "config.json").exists()
    assert "Stopped. Your config is saved" in capsys.readouterr().out


def test_not_a_terminal_only_writes_the_config(home, steps, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("prompted without a terminal: %s" % prompt))
    assert cli.main(["init", "--root", "~/code", "--email", "me@example.com"]) == 0
    assert steps == [] and "Next: tracker scan --days 30" in capsys.readouterr().out


def test_existing_config_is_refused_before_any_step(home, steps, monkeypatch):
    answering(monkeypatch, *INIT, "", "", "")
    assert cli.main(["init"]) == 0
    steps.clear()
    answering(monkeypatch, *INIT, "", "", "")
    assert cli.main(["init"]) == 1 and steps == []


def test_an_os_error_in_a_step_is_reported_the_same_way(home, steps, monkeypatch, capsys):
    def read_only(at="17:00"):
        raise PermissionError("[Errno 13] Permission denied: 'LaunchAgents'")
    monkeypatch.setattr(cli.schedule, "on", read_only)
    answering(monkeypatch, *INIT, "0", "", "")
    assert cli.main(["init"]) == 0
    out = capsys.readouterr().out
    assert "daily refresh failed: [Errno 13]" in out and "retry later with: tracker schedule on --at 17:00" in out
    assert "Traceback" not in out and names(steps) == ["setup", "summaries", "build", "open"]
