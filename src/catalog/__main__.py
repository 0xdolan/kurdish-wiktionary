import argparse
import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from rich.console import Console
from rich.table import Table
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.audit import audit_canonical_extraction
from src.catalog.canonical_extract import extract_pending_canonical
from src.catalog.canonical_sync import sync_canonical_wordlist
from src.catalog.checkpoint import (
    CatalogCheckpoint,
    clear_checkpoint,
    fingerprint_single_zim,
    fingerprint_zim_paths,
    load_checkpoint,
    save_checkpoint,
)
from src.catalog.cli_args import add_extract_arguments, add_resume_arguments
from src.catalog.cli_progress import CatalogJobProgress, ProgressTick
from src.catalog.extract import extract_pending_wordlist
from src.catalog.outcomes import build_outcome_report, report_to_json
from src.catalog.resume_ops import requeue_failed_canonical, requeue_failed_wordlist
from src.catalog.run_log import ExtractRunLogger
from src.catalog.stats import fetch_canonical_stats, fetch_catalog_stats, scan_all_zim_stats
from src.catalog.sync import sync_wordlist_to_sql
from src.catalog.zim_paths import resolve_zim_paths
from src.config import get_settings
from src.core.logging import configure_logging
from src.extraction.zim_reader import ZimReader
from src.repository.db.base import dispose_engine, get_session_factory, init_engine

# Progress on stdout; stderr is filtered during libzim lookups (see stream_filter).
console = Console(stderr=False)


class _ExtractBatchRunner(Protocol):
    async def requeue_failed(self, session: AsyncSession) -> int: ...

    async def run_batch(
        self,
        session: AsyncSession,
        *,
        limit: int,
        include_failed: bool,
        progress: Callable[[ProgressTick], None] | None,
    ) -> Any: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Raw-text catalog: canonical wordlist across ZIMs, HTML parse to UTF-8 plain text."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="ZIM file counts, SQL wordlist, and canonical lemma stats")
    sub.add_parser("audit", help="Verify extracted rows and HTML entity decoding")

    report_p = sub.add_parser(
        "report",
        help="Summarize skipped/failed lemmas with reasons (SQL + optional export)",
    )
    report_p.add_argument(
        "--scope",
        choices=["canonical", "wordlist"],
        default="canonical",
    )
    report_p.add_argument(
        "--status",
        choices=["both", "skipped", "failed"],
        default="both",
    )
    report_p.add_argument("--limit", type=int, default=100, help="Max detail rows in output")
    report_p.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Write full JSON report to this path",
    )

    sync_p = sub.add_parser("sync-wordlist", help="Per-ZIM titles into wordlist_titles (legacy)")
    sync_p.add_argument("--zim-path", type=Path, default=None)
    add_resume_arguments(sync_p)

    canon_sync = sub.add_parser(
        "sync-canonical",
        help="Merge lemma titles from all configured ZIMs into canonical_lemmas",
    )
    canon_sync.add_argument(
        "--zim-path",
        type=Path,
        action="append",
        default=None,
        help="Repeat for each ZIM (default: ZIM_PATHS or ZIM_PATH)",
    )
    add_resume_arguments(canon_sync)

    ext_p = sub.add_parser("extract", help="Extract pending per-ZIM wordlist rows (legacy)")
    ext_p.add_argument("--limit", type=int, default=100)
    ext_p.add_argument("--zim-path", type=Path, default=None)
    add_extract_arguments(ext_p)

    canon_ext = sub.add_parser(
        "extract-canonical",
        help="For each canonical lemma, parse HTML from every available ZIM and merge",
    )
    canon_ext.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Batch size (max rows per invocation; use 5000–10000 for throughput)",
    )
    canon_ext.add_argument(
        "--zim-path",
        type=Path,
        action="append",
        default=None,
    )
    add_extract_arguments(canon_ext)

    return parser


