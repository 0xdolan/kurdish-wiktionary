import argparse
import asyncio
import json
import sys

from rich.console import Console

from src.catalog.cli_progress import CatalogJobProgress
from src.config import get_settings
from src.lexicon import service as lexicon_service
from src.lexicon.media_download import close_media_http_client
from src.lexicon.media_run_log import MediaDownloadRunLogger
from src.repository.db.base import dispose_engine, get_session_factory, init_engine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lexicon CLI — SQL + ZIM preview/extract/HTML/media (mirrors /lexicon API).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    preview = sub.add_parser("preview", help="Parse ZIM; no DB write")
    preview.add_argument("word")

    zim_field = sub.add_parser("zim-field", help="One field from ZIM (check before extract)")
    zim_field.add_argument("word")
    zim_field.add_argument(
        "field",
        choices=[
            "definitions",
            "synonyms",
            "antonyms",
            "examples",
            "pronunciations",
            "phonetic_transcriptions",
            "derived_terms",
            "part_of_speech",
        ],
    )

    extract = sub.add_parser("extract", help="Persist entry + HTML + media URLs")
    extract.add_argument("word")
    extract.add_argument("--confirm", action="store_true", required=True)

    get_entry = sub.add_parser("get", help="Load entry from SQL")
    get_entry.add_argument("word")
    get_entry.add_argument("--field", default=None)

    zim_html = sub.add_parser("zim-html", help="Raw HTML from ZIM")
    zim_html.add_argument("word")
    zim_html.add_argument("--section", default=None)

    media_dl = sub.add_parser("media-download", help="Download media for one entry")
    media_dl.add_argument("word")
    media_dl.add_argument("--confirm", action="store_true")
    media_dl.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when local_path file already exists",
    )

    media_all = sub.add_parser(
        "media-download-all",
        help="Download media for all SQL entries with entry_media rows",
    )
    media_all.add_argument("--confirm", action="store_true")
    media_all.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max entries per batch (default 500, max 50000)",
    )
    media_all.add_argument("--offset", type=int, default=0)
    media_all.add_argument(
        "--force",
        action="store_true",
        help="Include entries that already have local_path set",
    )
    media_all.add_argument(
        "--all",
        action="store_true",
        help="Repeat batches until no pending media (requires --confirm)",
    )
    fetch = media_all.add_mutually_exclusive_group()
    fetch.add_argument(
        "--zim-only",
        action="store_true",
        help="Only read media from ZIM archives (maxi/nopic); skip Wikimedia HTTP",
    )
    fetch.add_argument(
        "--remote-only",
        action="store_true",
        help="Only fetch remote URLs; skip items available in ZIM",
    )

    sparse = sub.add_parser("sparse", help="Diagnostics for empty / stale rows")
    sparse.add_argument("--limit", type=int, default=50)
    sparse.add_argument(
        "--mode",
        choices=["all_empty", "missing_relations"],
        default="missing_relations",
    )

    return parser


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    init_engine(settings.database_url)
    factory = get_session_factory()

    if args.command == "preview":
        result = await lexicon_service.preview_entry(settings, args.word)
        print(
            json.dumps(
                {
                    "title": result.title,
                    "counts": result.counts,
                    "warnings": result.warnings,
                    "section_html_keys": result.section_html_keys,
                    "media_count": result.media_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "zim-field":
        payload = await lexicon_service.zim_field_preview(settings, args.word, args.field)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "zim-html":
        if args.section:
            section_payload = await lexicon_service.zim_html_section(
                settings,
                args.word,
                args.section,
            )
            if section_payload is None:
                print("Section not found", file=sys.stderr)
                return 1
            print(section_payload["html"])
            return 0
        full_payload = await lexicon_service.zim_html_full(settings, args.word)
        print(full_payload["html"])
        return 0

    async with factory() as session:
        if args.command == "extract":
            row = await lexicon_service.extract_entry_confirmed(session, settings, args.word)
            print(json.dumps({"entry": row.entry, "entry_id": row.id}, indent=2))
            return 0

        if args.command == "get":
            if args.field:
                values = await lexicon_service.get_entry_field(session, args.word, args.field)
                if values is None:
                    print("Not found", file=sys.stderr)
                    return 1
                print(
                    json.dumps(
                        {"field": args.field, "values": values},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            entry = await lexicon_service.get_entry(session, args.word)
            if entry is None:
                print("Not found", file=sys.stderr)
                return 1
            print(entry.model_dump_json(indent=2))
            return 0

        if args.command == "media-download":
            payload = await lexicon_service.download_entry_media(
                session,
                settings,
                args.word,
                confirm=args.confirm,
                missing_only=not args.force,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.command == "media-download-all":
            if args.all and not args.confirm:
                print("media-download-all --all requires --confirm", file=sys.stderr)
                return 2
            fetch_mode = "all"
            if args.zim_only:
                fetch_mode = "zim_only"
            elif args.remote_only:
                fetch_mode = "remote_only"
            if args.confirm:
                console = Console()
                run_logger = MediaDownloadRunLogger(settings.media_download_state_dir)
                with CatalogJobProgress(console, "Media download") as job:
                    hooks = lexicon_service.build_media_download_rich_hooks(
                        job,
                        run_all=args.all,
                    )
                    payload = await lexicon_service.download_all_entry_media(
                        session,
                        settings,
                        confirm=True,
                        limit=args.limit,
                        offset=args.offset,
                        missing_only=not args.force,
                        run_all=args.all,
                        progress_hooks=hooks,
                        failure_logger=run_logger,
                        fetch_mode=fetch_mode,
                    )
                if payload.get("failures_log"):
                    console.print(
                        f"[dim]Failures log: {payload['failures_log']}[/dim]"
                    )
            else:
                payload = await lexicon_service.download_all_entry_media(
                    session,
                    settings,
                    confirm=False,
                    limit=args.limit,
                    offset=args.offset,
                    missing_only=not args.force,
                    run_all=args.all,
                    fetch_mode=fetch_mode,
                )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.command == "sparse":
            items = await lexicon_service.list_sparse_entries(
                session,
                limit=args.limit,
                mode=args.mode,
            )
            print(json.dumps(items, ensure_ascii=False, indent=2))
            return 0

    return 1


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    async def _run() -> int:
        try:
            return await async_main(args)
        finally:
            await close_media_http_client()
            await dispose_engine()

    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
