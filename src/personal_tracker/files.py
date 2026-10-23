"""Cross-platform file helpers: UTF-8 JSON, atomic replace, and one exclusive lock."""
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from .errors import DataError

_RETRIES, _PAUSE = 10, 0.05   # Windows briefly refuses os.replace while antivirus or a reader holds the file


def read_json(path: Path, default=None):
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (ValueError, OSError) as e:
        raise DataError("%s: %s" % (path, e)) from e


def _replace(tmp: Path, path: Path) -> None:
    for attempt in range(_RETRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == _RETRIES - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(_PAUSE)


def write_text(path: Path, text: str) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    _replace(tmp, path)


def write_json(path: Path, obj, indent=1) -> None:
    write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False))


if sys.platform == "win32":
    import msvcrt

    def _acquire(f):
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)   # blocks ~10 s per try, so loop
                return
            except OSError:
                time.sleep(_PAUSE)

    def _release(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _acquire(f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def _release(f):
        fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def lock(path: Path):
    """Exclusive lock on `path` (created if needed); serialises concurrent tracker processes."""
    with open(path, "a+b") as f:
        _acquire(f)
        try:
            yield
        finally:
            _release(f)
