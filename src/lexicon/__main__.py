import argparse
import asyncio
import json
import sys

from src.config import get_settings
from src.lexicon import service as lexicon_service
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
            await dispose_engine()

    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
