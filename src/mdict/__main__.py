import argparse
import asyncio
from pathlib import Path

from src.config import DataSource, get_settings
from src.core.logging import configure_logging, get_logger
from src.mdict.export import build_mdict_artifacts, collect_entries
from src.repository.db.base import dispose_engine, get_session_factory, init_engine

logger = get_logger("uvicorn.error")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Wiktionary entries to MDX/MDD.")
    parser.add_argument(
        "--data-source",
        choices=[DataSource.ZIM.value, DataSource.SQL.value],
        default=None,
        help="Entry source (default: settings.DEFAULT_DATA_SOURCE)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: settings.MDX_WORK_DIR)",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum entries to export")
    parser.add_argument(
        "--include-media",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Build MDD resource package",
    )
    parser.add_argument("--title", type=Path, default=None, help="title.html override")
    parser.add_argument("--description", type=Path, default=None, help="description.html override")
    return parser


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    data_source = (
        DataSource(args.data_source) if args.data_source else settings.default_data_source
    )
    output_dir = args.output_dir or settings.mdx_work_dir
    include_media = (
        settings.mdx_include_media if args.include_media is None else args.include_media
    )

    try:
        if data_source is DataSource.SQL:
            init_engine(settings.database_url)
            session_factory = get_session_factory()
            async with session_factory() as db_session:
                entries = await collect_entries(
                    settings,
                    data_source=data_source,
                    limit=args.limit,
                    session=db_session,
                    zim_reader=None,
                )
                artifacts = await build_mdict_artifacts(
                    settings,
                    entries=entries,
                    output_dir=output_dir,
                    include_media=include_media,
                    title_html=args.title,
                    description_html=args.description,
                )
        else:
            entries = await collect_entries(
                settings,
                data_source=data_source,
                limit=args.limit,
                session=None,
                zim_reader=None,
            )
            artifacts = await build_mdict_artifacts(
                settings,
                entries=entries,
                output_dir=output_dir,
                include_media=include_media,
                title_html=args.title,
                description_html=args.description,
            )
    finally:
        await dispose_engine()

    logger.info(
        "MDX export complete: entries=%s mdx=%s",
        artifacts.entry_count,
        artifacts.mdx_path,
    )
    print(artifacts.manifest_path.read_text(encoding="utf-8"))
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
