import json
import shutil
import sys
from datetime import date

import pytest

from personal_tracker import config, setup
from personal_tracker.errors import TrackerError

CLAUDE = ["claude", "-p", "--model", "sonnet", "--tools", "", "--no-session-persistence"]


@pytest.fixture
def home(monkeypatch, tmp_path):
    h = tmp_path / "home"
    monkeypatch.setenv("TRACKER_HOME", str(h))
    return h


def old_checkout(tmp_path):
    """A pre-package checkout: flat data files next to the code, config without timezone/summariser."""
    old = tmp_path / "old"
    old.mkdir()
    (old / "config.json").write_text(json.dumps({"root": "~/Valiance", "author_emails": ["a@b.c"]}), encoding="utf-8")
    items = [{"id": "t-000%d" % n, "title": "हिंदी → ✅" if n == 2 else "task %d" % n, "status": "todo", "notes": []} for n in (1, 2, 3)]
    (old / "todo.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    (old / "tasks.json").write_text(json.dumps({"tasks": [{"id": "x"}]}), encoding="utf-8")
    (old / "commits.json").write_text(json.dumps({"commits": [{"sha": "a"}, {"sha": "b"}]}), encoding="utf-8")
    (old / "inks.json").write_text(json.dumps({"alpha": {"ink": "momiji", "variant": 0}}), encoding="utf-8")
    return old


# ---- init

def test_init_writes_config_and_refuses_overwrite(home):
    path = setup.init("~/code", ["me@example.com", "me@work.example"], timezone="Europe/London", summariser=CLAUDE)
    assert json.loads(path.read_text(encoding="utf-8")) == {"root": "~/code", "author_emails": ["me@example.com", "me@work.example"],
                                                            "timezone": "Europe/London", "summariser": CLAUDE}
    cfg = config.load()
    assert cfg.timezone == "Europe/London" and cfg.summariser == CLAUDE and len(cfg.author_emails) == 2
    with pytest.raises(TrackerError, match="--force"):
        setup.init("~/other", ["x@y.z"])
    assert config.load().author_emails == ["me@example.com", "me@work.example"]       # untouched
    setup.init("~/other", ["x@y.z"], force=True)
    assert config.load().author_emails == ["x@y.z"]


def test_init_rejects_bad_input_without_writing(home):
    with pytest.raises(TrackerError, match="unknown timezone: Mars/Base"):
        setup.init("~/code", ["a@b.c"], timezone="Mars/Base")
    with pytest.raises(TrackerError, match="email"):
        setup.init("~/code", [" ", ""])
    with pytest.raises(TrackerError, match="root"):
        setup.init("  ", ["a@b.c"])
    assert not (home / "config.json").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="reads /etc/localtime, a Unix symlink; symlinks need extra rights on Windows")
def test_detect_timezone_from_localtime_symlink(tmp_path):
    zi = tmp_path / "usr" / "share" / "zoneinfo" / "Asia"
    zi.mkdir(parents=True)
    (zi / "Kolkata").write_text("")
    link = tmp_path / "localtime"
    link.symlink_to(zi / "Kolkata")
    assert setup.detect_timezone(str(link)) == "Asia/Kolkata"
    assert setup.detect_timezone(str(tmp_path / "missing")) is None


def test_cli_init_with_flags(sandbox):
    (sandbox.dir / "config.json").unlink()
    r = sandbox("init", "--root", "~/code", "--email", "me@example.com", "--timezone", "Asia/Kolkata", "--no-summariser")
    assert r.returncode == 0, r.stderr
    assert sandbox("todo").returncode == 0
    again = sandbox("init", "--root", "~/code", "--email", "me@example.com")
    assert again.returncode == 1 and "--force" in again.stderr
    bad = sandbox("init", "--root", "~/code", "--email", "me@example.com", "--timezone", "Mars/Base", "--force")
    assert bad.returncode == 1 and "unknown timezone: Mars/Base" in bad.stderr


def test_cli_init_needs_root_and_email_when_not_interactive(sandbox):
    (sandbox.dir / "config.json").unlink()
    r = sandbox("init")
    assert r.returncode == 1 and "--root" in r.stderr and "--email" in r.stderr


