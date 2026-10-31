"""Release CLI: ``python -m src.dataset <stage>``. See docs/DATASET_LOCAL_GUIDE.md."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import time
from pathlib import Path

from rich.console import Console

from src.dataset import bundle, exporters, mdict_build, quality, verify
from src.dataset import media as media_stage
from src.dataset.build_db import build_database, connect

ROOT = Path("build/release")
MAXI = Path("zim/wiktionary/wiktionary_ku_all_maxi_2026-08.zim")
NOPIC = Path("zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim")
LEGACY_MEDIA = Path("build/media")

console = Console()


def _database(args: argparse.Namespace) -> Path:
    return Path(args.root) / "sql" / "wiktionary.sqlite"


def _store(args: argparse.Namespace) -> Path:
    return Path(args.root) / "media"


def _archives(args: argparse.Namespace) -> list[Path]:
    return [Path(args.maxi), Path(args.nopic)]


def _stage_parse(args: argparse.Namespace) -> None:
    started = time.monotonic()
    last = [0.0]

    def progress(flavour: str, done: int, total: int) -> None:
        if time.monotonic() - last[0] > 30 or done == total:
            last[0] = time.monotonic()
            console.print(f"{flavour}: {done}/{total} chunks ({time.monotonic() - started:.0f}s)")

    licences = media_stage.saved_licences(_database(args))
    stats = build_database(
        database=_database(args),
        maxi=Path(args.maxi),
        nopic=Path(args.nopic),
        progress=progress,
    )
    conn = connect(_database(args))
    conn.executemany("INSERT OR REPLACE INTO build_meta VALUES (?, ?)", list(stats.items()))
    media_stage.restore_licences(conn, licences)
    conn.commit()
    console.print(stats)


def _stage_media_extract(args: argparse.Namespace) -> None:
    conn = connect(_database(args))
    added = media_stage.register_zim_assets(conn, _archives(args))
    media_stage.assign_roles_and_usage(conn)
    console.print(f"registered {added} ZIM files no page references")
    result = media_stage.extract_from_zim(conn, _store(args), _archives(args))
    found = media_stage.rediscover_store(conn, _store(args))
    adopted = media_stage.adopt_previous_downloads(conn, _store(args), LEGACY_MEDIA)
    console.print({**result, "already_in_store": found, "adopted_previous_downloads": adopted})


def _stage_media_audit(args: argparse.Namespace) -> None:
    conn = connect(_database(args))
    report = media_stage.audit(conn, _store(args))
    media_stage.write_audit_files(report, Path(args.root) / "quality")
    summary = {key: value for key, value in report.items() if key != "missing_items"}
    console.print_json(json.dumps(summary, ensure_ascii=False))


def _stage_media_download(args: argparse.Namespace) -> None:
    conn = connect(_database(args))
    # WAL lets other stages read while this runs for hours. Close checkpoints it back.
    conn.execute("PRAGMA journal_mode=WAL")

    def progress(counts: dict[str, int], total: int) -> None:
        console.print(f"{counts} of {total}")

    result = asyncio.run(
        media_stage.download_missing(conn, _store(args), limit=args.limit, progress=progress)
    )
    console.print(result)


def _stage_media_licences(args: argparse.Namespace) -> None:
    conn = connect(_database(args))

    def progress(done: int, total: int) -> None:
        console.print(f"licences: {done}/{total} file names")

    console.print(asyncio.run(media_stage.fetch_licences(conn, progress=progress)))


def _log(message: str) -> None:
    console.print(f"[{time.strftime('%H:%M:%S')}] {message}", markup=False)


def _stage_export(args: argparse.Namespace) -> None:
    root = Path(args.root)
    conn = connect(_database(args))
    wanted = args.only or ["sql", "parquet", "csv", "jsonl", "excel"]
    if "sql" in wanted:
        exporters.export_sql(conn, root / "sql", _log)
    if "parquet" in wanted:
        exporters.export_parquet(conn, root / "parquet", _log)
    if "csv" in wanted:
        exporters.export_csv(conn, root / "csv", _log)
    if "jsonl" in wanted:
        count = exporters.export_jsonl(_database(args), root / "jsonl" / "entries.jsonl.gz", _log)
        _log(f"jsonl: {count} entries")
    if "excel" in wanted:
        exporters.export_excel(conn, root / "excel", _log)


def _stage_mdict(args: argparse.Namespace) -> None:
    root = Path(args.root)
    staging = root / "mdict" / "staging"
    dict_txt = staging / "dict.txt"
    counts = mdict_build.write_dict_txt(_database(args), dict_txt, _log)
    _log(f"dict.txt: {counts}")
    resources, audio = mdict_build.stage_resources(_store(args), Path("assets/mdict"), staging)
    if args.txt_only:
        return
    conn = connect(_database(args))
    entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    zim_date = bundle.zim_provenance([Path(args.maxi)])[0]["date"]
    templates = mdict_build.write_templates(
        staging / "templates",
        version=bundle.DATASET_VERSION,
        zim_date=zim_date,
        entries=entries,
    )
    outputs = mdict_build.pack_all(
        dict_txt=dict_txt,
        resources=resources,
        resources_audio=audio,
        templates=templates,
        output_dir=root / "mdict",
        log=root / "logs" / "mdict-pack.log",
    )
    for path in outputs:
        _log(f"packed {path} ({path.stat().st_size / 1e6:,.1f} MB)")


def _stage_quality(args: argparse.Namespace) -> None:
    conn = connect(_database(args))
    report = quality.write_report(conn, bundle.read_build_meta(conn), Path(args.root) / "quality")
    summary = {key: report[key] for key in ("row_counts", "coverage", "parse_errors")}
    console.print_json(json.dumps(summary, ensure_ascii=False))


def _stage_verify(args: argparse.Namespace) -> None:
    conn = sqlite3.connect(f"file:{_database(args)}?mode=ro", uri=True)
    if args.write_expected:
        verify.write_expected(conn, _archives(args))
        console.print(f"Wrote {verify.EXPECTED}")
        return
    problems = verify.compare(conn, _archives(args))
    if problems:
        for problem in problems:
            console.print(f"DIFFERS: {problem}", markup=False)
        raise SystemExit(1)
    console.print("MATCH: ZIM files, row counts and table contents equal the published release.")


def _stage_bundle(args: argparse.Namespace) -> None:
    root = Path(args.root)
    conn = connect(_database(args))
    bundle.finalize_database(conn)
    report = quality.write_report(conn, bundle.read_build_meta(conn), root / "quality")
    conn.close()
    result = bundle.assemble(
        root=root,
        report=report,
        zims=bundle.zim_provenance(_archives(args)),
        output=root / "kaggle",
        notebook=Path("assets/kaggle/kurdish_wiktionary_starter.ipynb"),
    )
    console.print(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="Release output folder")
    parser.add_argument("--maxi", default=str(MAXI), help="Newest ZIM (with images)")
    parser.add_argument("--nopic", default=str(NOPIC), help="Older ZIM (adds pages only)")
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("parse", help="ZIM -> section-aware SQLite").set_defaults(func=_stage_parse)
    sub.add_parser("media-extract", help="Copy all ZIM media; adopt old downloads").set_defaults(
        func=_stage_media_extract
    )
    sub.add_parser("media-audit", help="Compare references, table and disk").set_defaults(
        func=_stage_media_audit
    )
    download = sub.add_parser("media-download", help="Fetch missing files from Wikimedia")
    download.add_argument("--limit", type=int, default=None)
    download.set_defaults(func=_stage_media_download)
    sub.add_parser("media-licences", help="Per-file licence from Commons").set_defaults(
        func=_stage_media_licences
    )
    export = sub.add_parser("export", help="SQL, Parquet, CSV, JSONL and Excel")
    export.add_argument(
        "--only",
        action="append",
        choices=["sql", "parquet", "csv", "jsonl", "excel"],
        help="Repeat to choose formats (default: all)",
    )
    export.set_defaults(func=_stage_export)
    mdict = sub.add_parser("mdict", help="dict.txt + resources, then pack MDX/MDD")
    mdict.add_argument("--txt-only", action="store_true", help="Stop before packing")
    mdict.set_defaults(func=_stage_mdict)
    sub.add_parser("quality", help="Write quality/report.json and QUALITY.md").set_defaults(
        func=_stage_quality
    )
    sub.add_parser("bundle", help="Assemble the Kaggle folder").set_defaults(func=_stage_bundle)
    check = sub.add_parser("verify", help="Compare this build with the published release")
    check.add_argument(
        "--write-expected",
        action="store_true",
        help="Record this build as the baseline (after changing the parser on purpose)",
    )
    check.set_defaults(func=_stage_verify)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
