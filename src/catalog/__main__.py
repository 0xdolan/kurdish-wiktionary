import argparse
import asyncio
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from src.catalog.audit import audit_canonical_extraction
from src.catalog.canonical_extract import extract_pending_canonical
from src.catalog.canonical_sync import sync_canonical_wordlist
from src.catalog.extract import extract_pending_wordlist
from src.catalog.stats import fetch_canonical_stats, fetch_catalog_stats, scan_all_zim_stats
from src.catalog.sync import sync_wordlist_to_sql
from src.catalog.zim_paths import resolve_zim_paths
from src.config import get_settings
from src.core.logging import configure_logging
from src.repository.db.base import dispose_engine, get_session_factory, init_engine

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Raw-text catalog: canonical wordlist across ZIMs, HTML parse to UTF-8 plain text."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="ZIM file counts, SQL wordlist, and canonical lemma stats")
    sub.add_parser("audit", help="Verify extracted rows and HTML entity decoding")

    sync_p = sub.add_parser("sync-wordlist", help="Per-ZIM titles into wordlist_titles (legacy)")
    sync_p.add_argument("--zim-path", type=Path, default=None)

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

    ext_p = sub.add_parser("extract", help="Extract pending per-ZIM wordlist rows (legacy)")
    ext_p.add_argument("--limit", type=int, default=100)
    ext_p.add_argument("--zim-path", type=Path, default=None)

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
        "--all",
        action="store_true",
        help="Repeat batches until every pending canonical lemma is processed",
    )
    canon_ext.add_argument(
        "--zim-path",
        type=Path,
        action="append",
        default=None,
    )

    return parser


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


async def _run_sync(zim_path: Path) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()

    with Progress(
        TextColumn("[bold blue]Sync wordlist"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("titles", total=1)

        def on_progress(done: int, total: int) -> None:
            progress.update(task, total=total, completed=done)

        async with session_factory() as session:
            result = await sync_wordlist_to_sql(session, zim_path, progress=on_progress)

    console.print(
        f"[green]Done[/green]: scanned={result.scanned} new_rows={result.inserted} "
        f"(duplicates skipped by unique constraint)"
    )
    await dispose_engine()


async def _run_sync_canonical(zim_paths: list[Path]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()

    with Progress(
        TextColumn("[bold blue]Sync canonical"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("lemmas", total=1)

        def on_progress(done: int, total: int) -> None:
            progress.update(task, total=total, completed=done)

        async with session_factory() as session:
            result = await sync_canonical_wordlist(session, zim_paths, progress=on_progress)

    console.print(
        f"[green]Done[/green]: zims={result.zim_files} unique_lemmas={result.unique_lemmas} "
        f"upserted={result.upserted} in_all_zims={result.in_all_zims} "
        f"only_one_zim={result.in_single_zim}"
    )
    await dispose_engine()


async def _run_extract(zim_path: Path, limit: int) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()

    with Progress(
        TextColumn("[bold blue]Extract"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("entries", total=limit)

        def on_progress(done: int, total: int) -> None:
            progress.update(task, total=total, completed=done)

        async with session_factory() as session:
            result = await extract_pending_wordlist(
                session,
                zim_path,
                limit=limit,
                progress=on_progress,
            )

    console.print(
        f"[green]Batch complete[/green]: attempted={result.attempted} "
        f"extracted={result.extracted} skipped={result.skipped} failed={result.failed}"
    )
    await dispose_engine()


async def _run_extract_canonical(
    zim_paths: list[Path],
    limit: int,
    *,
    run_all: bool = False,
) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()

    batch_index = 0
    totals = {"attempted": 0, "extracted": 0, "skipped": 0, "failed": 0}

    while True:
        batch_index += 1
        label = f"Extract canonical (batch {batch_index})"
        with Progress(
            TextColumn(f"[bold blue]{label}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task_id: TaskID = progress.add_task("entries", total=limit)

            def on_progress(done: int, total: int, *, _task_id: TaskID = task_id) -> None:
                progress.update(_task_id, total=total, completed=done)

            async with session_factory() as session:
                result = await extract_pending_canonical(
                    session,
                    zim_paths,
                    limit=limit,
                    progress=on_progress,
                )

        console.print(
            f"[green]Batch {batch_index}[/green]: attempted={result.attempted} "
            f"extracted={result.extracted} skipped={result.skipped} failed={result.failed}"
        )
        for key in totals:
            totals[key] += getattr(result, key)

        if not run_all or result.attempted == 0:
            break

    if run_all and batch_index > 1:
        console.print(
            "[bold green]Full run complete[/bold green]: "
            f"batches={batch_index} attempted={totals['attempted']} "
            f"extracted={totals['extracted']} skipped={totals['skipped']} "
            f"failed={totals['failed']}"
        )

    await dispose_engine()


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()

    if args.command == "stats":
        await _run_stats()
    elif args.command == "audit":
        await _run_audit()
    elif args.command == "sync-wordlist":
        path = args.zim_path or settings.zim_path
        await _run_sync(path)
    elif args.command == "sync-canonical":
        paths = resolve_zim_paths(settings, args.zim_path)
        await _run_sync_canonical(paths)
    elif args.command == "extract":
        path = args.zim_path or settings.zim_path
        await _run_extract(path, args.limit)
    elif args.command == "extract-canonical":
        paths = resolve_zim_paths(settings, args.zim_path)
        await _run_extract_canonical(paths, args.limit, run_all=args.all)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
