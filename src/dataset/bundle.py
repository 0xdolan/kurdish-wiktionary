"""Assemble the release folder for Kaggle: docs, metadata, archives, manifest and checksums."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.dataset.schema import TABLES
from src.dataset.sections import POS_LABELS, SECTION_LABELS

DATASET_VERSION = "1.0.0"
# The existing Kaggle dataset. Its URL can only be changed in Kaggle's web settings, not by API.
DATASET_SLUG = "wiktionary-wordlists"
DATASET_TITLE = "Kurdish Wiktionary Dataset"
KAGGLE_OWNER = os.environ.get("KAGGLE_OWNER", "zeroxdolan")
_TEMPLATES = Path(__file__).resolve().parents[2] / "assets" / "dataset"
_SAMPLE_RECORDS = 200
_KEYWORDS = ["linguistics", "nlp", "text mining", "languages", "audio"]
_COVER = (
    Path(__file__).resolve().parents[2] / "assets" / "brand" / "export" / "kaggle-cover-dark.png"
)
_SOURCES = (
    "Wîkîferheng, the Kurdish Wiktionary ([ku.wiktionary.org](https://ku.wiktionary.org)), "
    "via Kiwix ZIM dumps ([kiwix.org](https://www.kiwix.org))"
)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render_template(text: str, values: dict[str, str]) -> str:
    """Fill ``{{name}}``; an unknown name is a bug in the template, so it raises."""
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], text)


def data_dictionary() -> str:
    lines = [
        "# Data dictionary",
        "",
        "Generated from `src/dataset/schema.py`. Each table ships under the same name in every",
        "format. `entry_key` (`title|language_code`) is the key to use across releases; numeric",
        "ids are rebuilt each release.",
        "",
    ]
    for table in TABLES:
        lines += [f"## `{table.name}`", "", table.description, "", "| Column | Type | Meaning |"]
        lines += ["|---|---|---|"]
        lines += [f"| `{c.name}` | {c.sql_type} | {c.description} |" for c in table.columns]
        lines.append("")
    lines += ["## Section types", "", "| `section_type` | Kurmancî | English |", "|---|---|---|"]
    lines += [f"| `{key}` | {ku} | {en} |" for key, (ku, en) in SECTION_LABELS.items()]
    lines += ["", "## Parts of speech", "", "| `pos` | Kurmancî | English |", "|---|---|---|"]
    lines += [f"| `{key}` | {ku} | {en} |" for key, (ku, en) in POS_LABELS.items()]
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def zim_provenance(paths: list[Path]) -> list[dict[str, str]]:
    from libzim.reader import Archive

    items = []
    for path in paths:
        archive = Archive(str(path))
        items.append(
            {
                "file": path.name,
                "uuid": str(archive.uuid),
                "date": bytes(archive.get_metadata("Date")).decode(),
                "flavour": bytes(archive.get_metadata("Flavour")).decode(),
                "sha256": _sha256(path),
            }
        )
    return items


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _link_tree(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, copy_function=_hardlink)


def _hardlink(source: str, destination: str) -> None:
    Path(destination).hardlink_to(source)


def _zip_folder(source: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    # MP3 and WebP are already compressed: storing them is faster and barely bigger.
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED, allowZip64=True) as out:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not path.name.endswith(".part"):
                out.write(path, path.relative_to(source.parent).as_posix())


def _write_samples(root: Path, target: Path) -> None:
    """A small dict.txt excerpt: lets people inspect the format without a large download."""
    source = root / "mdict" / "staging" / "dict.txt"
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        source.open(encoding="utf-8") as reader,
        (target / "dict_sample.txt").open("w", encoding="utf-8", newline="\n") as writer,
    ):
        for line in reader:
            writer.write(line)
            if line == "</>\n":
                count += 1
                if count == _SAMPLE_RECORDS:
                    break


def _gzip_copy(source: Path, target: Path) -> None:
    with source.open("rb") as reader, gzip.open(target, "wb", compresslevel=6) as writer:
        shutil.copyfileobj(reader, writer, 4 * 1024 * 1024)


def template_values(report: dict[str, Any], zims: list[dict[str, str]]) -> dict[str, str]:
    every = report["coverage"]["all"]
    kurmanci = report["coverage"]["kurmanci"]
    sorani = report["coverage"]["sorani"]
    rows = report["row_counts"]
    audio = sum(
        m["files"] for m in report["media"] if m["kind"] == "audio" and m["status"] == "present"
    )
    images = sum(
        m["files"] for m in report["media"] if m["kind"] == "image" and m["status"] == "present"
    )
    audio_missing = sum(
        m["files"] for m in report["media"] if m["kind"] == "audio" and m["status"] != "present"
    )
    kurmanci_audio = next(
        (item["recordings"] for item in report["audio_by_language"] if item["code"] == "ku"),
        0,
    )
    return {
        "version": DATASET_VERSION,
        "title": DATASET_TITLE,
        "slug": DATASET_SLUG,
        "owner": KAGGLE_OWNER,
        "zim_date": zims[0]["date"],
        "zim_older_date": zims[-1]["date"],
        "pages": f"{rows['pages']:,}",
        "entries": f"{rows['entries']:,}",
        "sections": f"{rows['sections']:,}",
        "senses": f"{rows['senses']:,}",
        "examples": f"{rows['examples']:,}",
        "quotations": f"{rows['quotations']:,}",
        "pronunciations": f"{rows['pronunciations']:,}",
        "etymologies": f"{rows['etymologies']:,}",
        "translations": f"{rows['translations']:,}",
        "relations": f"{rows['relations']:,}",
        "inflection_forms": f"{rows['inflection_forms']:,}",
        "languages": f"{report['language_count']:,}",
        "kurmanci_entries": f"{kurmanci['entries']:,}",
        "sorani_entries": f"{sorani['entries']:,}",
        "auto_pct": str(every["auto_generated_pct"]),
        "auto_count": f"{every['auto_generated']:,}",
        "pending_count": f"{every['definition_pending']:,}",
        "kurmanci_headwords": f"{kurmanci['headword_entries']:,}",
        "audio_top": ", ".join(
            f"{item['name']} {item['recordings']:,}" for item in report["audio_by_language"][:3]
        ),
        "audio_kurmanci": f"{kurmanci_audio:,}",
        "audio_files": f"{audio:,}",
        "audio_missing": f"{audio_missing:,}",
        "image_files": f"{images:,}",
        "year": datetime.now(tz=UTC).strftime("%Y"),
    }


def assemble(
    *,
    root: Path,
    report: dict[str, Any],
    zims: list[dict[str, str]],
    output: Path,
    notebook: Path,
) -> dict[str, Any]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for folder in ("parquet", "csv", "excel"):
        _link_tree(root / folder, output / folder)
    (output / "sql").mkdir()
    for path in (root / "sql").iterdir():
        if path.is_file() and not path.name.endswith(("-wal", "-shm", "-journal")):
            (output / "sql" / path.name).hardlink_to(path)
    (output / "jsonl").mkdir()
    (output / "jsonl" / "entries.jsonl.gz").hardlink_to(root / "jsonl" / "entries.jsonl.gz")

    mdict_out = output / "mdict"
    mdict_out.mkdir()
    for path in (root / "mdict").glob("wiktionary*.md[xd]"):
        (mdict_out / path.name).hardlink_to(path)
    _gzip_copy(root / "mdict" / "staging" / "dict.txt", mdict_out / "dict.txt.gz")
    _write_samples(root, output / "samples")
    shutil.copytree(root / "mdict" / "staging" / "resources" / "css", mdict_out / "css")
    shutil.copytree(root / "mdict" / "staging" / "resources" / "js", mdict_out / "js")

    media_out = output / "media"
    _zip_folder(root / "media" / "audio", media_out / "audio.zip")
    _zip_folder(root / "media" / "images", media_out / "images.zip")

    (output / "notebooks").mkdir()
    shutil.copy2(notebook, output / "notebooks" / notebook.name)
    (output / "quality").mkdir()
    for path in (root / "quality").iterdir():
        if path.suffix in (".json", ".jsonl"):
            shutil.copy2(path, output / "quality" / path.name)

    values = template_values(report, zims)
    for template in sorted(_TEMPLATES.glob("*")):
        (output / template.name).write_text(
            render_template(template.read_text(encoding="utf-8"), values),
            encoding="utf-8",
        )
    (output / "DATA_DICTIONARY.md").write_text(data_dictionary(), encoding="utf-8")
    shutil.copy2(root / "quality" / "QUALITY.md", output / "QUALITY.md")

    readme = (output / "README.md").read_text(encoding="utf-8")
    metadata = {
        "title": DATASET_TITLE,
        "subtitle": f"{values['entries']} entries with sections, audio and MDict build"[:80],
        "id": f"{KAGGLE_OWNER}/{DATASET_SLUG}",
        "licenses": [{"name": "CC-BY-SA-4.0"}],
        "keywords": _KEYWORDS,
        "description": readme,
        "userSpecifiedSources": _SOURCES,
        "image": _COVER.name,
    }
    shutil.copy2(_COVER, output / _COVER.name)
    (output / "dataset-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    checksums: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            relative = path.relative_to(output).as_posix()
            checksums[relative] = _sha256(path)
            sizes[relative] = path.stat().st_size
    manifest = {
        "dataset_version": DATASET_VERSION,
        "dataset_id": metadata["id"],
        "built_at_utc": datetime.now(tz=UTC).isoformat(),
        "git_commit": _git_commit(),
        "pipeline": "https://github.com/0xdolan/wiktionary_to_mdx",
        "sources": zims,
        "row_counts": report["row_counts"],
        "total_bytes": sum(sizes.values()),
        "files": {name: {"bytes": sizes[name], "sha256": checksums[name]} for name in checksums},
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in checksums.items()),
        encoding="utf-8",
    )
    return {"files": len(checksums), "total_gb": round(sum(sizes.values()) / 1e9, 2)}


def finalize_database(conn: sqlite3.Connection) -> None:
    """Leave WAL mode: a WAL database cannot be opened from read-only storage such as Kaggle's."""
    conn.execute("PRAGMA busy_timeout=5000")
    mode = conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
    if mode != "delete":
        raise SystemExit(
            f"Database still in {mode} mode. Finish or stop the media-download and licence stages."
        )


def read_build_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT key, value FROM build_meta"))
