"""Daily refresh (`tracker refresh --quiet`): launchd on macOS, Task Scheduler on Windows, a crontab line on Linux."""
import os
import plistlib
import re
import shlex
import subprocess
import sys
from pathlib import Path

from . import paths, server
from .errors import TrackerError

LABEL = "com.personal-work-dashboard.refresh"     # macOS LaunchAgent
TASK = "PersonalWorkDashboard\\Refresh"           # Windows scheduled task
_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_time(at):
    m = _TIME.match(at or "")
    if not m:
        raise TrackerError("time must be HH:MM in 24-hour form, e.g. 17:00 (got %r)" % at)
    return int(m.group(1)), int(m.group(2))


def _run(argv):
    """The only place that calls into the OS; tests replace it."""
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")


def plist_path():
    return Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")


def launchd_plist(python, at, home):
    hour, minute = parse_time(at)
    home = Path(home)
    # launchd starts jobs with a minimal PATH; add where `claude` and git usually live
    path = ":".join([os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"])
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [python, "-m", "personal_tracker", "refresh", "--quiet"],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "EnvironmentVariables": {"PATH": path, "TRACKER_HOME": str(home)},
        "StandardOutPath": str(home / "launchd.out.log"),
        "StandardErrorPath": str(home / "launchd.err.log"),
    }).decode("utf-8")


def schtasks_create_argv(pythonw, at):
    return ["schtasks", "/Create", "/SC", "DAILY", "/ST", at, "/TN", TASK,
            "/TR", '"%s" -m personal_tracker refresh --quiet' % pythonw, "/F"]


def crontab_line(python, at, home):
    hour, minute = parse_time(at)
    env = "TRACKER_HOME=%s " % shlex.quote(str(home)) if os.environ.get("TRACKER_HOME") else ""
    return "%d %d * * * %s%s -m personal_tracker refresh --quiet" % (minute, hour, env, shlex.quote(python))


def _launchd_target():
    return "gui/%d/%s" % (os.getuid(), LABEL)


def on(at="17:00", plat=sys.platform):
    hour, minute = parse_time(at)
    at = "%02d:%02d" % (hour, minute)
    home = paths.home()
    if plat == "darwin":
        home.mkdir(parents=True, exist_ok=True)
        plist = plist_path()
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(launchd_plist(sys.executable, at, home), encoding="utf-8")
        _run(["launchctl", "bootout", _launchd_target()])           # replace a running copy; "not loaded" is fine
        r = _run(["launchctl", "bootstrap", "gui/%d" % os.getuid(), str(plist)])
        if r.returncode != 0:
            raise TrackerError("launchctl couldn't load the job: %s" % (r.stderr.strip() or r.stdout.strip() or r.returncode))
        print("Daily refresh on: %s at %s (%s)" % ("macOS LaunchAgent", at, plist))
    elif plat == "win32":
        if os.environ.get("TRACKER_HOME"):
            print("warning: the scheduled task can't see TRACKER_HOME from this shell; set it for your user too "
                  "(setx TRACKER_HOME ...) or it will use the default data folder", file=sys.stderr)
        r = _run(schtasks_create_argv(server.background_python(sys.executable, "win32"), at))
        if r.returncode != 0:
            raise TrackerError("schtasks couldn't create the task: %s" % (r.stderr.strip() or r.stdout.strip() or r.returncode))
        print("Daily refresh on: Task Scheduler task %s at %s" % (TASK, at))
    else:
        print("This system has no scheduler tracker manages. Add this line with `crontab -e`:\n\n%s\n" % crontab_line(sys.executable, at, home))


def off(plat=sys.platform):
    if plat == "darwin":
        _run(["launchctl", "bootout", _launchd_target()])
        existed = plist_path().exists()
        plist_path().unlink(missing_ok=True)
        print("Daily refresh off" if existed else "Daily refresh was already off")
    elif plat == "win32":
        r = _run(["schtasks", "/Delete", "/TN", TASK, "/F"])
        print("Daily refresh off" if r.returncode == 0 else "Daily refresh was already off")
    else:
        print("Remove the tracker line from your crontab (`crontab -e`).")


def status(plat=sys.platform):
    if plat == "darwin":
        plist = plist_path()
        if not plist.exists():
            return "off (run: tracker schedule on)"
        when = plistlib.loads(plist.read_bytes())["StartCalendarInterval"]
        if _run(["launchctl", "print", _launchd_target()]).returncode != 0:
            return "off: the LaunchAgent file exists but isn't loaded (run: tracker schedule on)"
        return "on: refreshes daily at %02d:%02d (%s)" % (when["Hour"], when["Minute"], plist)
    if plat == "win32":
        r = _run(["schtasks", "/Query", "/TN", TASK])
        return "on: Task Scheduler task %s" % TASK if r.returncode == 0 else "off (run: tracker schedule on)"
    return "not managed on this system; use cron (see: tracker schedule on)"
