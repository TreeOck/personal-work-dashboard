import json
import os
import subprocess
import sys
import textwrap

import pytest

from personal_tracker import files
from personal_tracker.errors import DataError


def test_unicode_round_trip(tmp_path):
    p = tmp_path / "d.json"
    data = {"t": "हिंदी दस्तावेज़ → ✅ 🚀"}
    files.write_json(p, data)
    assert files.read_json(p) == data
    assert "हिंदी" in p.read_bytes().decode("utf-8")   # written as UTF-8, not \u escapes


def test_read_json_missing_and_bad(tmp_path):
    assert files.read_json(tmp_path / "nope.json", default={"x": 1}) == {"x": 1}
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(DataError) as e:
        files.read_json(bad)
    assert str(bad) in str(e.value)


def test_write_json_retries_permission_error(monkeypatch, tmp_path):
    p = tmp_path / "d.json"
    files.write_json(p, {"v": 1})
    real, calls = os.replace, []

    def flaky(a, b):
        calls.append(1)
        if len(calls) <= 2:
            raise PermissionError("held by antivirus")
        return real(a, b)
    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(files.time, "sleep", lambda s: None)
    files.write_json(p, {"v": 2})
    assert files.read_json(p) == {"v": 2} and len(calls) == 3

    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("always")))
    with pytest.raises(PermissionError):
        files.write_json(p, {"v": 3})
    assert files.read_json(p) == {"v": 2}            # original untouched


def test_write_text_is_utf8(tmp_path):
    p = tmp_path / "t.html"
    files.write_text(p, "<p>→ हिंदी</p>")
    assert p.read_bytes().decode("utf-8") == "<p>→ हिंदी</p>"


WORKER = textwrap.dedent("""
    import sys
    from pathlib import Path
    from personal_tracker.files import lock, read_json, write_json
    F, L, who = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    for i in range(15):
        with lock(L):
            d = read_json(F, {"n": []})
            d["n"].append("%s-%d" % (who, i))
            write_json(F, d)
""")


def test_concurrent_adds_lose_nothing(tmp_path):
    F, L, script = tmp_path / "d.json", tmp_path / "d.lock", tmp_path / "w.py"
    script.write_text(WORKER, encoding="utf-8")
    procs = [subprocess.Popen([sys.executable, str(script), str(F), str(L), w]) for w in ("a", "b")]
    assert [p.wait(timeout=60) for p in procs] == [0, 0]
    got = json.loads(F.read_text(encoding="utf-8"))["n"]
    assert len(got) == 30 and len(set(got)) == 30
