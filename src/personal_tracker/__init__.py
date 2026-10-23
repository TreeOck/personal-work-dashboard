from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("personal-work-dashboard")
except PackageNotFoundError:   # running from a source tree that was never installed
    __version__ = "0+unknown"