def test_init_prompts_when_interactive(home, monkeypatch, capsys):
    from personal_tracker import cli
    answers = iter(["~/Valiance", "a@b.c, d@e.f", "Asia/Kolkata", "none"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli.main(["init"]) == 0
    cfg = config.load()
    assert str(cfg.root).endswith("Valiance") and cfg.author_emails == ["a@b.c", "d@e.f"]
    assert cfg.timezone == "Asia/Kolkata" and cfg.summariser is None


def test_init_with_an_unusable_stdin_asks_for_flags_instead_of_crashing(home, monkeypatch, capsys):
    # Windows reports isatty() True for NUL (what scripts and agents get), then input() hits end-of-file
    from personal_tracker import cli

    def eof(prompt=""):
        raise EOFError
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", eof)
    assert cli.main(["init"]) == 1
    err = capsys.readouterr().err
    assert "--root" in err and "--email" in err and "Traceback" not in err
    assert not (home / "config.json").exists()


def test_init_with_root_and_email_but_an_unusable_stdin_uses_defaults_for_the_optional_answers(home, monkeypatch):
    # same Windows NUL situation: the optional prompts (timezone, summariser) must fall back to defaults, not fail
    from personal_tracker import cli

    def eof(prompt=""):
        raise EOFError
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", eof)
    assert cli.main(["init", "--root", "~/code", "--email", "a@b.c"]) == 0
    cfg = config.load()
    assert cfg.author_emails == ["a@b.c"] and cfg.summariser == setup.default_summariser()
    assert cli.main(["init", "--root", "~/code", "--email", "a@b.c"]) == 1       # second time: refuses, and says why


# ---- migrate

def test_migrate_copies_verifies_and_renames(home, tmp_path):
    old = old_checkout(tmp_path)
    before = {n: json.loads((old / n).read_text(encoding="utf-8")) for n in ("todo.json", "tasks.json", "commits.json", "inks.json")}
    names = setup.migrate(old, date(2026, 10, 23))
    assert sorted(names) == ["commits.json", "config.json", "inks.json", "tasks.json", "todo.json"]
    for n, data in before.items():
        assert json.loads((home / n).read_text(encoding="utf-8")) == data
    cfg = json.loads((home / "config.json").read_text(encoding="utf-8"))
    assert cfg == {"root": "~/Valiance", "author_emails": ["a@b.c"], "timezone": "Asia/Kolkata", "summariser": CLAUDE}
    for n in names:
        assert not (old / n).exists() and (old / (n + ".migrated-20261023")).exists()      # renamed, not left live
    assert "हिंदी → ✅" in (home / "todo.json").read_text(encoding="utf-8")


def test_migrate_keeps_an_existing_timezone_and_summariser(home, tmp_path):
    old = old_checkout(tmp_path)
    (old / "config.json").write_text(json.dumps({"root": "r", "author_emails": ["a@b.c"], "timezone": "Europe/London",
                                                 "summariser": ["mine"]}), encoding="utf-8")
    setup.migrate(old, date(2026, 10, 23))
    cfg = json.loads((home / "config.json").read_text(encoding="utf-8"))
    assert cfg["timezone"] == "Europe/London" and cfg["summariser"] == ["mine"]


def test_migrate_refuses_when_target_has_data(home, tmp_path):
    old = old_checkout(tmp_path)
    home.mkdir()
    (home / "todo.json").write_text('{"items": []}', encoding="utf-8")
    with pytest.raises(TrackerError, match="todo.json"):
        setup.migrate(old, date(2026, 10, 23))
    assert (old / "todo.json").exists() and not list(old.glob("*.migrated-*"))      # source untouched
    assert (home / "todo.json").read_text(encoding="utf-8") == '{"items": []}'      # target untouched


def test_migrate_twice_refuses_the_second_time(home, tmp_path):
    old = old_checkout(tmp_path)
    setup.migrate(old, date(2026, 10, 23))
    with pytest.raises(TrackerError):
        setup.migrate(old, date(2026, 10, 24))


def test_migrate_partial_failure_leaves_source_intact(home, tmp_path, monkeypatch):
    old = old_checkout(tmp_path)
    real, calls = shutil.copy2, []

    def flaky(src, dst, *a, **k):
        calls.append(src)
        if len(calls) == 3:
            raise OSError("disk full")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(setup.shutil, "copy2", flaky)
    with pytest.raises(TrackerError, match="disk full"):
        setup.migrate(old, date(2026, 10, 23))
    assert sorted(p.name for p in old.iterdir()) == ["commits.json", "config.json", "inks.json", "tasks.json", "todo.json"]
    assert not home.exists() or not any(home.iterdir())                              # no partial copies left behind


def test_migrate_detects_a_copy_that_does_not_match(home, tmp_path, monkeypatch):
    old = old_checkout(tmp_path)
    real = shutil.copy2

    def truncating(src, dst, *a, **k):
        real(src, dst, *a, **k)
        if str(src).endswith("todo.json"):
            (home / "todo.json").write_text('{"items": []}', encoding="utf-8")
    monkeypatch.setattr(setup.shutil, "copy2", truncating)
    with pytest.raises(TrackerError, match="todo.json"):
        setup.migrate(old, date(2026, 10, 23))
    assert (old / "todo.json").exists() and not list(old.glob("*.migrated-*"))


def test_migrate_with_nothing_to_migrate(home, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(TrackerError, match="nothing to migrate"):
        setup.migrate(empty, date(2026, 10, 23))


def test_migrate_from_the_data_folder_itself_is_refused(home):
    home.mkdir()
    (home / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(TrackerError, match="same"):
        setup.migrate(home, date(2026, 10, 23))
