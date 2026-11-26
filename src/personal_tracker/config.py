"""Settings from <data folder>/config.json (see docs/schema/todo-json.md for the fields)."""
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import files, paths
from .errors import TrackerError


@dataclass(frozen=True)
class Config:
    roots: list[Path]                  # folders containing your git repos (config "root", or "roots" for several)
    author_emails: list[str]           # every email you commit as
    timezone: str | None = None        # IANA name for day boundaries; None = this computer's zone
    summariser: list[str] | None = None  # argv of a command: prompt on stdin, JSON on stdout; None = no summaries
    summariser_input: str = "stdin"      # how the prompt is passed: "stdin" or "agy-stream-json" (Antigravity's agy)

    @property
    def root(self) -> Path:
        """The first root folder."""
        return self.roots[0]


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
        listed = raw.get("roots") or ([raw["root"]] if raw.get("root") else [])
        if not isinstance(listed, list) or not listed or not all(isinstance(r, str) and r.strip() for r in listed):
            raise KeyError("root")
        roots = [Path(r).expanduser() for r in listed]
    except (KeyError, TypeError) as e:
        raise TrackerError("%s: missing or invalid %s -- run: tracker init --force" % (path, e)) from e
    if not emails:
        raise TrackerError("%s: author_emails is empty" % path)
    tz = raw.get("timezone") or None
    summariser = raw.get("summariser") or None
    if summariser is not None and not (isinstance(summariser, list) and all(isinstance(a, str) for a in summariser)):
        raise TrackerError("%s: summariser must be a list of strings (a command and its arguments)" % path)
    mode = raw.get("summariser_input") or "stdin"
    if mode not in ("stdin", "agy-stream-json"):
        raise TrackerError("%s: summariser_input must be \"stdin\" or \"agy-stream-json\", not %r" % (path, mode))
    return Config(roots=roots, author_emails=emails, timezone=check_timezone(tz) if tz else None, summariser=summariser,
                  summariser_input=mode)
