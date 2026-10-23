"""Settings from <data folder>/config.json (see docs/schema/todo-json.md for the fields)."""
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import files, paths
from .errors import TrackerError


@dataclass(frozen=True)
class Config:
    root: Path                         # folder containing your git repos
    author_emails: list[str]           # every email you commit as
    timezone: str | None = None        # IANA name for day boundaries; None = this computer's zone
    summariser: list[str] | None = None  # argv of a command: prompt on stdin, JSON on stdout; None = no summaries


def check_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as e:
        raise TrackerError("unknown timezone: %s" % name) from e
    return name


def load() -> Config:
    path = paths.file("config.json")
    raw = files.read_json(path)
    if raw is None:
        raise TrackerError("no config at %s -- run: tracker init" % path)
    try:
        emails = list(raw["author_emails"])
        root = Path(raw["root"]).expanduser()
    except (KeyError, TypeError) as e:
        raise TrackerError("%s: missing or invalid %s -- run: tracker init --force" % (path, e)) from e
    if not emails:
        raise TrackerError("%s: author_emails is empty" % path)
    tz = raw.get("timezone") or None
    summariser = raw.get("summariser") or None
    if summariser is not None and not (isinstance(summariser, list) and all(isinstance(a, str) for a in summariser)):
        raise TrackerError("%s: summariser must be a list of strings (a command and its arguments)" % path)
    return Config(root=root, author_emails=emails, timezone=check_timezone(tz) if tz else None, summariser=summariser)
