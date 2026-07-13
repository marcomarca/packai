"""Single package version source for runtime display."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pack-ai")
except PackageNotFoundError:
    __version__ = "2.3.0"

VERSION = __version__
