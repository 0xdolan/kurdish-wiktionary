"""Filter known noisy lines from native libraries (libzim/xapian) during CLI progress."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from collections.abc import Iterator
from typing import TextIO

_SUPPRESSED_SUBSTRINGS = (
    "No stemming for language",
)


def _should_suppress_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in {"'ku'", "ku"}:
        return True
    if stripped.startswith("'") and stripped.endswith("'") and len(stripped) <= 5:
        return True
    return any(token in text for token in _SUPPRESSED_SUBSTRINGS)


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
        if _should_suppress_text(line):
            return
        self._underlying.write(line + "\n")

    def flush(self) -> None:
        if self._pending:
            pending = self._pending
            if not _should_suppress_text(pending):
                self._underlying.write(self._pending)
            self._pending = ""
        self._underlying.flush()

    def __getattr__(self, name: str) -> object:
        return getattr(self._underlying, name)


class _FdStderrFilter:
    """Re-entrant OS stderr redirect; libzim writes to fd 2, not sys.stderr."""

    def __init__(self) -> None:
        self._depth = 0
        self._lock = threading.Lock()
        self._saved_stderr: int | None = None
        self._read_fd: int | None = None
        self._thread: threading.Thread | None = None

    def enter(self) -> None:
        with self._lock:
            if self._depth == 0:
                self._start()
            self._depth += 1

    def exit(self) -> None:
        with self._lock:
            self._depth -= 1
            if self._depth <= 0:
                self._depth = 0
                self._shutdown()

    def _start(self) -> None:
        stderr_fd = sys.stderr.fileno()
        self._saved_stderr = os.dup(stderr_fd)
        read_fd, write_fd = os.pipe()
        self._read_fd = read_fd
        os.dup2(write_fd, stderr_fd)
        os.close(write_fd)
        self._thread = threading.Thread(target=self._drain, name="zim-stderr-filter", daemon=True)
        self._thread.start()

    def _drain(self) -> None:
        assert self._saved_stderr is not None and self._read_fd is not None
        pending = ""
        while True:
            try:
                chunk = os.read(self._read_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            pending += chunk.decode("utf-8", errors="replace")
            pending = self._emit_complete_lines(pending, final=False)
        self._emit_complete_lines(pending, final=True)

    def _emit_complete_lines(self, pending: str, *, final: bool) -> str:
        assert self._saved_stderr is not None
        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            if not _should_suppress_text(line):
                os.write(self._saved_stderr, (line + "\n").encode("utf-8", errors="replace"))
        if final and pending and not _should_suppress_text(pending):
            os.write(self._saved_stderr, pending.encode("utf-8", errors="replace"))
            return ""
        return pending

    def _shutdown(self) -> None:
        stderr_fd = sys.stderr.fileno()
        saved = self._saved_stderr
        read_fd = self._read_fd
        thread = self._thread
        if saved is not None:
            os.dup2(saved, stderr_fd)
        if thread is not None:
            thread.join(timeout=5.0)
        if read_fd is not None:
            with contextlib.suppress(OSError):
                os.close(read_fd)
        if saved is not None:
            with contextlib.suppress(OSError):
                os.close(saved)
        self._saved_stderr = None
        self._read_fd = None
        self._thread = None


_stderr_filter = _FdStderrFilter()


@contextlib.contextmanager
def suppress_known_zim_noise() -> Iterator[None]:
    """Drop libzim/Xapian ``No stemming for language 'ku'`` spam during ZIM lookups."""
    _stderr_filter.enter()
    out_filter = _LineFilterWriter(sys.stdout)
    err_filter = _LineFilterWriter(sys.stderr)
    try:
        with contextlib.redirect_stdout(out_filter), contextlib.redirect_stderr(err_filter):
            yield
    finally:
        _stderr_filter.exit()