def _init_checkpoint(
    *,
    state_dir: Path,
    command: str,
    fingerprint: str,
    limit: int,
    run_all: bool,
    resume: bool,
) -> CatalogCheckpoint:
    if not resume:
        clear_checkpoint(state_dir, command, fingerprint)
        return CatalogCheckpoint(
            command=command,
            fingerprint=fingerprint,
            limit=limit,
            run_all=run_all,
        )
    loaded = load_checkpoint(state_dir, command, fingerprint)
    if loaded is None:
        return CatalogCheckpoint(
            command=command,
            fingerprint=fingerprint,
            limit=limit,
            run_all=run_all,
        )
    if loaded.limit != limit or loaded.run_all != run_all:
        console.print(
            "[yellow]Checkpoint ignored[/yellow] (limit or --all changed); starting fresh totals."
        )
        clear_checkpoint(state_dir, command, fingerprint)
        return CatalogCheckpoint(
            command=command,
            fingerprint=fingerprint,
            limit=limit,
            run_all=run_all,
        )
    console.print(
        f"[cyan]Resuming[/cyan] {command}: batch={loaded.batch_index}, "
        f"items={loaded.totals.attempted:,}, upsert_offset={loaded.upsert_offset:,}"
    )
    return loaded


def _persist_checkpoint(state_dir: Path, checkpoint: CatalogCheckpoint) -> None:
    save_checkpoint(state_dir, checkpoint)


