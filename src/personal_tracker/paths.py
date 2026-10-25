"""Where the tracker keeps its data: $TRACKER_HOME, else ~/.personal-tracker (same on every OS)."""
import os
from pathlib import Path


def home() -> Path:
    env = os.environ.get("TRACKER_HOME")
    return Path(env) if env else Path.home() / ".personal-tracker"


def file(name: str) -> Path:
    return home() / name
