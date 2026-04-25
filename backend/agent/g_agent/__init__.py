"""Galyarder Agent - local-first runtime for agentic digital identity."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("galyarder-agent")
except PackageNotFoundError:
    __version__ = "0.1.13"

__logo__ = "G"
__brand__ = "g-agent"
# force ci
