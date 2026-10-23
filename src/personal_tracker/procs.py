"""Options for starting child processes."""
import sys

CREATE_NO_WINDOW = 0x08000000


def no_window(plat=None):
    """Popen/run options that stop a console program (git, a .cmd shim) from opening a visible window when the
    caller has no console of its own, as with pythonw under Task Scheduler or the edit server on Windows."""
    return {"creationflags": CREATE_NO_WINDOW} if (plat or sys.platform) == "win32" else {}
