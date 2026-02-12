"""Galyarder Agent - A lightweight personal AI assistant framework."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("galyarder-agent")
except PackageNotFoundError:
    __version__ = "0.1.7"

__logo__ = "🗿"
__brand__ = "g-agent"
