class TrackerError(Exception):
    """A problem to show the user as one line (cli.main prints it and exits 1)."""


class DataError(TrackerError):
    """A data file that can't be read."""