async def _run_stats() -> None:
    settings = get_settings()
    zim_paths = resolve_zim_paths(settings)

    zim_table = Table(title="ZIM archives (filtered title counts)")
    zim_table.add_column("Path")
    zim_table.add_column("UUID")
    zim_table.add_column("Titles", justify="right")
    for row in scan_all_zim_stats(zim_paths):
        zim_table.add_row(row.path, row.uuid or "—", str(row.title_count))
    console.print(zim_table)

    try:
        init_engine(settings.database_url)
        session_factory = get_session_factory()
        async with session_factory() as session:
            legacy = await fetch_catalog_stats(session, settings.zim_path)
            canonical = await fetch_canonical_stats(
                session,
                configured_zim_count=len(zim_paths),
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Database unavailable ({exc}).[/yellow]")
        await dispose_engine()
        return
    finally:
        await dispose_engine()

    sql_table = Table(title="SQL — per-ZIM wordlist_titles (legacy index)")
    sql_table.add_column("Metric")
    sql_table.add_column("Value", justify="right")
    sql_table.add_row("Primary ZIM (settings)", legacy.zim_path)
    sql_table.add_row("Wordlist rows (all UUIDs)", str(legacy.wordlist_total))
    sql_table.add_row("  pending", str(legacy.wordlist_pending))
    sql_table.add_row("  extracted", str(legacy.wordlist_extracted))
    sql_table.add_row("Entry rows", str(legacy.entries_total))
    console.print(sql_table)

    canon_table = Table(title="SQL — canonical_lemmas (use for extract-canonical)")
    canon_table.add_column("Metric")
    canon_table.add_column("Value", justify="right")
    canon_table.add_row("Unique lemmas", str(canonical.total))
    canon_table.add_row("  pending", str(canonical.pending))
    canon_table.add_row("  extracted", str(canonical.extracted))
    canon_table.add_row("  skipped", str(canonical.skipped))
    canon_table.add_row("  failed", str(canonical.failed))
    canon_table.add_row(f"In all {len(zim_paths)} ZIM(s)", str(canonical.in_all_configured_zims))
    canon_table.add_row("In exactly one ZIM", str(canonical.in_one_zim_only))
    canon_table.add_row("Entry rows (total)", str(canonical.entries_total))
    console.print(canon_table)


async def _run_report(
    *,
    scope: str,
    status_filter: str,
    limit: int,
    export_path: Path | None,
) -> None:
    settings = get_settings()
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    async with session_factory() as session:
        report = await build_outcome_report(
            session,
            scope=scope,
            status_filter=status_filter,
            row_limit=limit,
        )
    await dispose_engine()

    summary = Table(title=f"Extract outcomes ({scope})")
    summary.add_column("Status")
    summary.add_column("Category")
    summary.add_column("Count", justify="right")
    summary.add_column("Samples")
    for item in report.categories:
        samples = ", ".join(item.sample_titles[:3]) or "—"
        summary.add_row(item.status, item.category, str(item.count), samples)
    console.print(summary)
    console.print(
        f"[bold]Totals[/bold]: skipped={report.skipped_total:,} failed={report.failed_total:,}"
    )

    if export_path is not None:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(report_to_json(report), encoding="utf-8")
        console.print(f"[green]Exported[/green] {export_path}")

    if report.failed_total:
        console.print(
            "[cyan]Retry failed[/cyan]: "
            "catalog extract-canonical --retry-failed --resume --all "
            "(or extract for wordlist scope)"
        )


async def _run_audit() -> None:
    settings = get_settings()
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    async with session_factory() as session:
        report = await audit_canonical_extraction(session)
    await dispose_engine()

    table = Table(title="Extraction audit")
    table.add_column("Check")
    table.add_column("Result", justify="right")
    table.add_row("Canonical lemmas", str(report.canonical_total))
    table.add_row("Extracted", str(report.canonical_extracted))
    table.add_row("Pending", str(report.canonical_pending))
    table.add_row("Extracted but missing entry_id", str(report.extracted_missing_entry_id))
    table.add_row(
        "Definitions with HTML entities (sample scan)",
        str(report.entries_with_html_entities),
    )
    console.print(table)
    if report.sample_entity_lemmas:
        samples = ", ".join(report.sample_entity_lemmas)
        console.print(f"[yellow]Sample lemmas with entities:[/yellow] {samples}")


async def _run_sync(zim_path: Path, *, resume: bool) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    fingerprint = fingerprint_single_zim(zim_path)
    checkpoint = _init_checkpoint(
        state_dir=settings.catalog_state_dir,
        command="sync-wordlist",
        fingerprint=fingerprint,
        limit=0,
        run_all=False,
        resume=resume,
    )

    with CatalogJobProgress(console, "Sync wordlist") as job:
        job.run_totals = checkpoint.totals
        started = False

        def on_progress(tick: ProgressTick) -> None:
            nonlocal started
            if not started:
                job.start_batch(
                    batch_index=1,
                    batch_total=1,
                    item_total=tick.total,
                    corpus_pending=tick.total,
                )
                started = True
            job.on_tick(tick)
            checkpoint.upsert_offset = tick.done
            _persist_checkpoint(settings.catalog_state_dir, checkpoint)

        async with session_factory() as session:
            result = await sync_wordlist_to_sql(
                session,
                zim_path,
                upsert_start_offset=checkpoint.upsert_offset,
                progress=on_progress,
            )

        job.finish_batch(
            attempted=result.scanned,
            extracted=result.inserted,
            skipped=0,
            failed=0,
        )
        checkpoint.totals = job.run_totals

    clear_checkpoint(settings.catalog_state_dir, "sync-wordlist", fingerprint)
    console.print(
        f"[green]Done[/green]: scanned={result.scanned:,} new_rows={result.inserted:,} "
        f"(duplicates skipped by unique constraint)"
    )
    await dispose_engine()


async def _run_sync_canonical(zim_paths: list[Path], *, resume: bool) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    fingerprint = fingerprint_zim_paths(zim_paths)
    checkpoint = _init_checkpoint(
        state_dir=settings.catalog_state_dir,
        command="sync-canonical",
        fingerprint=fingerprint,
        limit=0,
        run_all=False,
        resume=resume,
    )

    with CatalogJobProgress(console, "Sync canonical") as job:
        job.run_totals = checkpoint.totals
        started = False

        def on_progress(tick: ProgressTick) -> None:
            nonlocal started
            if not started:
                job.start_batch(
                    batch_index=1,
                    batch_total=1,
                    item_total=tick.total,
                    corpus_pending=tick.total,
                )
                started = True
            job.on_tick(tick)
            checkpoint.upsert_offset = tick.done
            _persist_checkpoint(settings.catalog_state_dir, checkpoint)

        async with session_factory() as session:
            result = await sync_canonical_wordlist(
                session,
                zim_paths,
                upsert_start_offset=checkpoint.upsert_offset,
                progress=on_progress,
            )

        job.finish_batch(
            attempted=result.unique_lemmas,
            extracted=result.upserted,
            skipped=0,
            failed=0,
        )

    clear_checkpoint(settings.catalog_state_dir, "sync-canonical", fingerprint)
    console.print(
        f"[green]Done[/green]: zims={result.zim_files} unique_lemmas={result.unique_lemmas:,} "
        f"upserted={result.upserted:,} in_all_zims={result.in_all_zims:,} "
        f"only_one_zim={result.in_single_zim:,}"
    )
    await dispose_engine()


async def _run_extract_loop(
    *,
    settings: Any,
    session_factory: Any,
    fingerprint: str,
    command: str,
    limit: int,
    run_all: bool,
    resume: bool,
    retry_failed: bool,
    job_title: str,
    pending_count_fn: Callable[[AsyncSession], Awaitable[int]],
    extract_fn: _ExtractBatchRunner,
) -> None:
    checkpoint = _init_checkpoint(
        state_dir=settings.catalog_state_dir,
        command=command,
        fingerprint=fingerprint,
        limit=limit,
        run_all=run_all,
        resume=resume,
    )
    batch_index = checkpoint.batch_index
    retried_failed = False

    async with session_factory() as session:
        if retry_failed and not retried_failed:
            requeued = await extract_fn.requeue_failed(session)
            if requeued:
                console.print(f"[cyan]Re-queued {requeued:,} failed rows[/cyan]")
            retried_failed = True
        initial_pending = await pending_count_fn(session)
    if checkpoint.pending_at_start is None:
        checkpoint.pending_at_start = initial_pending

    pending_start = checkpoint.pending_at_start
    batch_total = (
        CatalogJobProgress.estimate_batch_count(pending_start, limit) if run_all else 1
    )
    scope = "canonical" if command == "extract-canonical" else "wordlist"
    run_logger = ExtractRunLogger(
        settings.catalog_state_dir,
        command=command,
        fingerprint=fingerprint,
    )

    with CatalogJobProgress(console, job_title) as job:
        job.run_totals = checkpoint.totals

        while True:
            batch_index += 1
            async with session_factory() as session:
                pending_now = await pending_count_fn(session)
                item_total = min(limit, max(1, pending_now)) if pending_now else limit

                job.start_batch(
                    batch_index=batch_index,
                    batch_total=batch_total if run_all else 1,
                    item_total=item_total,
                    corpus_pending=pending_now,
                )

                def on_progress(tick: ProgressTick) -> None:
                    job.on_tick(tick)

                result = await extract_fn.run_batch(
                    session,
                    limit=limit,
                    include_failed=False,
                    progress=on_progress,
                )

            job.finish_batch(
                attempted=result.attempted,
                extracted=result.extracted,
                skipped=result.skipped,
                failed=result.failed,
            )
            run_logger.log_batch(
                batch_index=batch_index,
                attempted=result.attempted,
                extracted=result.extracted,
                skipped=result.skipped,
                failed=result.failed,
                outcomes=getattr(result, "outcomes", []),
            )

            checkpoint.batch_index = batch_index
            checkpoint.totals = job.run_totals
            checkpoint.pending_at_start = pending_start
            _persist_checkpoint(settings.catalog_state_dir, checkpoint)

            if not run_all or result.attempted == 0:
                break

            if run_all and pending_start:
                remaining = max(0, pending_start - job.run_totals.attempted)
                batch_total = CatalogJobProgress.estimate_batch_count(remaining, limit)

    totals = job.run_totals
    async with session_factory() as session:
        pending_left = await pending_count_fn(session)
        outcome_report = await build_outcome_report(
            session,
            scope=scope,
            status_filter="both",
            row_limit=500,
        )
    report_path = run_logger.run_dir / "outcome-report.json"
    report_path.write_text(report_to_json(outcome_report), encoding="utf-8")
    manifest_path = run_logger.finalize(
        totals={
            "batches": totals.batches,
            "attempted": totals.attempted,
            "extracted": totals.extracted,
            "skipped": totals.skipped,
            "failed": totals.failed,
        },
        pending_left=pending_left,
        report_path=str(report_path),
    )

    if run_all and pending_left == 0:
        clear_checkpoint(settings.catalog_state_dir, command, fingerprint)
    elif not run_all:
        console.print(
            f"[dim]Checkpoint saved — rerun with --resume to continue "
            f"({pending_left:,} pending)[/dim]"
        )

    if run_all:
        console.print(
            "[bold green]Run complete[/bold green]: "
            f"batches={totals.batches} items={totals.attempted:,} "
            f"extracted={totals.extracted:,} skipped={totals.skipped:,} "
            f"failed={totals.failed:,} pending_left={pending_left:,}"
        )
    else:
        console.print(
            f"[green]Batch {batch_index}/{batch_total}[/green]: attempted={totals.attempted} "
            f"extracted={totals.extracted} skipped={totals.skipped} failed={totals.failed} "
            f"(pending {pending_left:,})"
        )
    console.print(
        f"[dim]Run log[/dim]: {manifest_path}  "
        f"[dim]outcomes[/dim]: skipped={outcome_report.skipped_total:,} "
        f"failed={outcome_report.failed_total:,} → {report_path}"
    )
    if outcome_report.failed_total:
        console.print(
            "[cyan]Retry failed[/cyan]: "
            f"catalog {command} --retry-failed --resume" + (" --all" if run_all else "")
        )


async def _run_extract(
    zim_path: Path,
    limit: int,
    *,
    run_all: bool,
    resume: bool,
    retry_failed: bool,
) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    fingerprint = fingerprint_single_zim(zim_path)
    zim_uuid = str(ZimReader(zim_path).metadata().uuid)

    class _ExtractFn:
        @staticmethod
        async def requeue_failed(session: AsyncSession) -> int:
            return await requeue_failed_wordlist(session, zim_uuid=zim_uuid)

        @staticmethod
        async def run_batch(
            session: AsyncSession,
            *,
            limit: int,
            include_failed: bool,
            progress: Callable[[ProgressTick], None] | None,
        ) -> Any:
            return await extract_pending_wordlist(
                session,
                zim_path,
                limit=limit,
                include_failed=include_failed,
                progress=progress,
            )

    async def pending_count(session: AsyncSession) -> int:
        stats = await fetch_catalog_stats(session, zim_path)
        return stats.wordlist_pending

    await _run_extract_loop(
        settings=settings,
        session_factory=session_factory,
        fingerprint=fingerprint,
        command="extract",
        limit=limit,
        run_all=run_all,
        resume=resume,
        retry_failed=retry_failed,
        job_title="Extract wordlist",
        pending_count_fn=pending_count,
        extract_fn=_ExtractFn,
    )
    await dispose_engine()


async def _run_extract_canonical(
    zim_paths: list[Path],
    limit: int,
    *,
    run_all: bool,
    resume: bool,
    retry_failed: bool,
) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    fingerprint = fingerprint_zim_paths(zim_paths)

    class _ExtractFn:
        @staticmethod
        async def requeue_failed(session: AsyncSession) -> int:
            return await requeue_failed_canonical(session)

        @staticmethod
        async def run_batch(
            session: AsyncSession,
            *,
            limit: int,
            include_failed: bool,
            progress: Callable[[ProgressTick], None] | None,
        ) -> Any:
            return await extract_pending_canonical(
                session,
                zim_paths,
                limit=limit,
                include_failed=include_failed,
                progress=progress,
            )

    async def pending_count(session: AsyncSession) -> int:
        stats = await fetch_canonical_stats(session, configured_zim_count=len(zim_paths))
        return stats.pending

    await _run_extract_loop(
        settings=settings,
        session_factory=session_factory,
        fingerprint=fingerprint,
        command="extract-canonical",
        limit=limit,
        run_all=run_all,
        resume=resume,
        retry_failed=retry_failed,
        job_title="Extract canonical",
        pending_count_fn=pending_count,
        extract_fn=_ExtractFn,
    )
    await dispose_engine()


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()

    if args.command == "stats":
        await _run_stats()
    elif args.command == "audit":
        await _run_audit()
    elif args.command == "report":
        await _run_report(
            scope=args.scope,
            status_filter=args.status,
            limit=args.limit,
            export_path=args.export,
        )
    elif args.command == "sync-wordlist":
        path = args.zim_path or settings.zim_path
        await _run_sync(path, resume=args.resume)
    elif args.command == "sync-canonical":
        paths = resolve_zim_paths(settings, args.zim_path)
        await _run_sync_canonical(paths, resume=args.resume)
    elif args.command == "extract":
        path = args.zim_path or settings.zim_path
        await _run_extract(
            path,
            args.limit,
            run_all=args.all,
            resume=args.resume,
            retry_failed=args.retry_failed,
        )
    elif args.command == "extract-canonical":
        paths = resolve_zim_paths(settings, args.zim_path)
        await _run_extract_canonical(
            paths,
            args.limit,
            run_all=args.all,
            resume=args.resume,
            retry_failed=args.retry_failed,
        )
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
