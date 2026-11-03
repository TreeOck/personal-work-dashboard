"""Options for starting child processes."""
import sys

CREATE_NO_WINDOW = 0x08000000


def no_window(plat=None):
    """Popen/run options that stop a console program (git, a .cmd shim) from opening a visible window when the
    caller has no console of its own, as with pythonw under Task Scheduler or the edit server on Windows."""
    return {"creationflags": CREATE_NO_WINDOW} if (plat or sys.platform) == "win32" else {}


def _kill_tree(proc):
    """Stop a process and everything it started. Windows: a .cmd shim's real program is a child of cmd.exe and keeps
    the output pipes open after the shim is killed. Elsewhere the process leads its own group (see run_tree)."""
    import os
    import signal
    import subprocess
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30, **no_window())
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run_tree(cmd, input_text, timeout, cwd=None):
    """subprocess.run(cmd, input=..., capture_output=True, text UTF-8, timeout=...) that, on timeout or interruption,
    stops the whole process tree instead of only `cmd`. Raises subprocess.TimeoutExpired like run()."""
    import subprocess
    extra = no_window()
    if sys.platform != "win32":
        extra["start_new_session"] = True   # its own process group, so the group can be killed together
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", cwd=cwd, **extra)
    try:
        out, err = proc.communicate(input_text, timeout=timeout)
    except BaseException:   # timeout, Ctrl-C, anything: don't leave the summariser running
        _kill_tree(proc)
        try:
            proc.communicate(timeout=10)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            pass
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
