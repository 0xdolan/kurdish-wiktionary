import argparse
import asyncio
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from src.catalog.extract import extract_pending_wordlist
from src.catalog.stats import count_zim_titles_sync, fetch_catalog_stats
from src.catalog.sync import sync_wordlist_to_sql
from src.config import get_settings
from src.core.logging import configure_logging
from src.repository.db.base import dispose_engine, get_session_factory, init_engine

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Raw-text catalog: wordlist index + sequential ZIM extract to SQL.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="Show ZIM vs SQL wordlist and entry counts")

    sync_p = sub.add_parser("sync-wordlist", help="Scan ZIM titles into wordlist_titles")
    sync_p.add_argument("--zim-path", type=Path, default=None)

    ext_p = sub.add_parser(
        "extract",
        help="Extract pending wordlist rows into entries (plain text)",
    )
    ext_p.add_argument("--limit", type=int, default=100)
    ext_p.add_argument("--zim-path", type=Path, default=None)

    return parser


async def _run_stats() -> None:
    settings = get_settings()
    zim_count, zim_uuid = count_zim_titles_sync(settings.zim_path)
    stats = None
    try:
        init_engine(settings.database_url)
        session_factory = get_session_factory()
        async with session_factory() as session:
            stats = await fetch_catalog_stats(session, settings.zim_path)
    except Exception as exc:  # noqa: BLE001 — show ZIM stats even if DB down
        console.print(f"[yellow]Database unavailable ({exc}); showing ZIM scan only.[/yellow]")
        stats = None
    finally:
        await dispose_engine()

    if stats is None:
        table = Table(title="Catalog statistics (ZIM only)")
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        table.add_row("ZIM path", str(settings.zim_path.resolve()))
        table.add_row("ZIM UUID", zim_uuid or "—")
        table.add_row("Titles in ZIM (filtered)", str(zim_count))
        console.print(table)
        return

    table = Table(title="Catalog statistics")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("ZIM path", stats.zim_path)
    table.add_row("ZIM UUID", stats.zim_uuid or "—")
    table.add_row("Titles in ZIM (filtered)", str(stats.zim_title_count))
    table.add_row("Wordlist rows (SQL)", str(stats.wordlist_total))
    table.add_row("  pending", str(stats.wordlist_pending))
    table.add_row("  extracted", str(stats.wordlist_extracted))
    table.add_row("  skipped", str(stats.wordlist_skipped))
    table.add_row("  failed", str(stats.wordlist_failed))
    table.add_row("Entry rows (SQL)", str(stats.entries_total))
    console.print(table)


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


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.command == "stats":
        await _run_stats()
    elif args.command == "sync-wordlist":
        zim_path = args.zim_path or settings.zim_path
        await _run_sync(zim_path)
    elif args.command == "extract":
        zim_path = args.zim_path or settings.zim_path
        await _run_extract(zim_path, args.limit)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
