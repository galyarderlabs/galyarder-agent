"""Galyarder Agent - Sovereignty-first AI assistant runtime for real daily workflows."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("galyarder-agent")
except PackageNotFoundError:
    __version__ = "0.1.10"

__logo__ = "🗿"
__brand__ = "g-agent"
