import argparse
import asyncio
import json
from pathlib import Path

from src.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.extraction.pipeline import run_extraction_pipeline

logger = get_logger("uvicorn.error")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract Wiktionary entries from a Kiwix ZIM file.",
    )
    parser.add_argument(
        "--zim-path",
        type=Path,
        default=None,
        help="Path to wiktionary_ku_*.zim (defaults to settings.ZIM_PATH)",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=None,
        help="Stop after N successfully parsed entries",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print stats without writing to a database",
    )
    parser.add_argument(
        "--sample-json",
        type=int,
        default=0,
        help="Print up to N parsed entries as JSON lines to stdout",
    )
    return parser


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    zim_path = args.zim_path or settings.zim_path
    if not zim_path.is_file():
        logger.error("ZIM file not found: %s", zim_path)
        return 1

    result = await run_extraction_pipeline(zim_path, max_entries=args.max_entries)
    stats = result.stats
    logger.info(
        "Extraction finished (dry_run=%s): processed=%s skipped=%s failed=%s",
        args.dry_run,
        stats.processed,
        stats.skipped,
        stats.failed,
    )

    if args.sample_json > 0:
        for entry in result.entries[: args.sample_json]:
            print(entry.model_dump_json())

    if args.dry_run:
        print(
            json.dumps(
                {
                    "processed": stats.processed,
                    "skipped": stats.skipped,
                    "failed": stats.failed,
                    "zim_path": str(zim_path.resolve()),
                }
            )
        )
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
