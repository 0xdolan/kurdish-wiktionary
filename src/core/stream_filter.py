"""Filter known noisy lines from native libraries (libzim/xapian) during CLI progress."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from typing import TextIO

_SUPPRESSED_SUBSTRINGS = (
    "No stemming for language",
)


class _LineFilterWriter:
    def __init__(self, underlying: TextIO) -> None:
        self._underlying = underlying
        self._pending = ""

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._pending += data
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._emit_line(line)
        return len(data)

    def _emit_line(self, line: str) -> None:
        stripped = line.strip()
        if stripped in {"'ku'", "ku"}:
            return
        if stripped.startswith("'") and stripped.endswith("'") and len(stripped) <= 5:
            return
        if any(token in line for token in _SUPPRESSED_SUBSTRINGS):
            return
        self._underlying.write(line + "\n")

    def flush(self) -> None:
        if self._pending:
            pending = self._pending
            stripped = pending.strip()
            noisy = stripped in {"'ku'", "ku"} or (
                stripped.startswith("'") and stripped.endswith("'") and len(stripped) <= 5
            )
            if not noisy and not any(token in pending for token in _SUPPRESSED_SUBSTRINGS):
                self._underlying.write(self._pending)
            self._pending = ""
        self._underlying.flush()

    def __getattr__(self, name: str) -> object:
        return getattr(self._underlying, name)


@contextlib.contextmanager
def suppress_known_zim_noise() -> Iterator[None]:
    """Keep Rich progress stable while libzim prints per-lookup warnings."""
    out_filter = _LineFilterWriter(sys.stdout)
    err_filter = _LineFilterWriter(sys.stderr)
    with contextlib.redirect_stdout(out_filter), contextlib.redirect_stderr(err_filter):
        yield
