import sys


def _run() -> int:
    from .cli import main   # imported late so `python -m personal_tracker` fails readably until cli exists
    return main()


if __name__ == "__main__":
    sys.exit(_run())
