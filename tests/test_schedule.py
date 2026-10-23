import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from personal_tracker import schedule, server
from personal_tracker.errors import TrackerError

LABEL = "com.personal-work-dashboard.refresh"


def done(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, out, err)


@pytest.fixture
def os_calls(monkeypatch, tmp_path):
    """Replace every call into the OS with a recorder; LaunchAgents lives in tmp_path. `calls` lists argv's;
    set `os_calls.results[<first two argv words>]` to change what a command returns."""
    calls, results = [], {}

    def fake_run(argv):
        calls.append(list(argv))
        return results.get(" ".join(argv[:2]), done())
    monkeypatch.setattr(schedule, "_run", fake_run)
    monkeypatch.setattr(schedule, "plist_path", lambda: tmp_path / "LaunchAgents" / (LABEL + ".plist"))
    monkeypatch.setenv("TRACKER_HOME", str(tmp_path / "home"))
    fake_run.calls, fake_run.results = calls, results
    return fake_run


def test_launchd_plist_contents(tmp_path):
    home = tmp_path / "my home"
    p = plistlib.loads(schedule.launchd_plist("/venv/bin/python", "17:05", home).encode("utf-8"))
    assert p["Label"] == LABEL
    assert p["ProgramArguments"] == ["/venv/bin/python", "-m", "personal_tracker", "refresh", "--quiet"]
    assert p["StartCalendarInterval"] == {"Hour": 17, "Minute": 5}
    env = p["EnvironmentVariables"]
    assert env["PATH"].startswith(os.path.expanduser("~/.local/bin") + ":")        # where `claude` usually lives
    assert env["PATH"].endswith(":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    assert env["TRACKER_HOME"] == str(home)
    assert p["StandardOutPath"] == str(home / "launchd.out.log") and p["StandardErrorPath"] == str(home / "launchd.err.log")


def test_schtasks_create_argv():
    assert schedule.schtasks_create_argv("C:\\Py\\pythonw.exe", "17:00") == [
        "schtasks", "/Create", "/SC", "DAILY", "/ST", "17:00", "/TN", "PersonalWorkDashboard\\Refresh",
        "/TR", '"C:\\Py\\pythonw.exe" -m personal_tracker refresh --quiet', "/F"]


@pytest.mark.parametrize("bad", ["25:00", "5pm", "17:60", "", "9", "17-00", "17:5", "ab:cd"])
def test_bad_times_are_rejected(bad):
    with pytest.raises(TrackerError, match="HH:MM"):
        schedule.parse_time(bad)


@pytest.mark.parametrize("ok, want", [("09:05", (9, 5)), ("9:05", (9, 5)), ("0:00", (0, 0)), ("23:59", (23, 59))])
def test_good_times(ok, want):
    assert schedule.parse_time(ok) == want


def test_linux_prints_a_crontab_line_and_changes_nothing(os_calls, capsys):
    schedule.on("17:00", plat="linux")
    assert os_calls.calls == []
    out = capsys.readouterr().out
    assert "0 17 * * * " in out and "-m personal_tracker refresh --quiet" in out and "crontab" in out
    schedule.off(plat="linux")
    assert os_calls.calls == []


def test_macos_on_twice_leaves_one_job_with_the_new_time(os_calls, tmp_path):
    plist = schedule.plist_path()
    uid = os.getuid()
    schedule.on("17:00", plat="darwin")
    schedule.on("18:30", plat="darwin")
    assert os_calls.calls == [["launchctl", "bootout", "gui/%d/%s" % (uid, LABEL)], ["launchctl", "bootstrap", "gui/%d" % uid, str(plist)]] * 2
    assert plistlib.loads(plist.read_bytes())["StartCalendarInterval"] == {"Hour": 18, "Minute": 30}
    assert [p.name for p in plist.parent.iterdir()] == [LABEL + ".plist"]


def test_macos_not_loaded_on_first_install_is_fine_but_bootstrap_failure_is_reported(os_calls):
    os_calls.results["launchctl bootout"] = done(113, err="Could not find service")
    schedule.on("17:00", plat="darwin")                                         # bootout of a missing job is expected
    os_calls.results["launchctl bootstrap"] = done(5, err="boom: Input/output error")
    with pytest.raises(TrackerError, match="boom"):
        schedule.on("17:00", plat="darwin")


def test_macos_off_removes_the_plist_and_is_safe_when_already_off(os_calls):
    schedule.on("17:00", plat="darwin")
    schedule.off(plat="darwin")
    assert not schedule.plist_path().exists() and os_calls.calls[-1][:2] == ["launchctl", "bootout"]
    schedule.off(plat="darwin")                                                 # nothing to remove: no error


def test_macos_status(os_calls):
    assert schedule.status(plat="darwin").startswith("off")
    schedule.on("17:05", plat="darwin")
    assert "on" in schedule.status(plat="darwin") and "17:05" in schedule.status(plat="darwin")
    os_calls.results["launchctl print"] = done(113)                             # plist written but job not loaded
    assert schedule.status(plat="darwin").startswith("off")


def test_windows_on_off_status(os_calls):
    schedule.on("07:30", plat="win32")
    assert os_calls.calls == [schedule.schtasks_create_argv(server.background_python(sys.executable, "win32"), "07:30")]
    os_calls.results["schtasks /Create"] = done(1, err="ERROR: Access is denied.")
    with pytest.raises(TrackerError, match="Access is denied"):
        schedule.on("07:30", plat="win32")
    schedule.off(plat="win32")
    assert os_calls.calls[-1] == ["schtasks", "/Delete", "/TN", "PersonalWorkDashboard\\Refresh", "/F"]
    os_calls.results["schtasks /Query"] = done(0, out="PersonalWorkDashboard\\Refresh   07:30")
    assert schedule.status(plat="win32").startswith("on")
    os_calls.results["schtasks /Query"] = done(1)
    assert schedule.status(plat="win32").startswith("off")


def test_cli_rejects_a_bad_time_before_touching_the_os(sandbox):
    r = sandbox("schedule", "on", "--at", "25:00")
    assert r.returncode == 1 and "HH:MM" in r.stderr and "Traceback" not in r.stderr
