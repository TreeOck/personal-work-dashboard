"""First-run setup: `tracker init` writes the config, `tracker migrate` moves an old checkout's data into the data folder."""
import os
import shlex
import shutil
import sys
from datetime import date
from pathlib import Path

from . import config, files, paths
from .errors import TrackerError

CLAUDE_SUMMARISER = ["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence"]
MIGRATED_TIMEZONE = "Asia/Kolkata"   # the old scripts hard-coded it, so a migrated config keeps that behaviour
DATA_FILES = ("config.json", "todo.json", "tasks.json", "commits.json", "inks.json")
_COUNTS = {"todo.json": "items", "tasks.json": "tasks", "commits.json": "commits"}


def detect_timezone(localtime="/etc/localtime"):
    """The computer's IANA timezone name when it can be read from the localtime symlink, else None."""
    real = os.path.realpath(localtime)
    marker = "zoneinfo" + os.sep
    if marker not in real:
        return None
    try:
        return config.check_timezone(real.split(marker, 1)[1].replace(os.sep, "/"))
    except TrackerError:
        return None


def default_summariser():
    return CLAUDE_SUMMARISER if shutil.which("claude") else None


def split_command(line):
    return shlex.split(line, posix=os.name != "nt")   # Windows paths contain backslashes


def init(root, emails, timezone=None, summariser=None, force=False):
    root = (root or "").strip()
    emails = [e.strip() for e in emails if e and e.strip()]
    if not root:
        raise TrackerError("root can't be empty (the folder that contains your git repos)")
    if not emails:
        raise TrackerError("at least one author email is needed (the email(s) you commit as)")
    if timezone:
        config.check_timezone(timezone)
    path = paths.file("config.json")
    if path.exists() and not force:
        raise TrackerError("%s already exists -- use --force to overwrite it" % path)
    paths.home().mkdir(parents=True, exist_ok=True)
    files.write_json(path, {"root": root, "author_emails": emails, "timezone": timezone or None, "summariser": summariser or None})
    if not Path(root).expanduser().is_dir():
        print("warning: %s doesn't exist yet; keeping it anyway" % Path(root).expanduser(), file=sys.stderr)
    return path


def default_source():
    """The checkout this package is running from, when it still holds the old data files."""
    src = Path(__file__).resolve().parents[2]
    if not (src / "config.json").is_file():
        raise TrackerError("can't tell where your old data is -- pass --from <folder with your old config.json and todo.json>")
    return src


def _fill_config_defaults(path):
    cfg = files.read_json(path)
    cfg.setdefault("timezone", MIGRATED_TIMEZONE)
    cfg.setdefault("summariser", CLAUDE_SUMMARISER)
    files.write_json(path, cfg)


def _verify(src, home, names):
    for n in names:
        a, b = files.read_json(src / n), files.read_json(home / n)
        if n in _COUNTS:
            key = _COUNTS[n]
            if len(a[key]) != len(b[key]):
                raise TrackerError("%s: the copy has %d %s but the original has %d" % (n, len(b[key]), key, len(a[key])))
        elif any(b.get(k) != v for k, v in a.items()):   # config gains keys; nothing the original had may change
            raise TrackerError("%s: the copy doesn't match the original" % n)


def _rename_original(path, today):
    dest = path.with_name("%s.migrated-%s" % (path.name, today.strftime("%Y%m%d")))
    n = 2
    while dest.exists():
        dest = path.with_name("%s.migrated-%s-%d" % (path.name, today.strftime("%Y%m%d"), n))
        n += 1
    path.rename(dest)


def migrate(src, today=None):
    """Copy an old checkout's data files into the data folder, verify them, then rename the originals
    to <name>.migrated-YYYYMMDD so nothing old can keep writing to a live copy. Returns the names moved."""
    src, home, today = Path(src), paths.home(), today or date.today()
    if home.exists() and src.resolve() == home.resolve():
        raise TrackerError("the source and the data folder are the same (%s)" % src)
    names = [n for n in DATA_FILES if (src / n).is_file()]
    if not names:
        raise TrackerError("nothing to migrate in %s" % src)
    taken = [n for n in DATA_FILES if (home / n).exists()]
    if taken:
        raise TrackerError("%s already has data (%s); nothing was changed" % (home, ", ".join(taken)))
    created = not home.exists()
    home.mkdir(parents=True, exist_ok=True)
    try:
        for n in names:
            shutil.copy2(src / n, home / n)
        if "config.json" in names:
            _fill_config_defaults(home / "config.json")
        _verify(src, home, names)
    except (OSError, TrackerError) as e:
        for n in names:                      # none of these existed before, so anything there now is ours
            (home / n).unlink(missing_ok=True)
        if created:
            try:
                home.rmdir()
            except OSError:
                pass
        raise e if isinstance(e, TrackerError) else TrackerError("migrate failed (%s); nothing was changed" % e)
    for n in names:
        try:
            _rename_original(src / n, today)
        except OSError as e:
            raise TrackerError("copied to %s, but couldn't rename %s (%s) -- rename the old files by hand so nothing keeps writing to them" % (home, n, e))
    return names
