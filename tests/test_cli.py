from personal_tracker import __version__


def test_version(sandbox):
    r = sandbox("--version")
    assert r.returncode == 0 and r.stdout.strip() == "tracker " + __version__ == "tracker 0.8.0"


def test_no_config_says_run_init(sandbox):
    (sandbox.dir / "config.json").unlink()
    r = sandbox("todo")
    assert r.returncode == 1 and "tracker init" in r.stderr


def test_add_hindi_title(sandbox):
    title = "हिंदी दस्तावेज़ → ✅"
    assert sandbox("add", title).stdout.strip() == "t-0001"
    assert title in sandbox("todo").stdout


def test_user_errors_are_one_line_not_a_traceback(sandbox):
    r = sandbox("start", "t-0999")
    assert r.returncode == 1 and "Traceback" not in r.stderr and "no task with id t-0999" in r.stderr
