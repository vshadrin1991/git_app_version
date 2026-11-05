"""Text from outside the app (git's stderr, the remote's "remote:" lines, gh's output) made safe to show."""
from __future__ import annotations

import logging
import re

# C0/C1 controls except "\n", bidi marks, overrides and isolates, and the Unicode line and paragraph
# separators: outside text must not rewrite the terminal, reorder what the user reads, or start a line.
_UNPRINTABLE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f\u061c\u200e\u200f\u2028-\u202e\u2066-\u2069]")


def printable(text: str, keep_newlines: bool = False) -> str:
    """`text` with control characters and bidi overrides replaced by "?"; newlines too unless kept."""
    cleaned = _UNPRINTABLE.sub("?", text)
    return cleaned if keep_newlines else cleaned.replace("\n", "?")


class PrintableFormatter(logging.Formatter):
    """Log lines quote git and gh: keep their control characters out of the log window, app.log and stderr."""

    def format(self, record: logging.LogRecord) -> str:
        return printable(super().format(record), keep_newlines=True)
