from pathlib import Path

from personal_tracker import paths


def test_home_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_HOME", str(tmp_path / "a b"))
    assert paths.home() == tmp_path / "a b"
    assert paths.file("todo.json") == tmp_path / "a b" / "todo.json"
    monkeypatch.delenv("TRACKER_HOME")
    assert paths.home() == Path.home() / ".personal-tracker"


def test_home_does_not_create_the_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_HOME", str(tmp_path / "new"))
    paths.home()
    assert not (tmp_path / "new").exists()
