"""Steady Rich progress for catalog CLI commands (batch + item counters, live stats)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)


@dataclass(frozen=True, slots=True)
class ProgressTick:
    done: int
    total: int
    extracted: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class BatchRunTotals:
    batches: int = 0
    attempted: int = 0
    extracted: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class CatalogJobProgress:
    """Single progress bar for one job; supports multi-batch extract-canonical --all."""

    console: Console
    job_title: str
    _progress: Progress | None = field(default=None, init=False, repr=False)
    _task_id: TaskID | None = field(default=None, init=False, repr=False)
    run_totals: BatchRunTotals = field(default_factory=BatchRunTotals)

    def __enter__(self) -> CatalogJobProgress:
        self._progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TextColumn("[cyan]{task.fields[batch_line]}"),
            TextColumn("•"),
            TextColumn(
                "[green]ok={task.fields[ok]}[/green] "
                "[yellow]skip={task.fields[skip]}[/yellow] "
                "[red]fail={task.fields[fail]}[/red]"
            ),
            TimeRemainingColumn(),
            console=self.console,
            refresh_per_second=8,
            transient=False,
        )
        self._progress.start()
        return self

    def __exit__(self, *args: object) -> None:
        if self._progress is not None:
            self._progress.stop()

    @staticmethod
    def estimate_batch_count(pending: int, batch_size: int) -> int:
        if pending <= 0:
            return 0
        return max(1, math.ceil(pending / max(1, batch_size)))

    def start_batch(
        self,
        *,
        batch_index: int,
        batch_total: int | None,
        item_total: int,
        corpus_pending: int | None = None,
    ) -> None:
        assert self._progress is not None
        if self._task_id is not None:
            self._progress.remove_task(self._task_id)

        batch_line = f"batch {batch_index}"
        if batch_total is not None and batch_total > 0:
            batch_line = f"batch {batch_index}/{batch_total}"
        if corpus_pending is not None:
            batch_line = f"{batch_line} · corpus pending {corpus_pending:,}"

        self._task_id = self._progress.add_task(
            self.job_title,
            total=max(1, item_total),
            completed=0,
            batch_line=batch_line,
            ok=str(self.run_totals.extracted),
            skip=str(self.run_totals.skipped),
            fail=str(self.run_totals.failed),
        )

    def on_tick(self, tick: ProgressTick) -> None:
        assert self._progress is not None and self._task_id is not None
        self._progress.update(
            self._task_id,
            total=max(1, tick.total),
            completed=tick.done,
            ok=str(self.run_totals.extracted + tick.extracted),
            skip=str(self.run_totals.skipped + tick.skipped),
            fail=str(self.run_totals.failed + tick.failed),
        )

    def finish_batch(
        self,
        *,
        attempted: int,
        extracted: int,
        skipped: int,
        failed: int,
    ) -> None:
        self.run_totals.batches += 1
        self.run_totals.attempted += attempted
        self.run_totals.extracted += extracted
        self.run_totals.skipped += skipped
        self.run_totals.failed += failed
        assert self._progress is not None and self._task_id is not None
        self._progress.update(
            self._task_id,
            ok=str(self.run_totals.extracted),
            skip=str(self.run_totals.skipped),
            fail=str(self.run_totals.failed),
        )
