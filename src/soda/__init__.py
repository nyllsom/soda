"""SODA: compile Markdown and optional motion into browser presentations."""

from ._version import __version__
from .api import Deck, compile_deck, compile_text, export_html
from .compiler.diagnostics import SodaError

__all__ = ["__version__", "Deck", "SodaError", "compile_deck", "compile_text", "export_html"]
