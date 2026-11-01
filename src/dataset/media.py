"""Media store: extract from ZIM, audit against references, download gaps, fetch licences.

Files live at ``{images|audio}/{media_id[:2]}/{media_id}.{ext}``: ASCII-only names that survive
every filesystem and dictionary app, and one copy per file however many pages use it. The ``media``
table maps each id back to its ZIM path, source URL and Commons file.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import json
import os
import re
import sqlite3
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from libzim.reader import Archive

from src.dataset.page_parser import media_id_for

# https://wikitech.wikimedia.org/wiki/Robot_policy: media concurrency <= 2 and <= 25 Mbps;
# API concurrency <= 3 and < 5 requests/s when unauthenticated.
MEDIA_CONCURRENCY = 2
MEDIA_MAX_BYTES_PER_S = 25_000_000 // 8
# Uncached transcodes get a 429 after a burst of about 10 requests. Measured 2026-10: a steady
# 1 request/s stays under that limit, and is as fast as bursting and waiting out Retry-After.
MEDIA_MIN_INTERVAL_S = 1.0
API_MIN_INTERVAL_S = 0.5
_API_BATCH = 50
_MAX_ATTEMPTS = 6
_RETRYABLE = frozenset({429, 500, 502, 503, 504})
DEFAULT_USER_AGENT = "wiktionary-to-mdx/1.0 (https://github.com/0xdolan/kurdish-wiktionary) httpx"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
KU_WIKTIONARY_API = "https://ku.wiktionary.org/w/api.php"

_ASSET_MIME_PREFIXES = ("image/", "audio/", "video/")
_UI_PREFIXES = ("_mw_/", "_res_/", "_webp_/")
_TAG = re.compile(r"<[^>]+>")
_MIME_EXT = {
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/tiff": "tif",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/flac": "flac",
    "audio/webm": "webm",
}


def user_agent() -> str:
    return os.environ.get("MEDIA_USER_AGENT", DEFAULT_USER_AGENT)


def sniff_mime(payload: bytes) -> str | None:
    """MIME from file bytes. ZIM paths lie: ``x.jpg`` usually holds WebP."""
    head = payload[:64]
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "audio/mpeg"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"fLaC"):
        return "audio/flac"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if b"<svg" in payload[:2048]:
        return "image/svg+xml"
    return None


def store_path(media_id: str, kind: str, mime: str | None) -> str:
    folder = "audio" if kind == "audio" else "images"
    extension = _MIME_EXT.get(mime or "", "bin")
    return f"{folder}/{media_id[:2]}/{media_id}.{extension}"


def _record_file(
    conn: sqlite3.Connection,
    media_id: str,
    *,
    mime: str | None,
    size: int,
    digest: str,
    local_path: str,
) -> None:
    conn.execute(
        "UPDATE media SET mime=?, bytes=?, sha256=?, local_path=?, status='present', error=NULL"
        " WHERE media_id=?",
        (mime, size, digest, local_path, media_id),
    )


def _write_atomic(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(payload)
    temporary.replace(target)


def register_zim_assets(conn: sqlite3.Connection, archives: Iterable[Path]) -> int:
    """Add ZIM media no page references, so the store holds everything the ZIM holds."""
    added = 0
    for archive_path in archives:
        archive = Archive(str(archive_path))
        for index in range(archive.all_entry_count):
            entry = archive._get_entry_by_id(index)
            path = entry.path
            if entry.is_redirect or not path.startswith(("_assets_/", *_UI_PREFIXES)):
                continue
            mime = entry.get_item().mimetype
            if not mime.startswith(_ASSET_MIME_PREFIXES):
                continue
            cursor = conn.execute(
                "INSERT OR IGNORE INTO media (media_id, kind, source, zim_path, status)"
                " VALUES (?, 'image', 'zim', ?, 'missing')",
                (media_id_for(path), path),
            )
            added += cursor.rowcount
    conn.commit()
    return added


def assign_roles_and_usage(conn: sqlite3.Connection) -> None:
    """A file used as an illustration anywhere is an illustration; otherwise its first role."""
    conn.execute(
        "UPDATE media SET usage_count ="
        " (SELECT COUNT(*) FROM media_usages u WHERE u.media_id = media.media_id)"
    )
    conn.execute(
        """
        UPDATE media SET role = COALESCE(
            (SELECT u.role FROM media_usages u WHERE u.media_id = media.media_id
             ORDER BY CASE u.role WHEN 'pronunciation' THEN 0 WHEN 'illustration' THEN 1
                      WHEN 'hieroglyph' THEN 2 WHEN 'link' THEN 3 ELSE 4 END LIMIT 1),
            CASE WHEN zim_path LIKE '\\_assets\\_/%' ESCAPE '\\' THEN 'unreferenced' ELSE 'ui' END)
        """
    )
    conn.commit()


def extract_from_zim(
    conn: sqlite3.Connection,
    store: Path,
    archives: list[Path],
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, int]:
    """Copy every ZIM media file into the store. Newest archive first; idempotent."""
    opened = [Archive(str(path)) for path in archives]
    rows = conn.execute(
        "SELECT media_id, kind, zim_path FROM media WHERE zim_path IS NOT NULL"
    ).fetchall()
    extracted = unresolved = 0
    for done, (media_id, kind, zim_path) in enumerate(rows, start=1):
        item = None
        for archive in opened:
            if archive.has_entry_by_path(zim_path):
                item = archive.get_entry_by_path(zim_path).get_item()
                break
        if item is None:
            unresolved += 1
            conn.execute(
                "UPDATE media SET status='missing', error=? WHERE media_id=?",
                ("not found in any ZIM", media_id),
            )
            continue
        payload = bytes(item.content)
        mime = sniff_mime(payload) or item.mimetype.split(";")[0].strip()
        relative = store_path(media_id, kind, mime)
        target = store / relative
        if not (target.is_file() and target.stat().st_size == len(payload)):
            _write_atomic(target, payload)
        _record_file(
            conn,
            media_id,
            mime=mime,
            size=len(payload),
            digest=hashlib.sha256(payload).hexdigest(),
            local_path=relative,
        )
        extracted += 1
        if progress and done % 500 == 0:
            progress(done, len(rows))
    conn.commit()
    return {"extracted": extracted, "unresolved": unresolved}


def adopt_previous_downloads(conn: sqlite3.Connection, store: Path, legacy_root: Path) -> int:
    """Reuse ``build/media/{lemma}/audio/{stem}-{hash10}.{ext}`` files; saves re-downloading."""
    if not legacy_root.is_dir():
        return 0
    by_digest: dict[str, Path] = {}
    for lemma in os.scandir(legacy_root):
        audio = Path(lemma.path) / "audio"
        if lemma.name == "state" or not audio.is_dir():
            continue
        for file_path in audio.iterdir():
            by_digest[file_path.stem.rsplit("-", 1)[-1]] = file_path
    adopted = 0
    rows = conn.execute(
        "SELECT media_id, kind, source_url FROM media WHERE source_url IS NOT NULL"
        " AND status != 'present'"
    ).fetchall()
    for media_id, kind, url in rows:
        legacy = by_digest.get(hashlib.sha256(url.encode("utf-8")).hexdigest()[:10])
        if legacy is None:
            continue
        payload = legacy.read_bytes()
        mime = sniff_mime(payload)
        if mime is None or not payload:
            continue
        relative = store_path(media_id, kind, mime)
        target = store / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            os.link(legacy, target)
        _record_file(
            conn,
            media_id,
            mime=mime,
            size=len(payload),
            digest=hashlib.sha256(payload).hexdigest(),
            local_path=relative,
        )
        adopted += 1
    conn.commit()
    return adopted


def rediscover_store(conn: sqlite3.Connection, store: Path) -> int:
    """Reconnect files already in the store after ``parse`` rebuilt the database."""
    on_disk: dict[str, Path] = {}
    folder = store / "audio"
    if folder.is_dir():
        on_disk = {
            path.stem: path
            for path in folder.rglob("*")
            if path.is_file() and path.suffix != ".part"
        }
    found = 0
    rows = conn.execute(
        "SELECT media_id FROM media WHERE source_url IS NOT NULL AND status != 'present'"
    ).fetchall()
    for (media_id,) in rows:
        path = on_disk.get(media_id)
        if path is None:
            continue
        payload = path.read_bytes()
        _record_file(
            conn,
            media_id,
            mime=sniff_mime(payload),
            size=len(payload),
            digest=hashlib.sha256(payload).hexdigest(),
            local_path=path.relative_to(store).as_posix(),
        )
        found += 1
    conn.commit()
    return found


def audit(conn: sqlite3.Connection, store: Path) -> dict[str, Any]:
    """Compare what pages reference, what the table says, and what is really on disk."""
    rows = conn.execute(
        "SELECT media_id, kind, role, source, status, local_path, source_url, zim_path, error,"
        " usage_count, bytes FROM media"
    ).fetchall()
    by_status: dict[str, int] = defaultdict(int)
    bytes_by_kind: dict[str, int] = defaultdict(int)
    lost: list[str] = []
    missing: list[dict[str, Any]] = []
    for media_id, kind, role, source, status, local_path, url, zim_path, error, usage, size in rows:
        if status == "present":
            target = store / local_path
            if not target.is_file() or target.stat().st_size != size:
                status = "missing"
                lost.append(media_id)
            else:
                bytes_by_kind[kind] += size
        by_status[f"{kind}/{role}/{source}/{status}"] += 1
        if status != "present":
            missing.append(
                {
                    "media_id": media_id,
                    "kind": kind,
                    "role": role,
                    "source": source,
                    "status": status,
                    "source_url": url,
                    "zim_path": zim_path,
                    "usage_count": usage,
                    "error": error,
                }
            )
    if lost:
        conn.executemany(
            "UPDATE media SET status='missing', error='file vanished from store' WHERE media_id=?",
            [(media_id,) for media_id in lost],
        )
        conn.commit()
    orphans = conn.execute(
        "SELECT COUNT(DISTINCT u.media_id) FROM media_usages u"
        " LEFT JOIN media m ON m.media_id = u.media_id WHERE m.media_id IS NULL"
    ).fetchone()[0]
    return {
        "total_files": len(rows),
        "present": len(rows) - len(missing),
        "missing": len(missing),
        "bytes_present_by_kind": dict(bytes_by_kind),
        "by_kind_role_source_status": dict(sorted(by_status.items())),
        "usages_without_media_row": orphans,
        "missing_items": missing,
    }


def original_url_for(commons_file: str) -> str:
    """Upload URL of a Commons original, used when a transcode is gone."""
    name = commons_file.replace(" ", "_")
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()  # noqa: S324 - MediaWiki's path scheme
    return (
        "https://upload.wikimedia.org/wikipedia/commons/"
        f"{digest[0]}/{digest[:2]}/{quote(name, safe='')}"
    )


def transcoded_url_for(commons_file: str) -> str:
    """Upload URL of the MP3 that Commons converts a recording to."""
    name = commons_file.replace(" ", "_")
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()  # noqa: S324 - MediaWiki's path scheme
    quoted = quote(name, safe="")
    return (
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/"
        f"{digest[0]}/{digest[:2]}/{quoted}/{quoted}.mp3"
    )


class _Pacer:
    """Shared pause after a 429, plus a bytes-per-second ceiling across workers."""

    def __init__(self, max_bytes_per_s: int) -> None:
        self.max_bytes_per_s = max_bytes_per_s
        self.resume_at = 0.0
        self.window_start = time.monotonic()
        self.window_bytes = 0
        self.next_slot = 0.0
        self.lock = asyncio.Lock()

    async def wait(self) -> None:
        """Take the next request slot, shared by all workers."""
        while True:
            now = time.monotonic()
            if self.resume_at > now:
                await asyncio.sleep(self.resume_at - now)
                continue
            slot = max(now, self.next_slot)
            self.next_slot = slot + MEDIA_MIN_INTERVAL_S
            if slot > now:
                await asyncio.sleep(slot - now)
            return

    def back_off(self, seconds: float) -> None:
        self.resume_at = max(self.resume_at, time.monotonic() + seconds)

    async def account(self, size: int) -> None:
        async with self.lock:
            now = time.monotonic()
            if now - self.window_start >= 10:
                self.window_start, self.window_bytes = now, 0
            self.window_bytes += size
            allowed = self.max_bytes_per_s * 10
            if self.window_bytes > allowed:
                await asyncio.sleep(self.window_start + 10 - now)
                self.window_start, self.window_bytes = time.monotonic(), 0


@dataclass(slots=True)
class DownloadResult:
    payload: bytes | None = None
    error: str | None = None
    used_fallback: bool = False


async def _fetch(
    client: httpx.AsyncClient, url: str, pacer: _Pacer
) -> tuple[bytes | None, str | None]:
    error: str | None = None
    for attempt in range(_MAX_ATTEMPTS):
        await pacer.wait()
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"[:200]
            await asyncio.sleep(min(60.0, 2.0 * 2**attempt))
            continue
        if response.status_code == 200:
            await pacer.account(len(response.content))
            return response.content, None
        error = f"HTTP {response.status_code}"
        if response.status_code not in _RETRYABLE:
            return None, error
        retry_after = response.headers.get("Retry-After", "")
        delay = float(retry_after) if retry_after.isdigit() else min(120.0, 5.0 * 2**attempt)
        if response.status_code == 429:
            pacer.back_off(delay)
        else:
            await asyncio.sleep(delay)
    return None, error


async def _renamed_commons_file(client: httpx.AsyncClient, commons_file: str) -> str | None:
    """Current name of a file moved on Commons, or None if it has not moved."""
    try:
        payload = await _api_get(
            client, COMMONS_API, {"redirects": "1", "titles": f"File:{commons_file}"}
        )
    except httpx.HTTPError:
        return None
    redirects = payload.get("query", {}).get("redirects") or []
    return str(redirects[-1]["to"]).split(":", 1)[-1] if redirects else None


async def _download_one(
    client: httpx.AsyncClient,
    url: str,
    commons_file: str | None,
    pacer: _Pacer,
) -> DownloadResult:
    payload, error = await _fetch(client, url, pacer)
    if payload is None and error == "HTTP 404" and commons_file:
        fallback = original_url_for(commons_file)
        if fallback != url:
            payload, fallback_error = await _fetch(client, fallback, pacer)
            if payload is not None:
                return DownloadResult(payload=payload, used_fallback=True)
            error = f"{error}; original: {fallback_error}"
        # Commons editors rename files after the ZIM is made. The old name only redirects in the
        # API, not on upload.wikimedia.org.
        renamed = await _renamed_commons_file(client, commons_file)
        if renamed:
            for moved in (transcoded_url_for(renamed), original_url_for(renamed)):
                payload, _ = await _fetch(client, moved, pacer)
                if payload is not None:
                    return DownloadResult(payload=payload, used_fallback=True)
    return DownloadResult(payload=payload, error=error)


async def download_missing(
    conn: sqlite3.Connection,
    store: Path,
    *,
    limit: int | None = None,
    include_failed: bool = True,
    progress: Callable[[dict[str, int], int], None] | None = None,
) -> dict[str, int]:
    """Fetch missing remote files. Safe to stop and rerun; state is committed as it goes."""
    states = ("missing", "failed") if include_failed else ("missing",)
    marks = ",".join("?" * len(states))
    sql = (
        "SELECT media_id, kind, source_url, commons_file FROM media"
        f" WHERE source_url IS NOT NULL AND status IN ({marks}) ORDER BY usage_count DESC, media_id"
    )
    rows = conn.execute(sql + (f" LIMIT {int(limit)}" if limit else ""), states).fetchall()
    counts = {"downloaded": 0, "fallback": 0, "failed": 0}
    pacer = _Pacer(MEDIA_MAX_BYTES_PER_S)
    queue: asyncio.Queue[tuple[str, str, str, str | None]] = asyncio.Queue()
    for row in rows:
        queue.put_nowait(row)

    async def worker(client: httpx.AsyncClient) -> None:
        while True:
            try:
                media_id, kind, url, commons_file = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            result = await _download_one(client, url, commons_file, pacer)
            mime = sniff_mime(result.payload) if result.payload else None
            if result.payload and mime:
                relative = store_path(media_id, kind, mime)
                await asyncio.to_thread(_write_atomic, store / relative, result.payload)
                _record_file(
                    conn,
                    media_id,
                    mime=mime,
                    size=len(result.payload),
                    digest=hashlib.sha256(result.payload).hexdigest(),
                    local_path=relative,
                )
                counts["downloaded"] += 1
                counts["fallback"] += int(result.used_fallback)
            else:
                error = result.error or "response is not a recognised media file"
                conn.execute(
                    "UPDATE media SET status='failed', error=? WHERE media_id=?",
                    (error, media_id),
                )
                counts["failed"] += 1
            done = counts["downloaded"] + counts["failed"]
            if done % 50 == 0:
                conn.commit()
                if progress and done % 500 == 0:
                    progress(counts, len(rows))

    headers = {"User-Agent": user_agent()}
    timeout = httpx.Timeout(120.0, connect=30.0)
    async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=timeout) as client:
        await asyncio.gather(*(worker(client) for _ in range(MEDIA_CONCURRENCY)))
    conn.commit()
    return counts


def _plain(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(html_lib.unescape(_TAG.sub(" ", value)).split()) or None


async def _api_get(
    client: httpx.AsyncClient,
    endpoint: str,
    params: dict[str, str],
) -> dict[str, Any]:
    query = {"action": "query", "format": "json", "formatversion": "2", "maxlag": "5", **params}
    for attempt in range(_MAX_ATTEMPTS):
        await asyncio.sleep(API_MIN_INTERVAL_S)
        try:
            response = await client.post(endpoint, data=query)
        except httpx.HTTPError:
            await asyncio.sleep(min(60.0, 2.0 * 2**attempt))
            continue
        if response.status_code in _RETRYABLE:
            retry_after = response.headers.get("Retry-After", "")
            await asyncio.sleep(float(retry_after) if retry_after.isdigit() else 5.0 * 2**attempt)
            continue
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if payload.get("error", {}).get("code") == "maxlag":
            await asyncio.sleep(5.0 * 2**attempt)
            continue
        return payload
    raise httpx.HTTPError(f"API request failed after {_MAX_ATTEMPTS} attempts")


def _file_info(page: dict[str, Any]) -> dict[str, Any] | None:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    meta = info.get("extmetadata") or {}

    def read(key: str) -> str | None:
        field = meta.get(key) or {}
        return _plain(str(field.get("value"))) if field.get("value") else None

    return {
        "license": read("LicenseShortName"),
        "license_url": read("LicenseUrl"),
        "artist": read("Artist") or read("Attribution"),
        "description_url": info.get("descriptionurl"),
        "width": info.get("width"),
        "height": info.get("height"),
    }


async def _commons_file_infos(
    client: httpx.AsyncClient,
    names: list[str],
    progress: Callable[[int, int], None] | None,
) -> dict[str, dict[str, Any]]:
    """Licence and size per file name, keyed with underscores."""
    infos: dict[str, dict[str, Any]] = {}
    for start in range(0, len(names), _API_BATCH):
        batch = names[start : start + _API_BATCH]
        payload = await _api_get(
            client,
            COMMONS_API,
            {
                "prop": "imageinfo",
                "iiprop": "size|url|extmetadata",
                "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Attribution",
                "titles": "|".join(f"File:{name}" for name in batch),
            },
        )
        for page in payload.get("query", {}).get("pages", []):
            info = _file_info(page)
            if info is not None:
                title = str(page.get("title", "")).split(":", 1)[-1]
                infos[title.replace(" ", "_")] = info
        if progress:
            progress(min(start + _API_BATCH, len(names)), len(names))
    return infos


async def _page_files(client: httpx.AsyncClient, titles: list[str]) -> dict[str, list[str]]:
    """Files used per wiki page, via the ku.wiktionary API."""
    files: dict[str, list[str]] = defaultdict(list)
    for start in range(0, len(titles), _API_BATCH):
        batch = titles[start : start + _API_BATCH]
        params = {"prop": "images", "imlimit": "max", "titles": "|".join(batch)}
        while True:
            payload = await _api_get(client, KU_WIKTIONARY_API, params)
            for page in payload.get("query", {}).get("pages", []):
                for image in page.get("images") or []:
                    name = str(image["title"]).split(":", 1)[-1].replace(" ", "_")
                    files[str(page["title"])].append(name)
            continuation = payload.get("continue")
            if not continuation:
                break
            params = {**params, **{k: str(v) for k, v in continuation.items()}}
    return files


def _apply_license(conn: sqlite3.Connection, media_id: str, info: dict[str, Any], how: str) -> None:
    conn.execute(
        "UPDATE media SET license=?, license_url=?, artist=?, description_url=?, license_match=?"
        " WHERE media_id=?",
        (
            info["license"],
            info["license_url"],
            info["artist"],
            info["description_url"],
            how,
            media_id,
        ),
    )


async def fetch_licences(
    conn: sqlite3.Connection,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, int]:
    """Per-file licence and author from Commons. Resumable: skips files that already have one."""
    headers = {"User-Agent": user_agent()}
    timeout = httpx.Timeout(60.0, connect=30.0)
    counts = {"audio_exact": 0, "image_by_dimensions": 0, "image_ambiguous": 0}
    async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=timeout) as client:
        rows = conn.execute(
            "SELECT media_id, commons_file FROM media WHERE commons_file IS NOT NULL"
            " AND license IS NULL"
        ).fetchall()
        names = sorted({str(name).replace(" ", "_") for _, name in rows})
        by_name: dict[str, list[str]] = defaultdict(list)
        for media_id, name in rows:
            by_name[str(name).replace(" ", "_")].append(media_id)
        infos: dict[str, dict[str, Any]] = {}
        for start in range(0, len(names), 2000):
            part = names[start : start + 2000]
            part_infos = await _commons_file_infos(client, part, None)
            infos.update(part_infos)
            for name, info in part_infos.items():
                for media_id in by_name.get(name, []):
                    _apply_license(conn, media_id, info, "exact")
                    counts["audio_exact"] += 1
            conn.commit()
            if progress:
                progress(min(start + 2000, len(names)), len(names))

        # ZIM images have hashed names. The page's file list plus the original dimensions kept
        # in the HTML identifies them when exactly one file on the page has those dimensions.
        usage_rows = conn.execute(
            "SELECT DISTINCT m.media_id, p.title, m.original_width, m.original_height"
            " FROM media m JOIN media_usages u ON u.media_id = m.media_id"
            " JOIN pages p ON p.page_id = u.page_id"
            " WHERE m.role = 'illustration' AND m.license IS NULL"
            " AND m.original_width IS NOT NULL AND p.in_latest_dump = 1"
        ).fetchall()
        titles = sorted({title for _, title, _, _ in usage_rows})
        page_files = await _page_files(client, titles)
        wanted = sorted({name for files in page_files.values() for name in files})
        image_infos = await _commons_file_infos(client, wanted, None)
        for media_id, title, width, height in usage_rows:
            candidates = [
                name
                for name in page_files.get(title, [])
                if image_infos.get(name, {}).get("width") == width
                and image_infos.get(name, {}).get("height") == height
            ]
            unique = list(dict.fromkeys(candidates))
            if len(unique) != 1:
                counts["image_ambiguous"] += 1
                continue
            already = conn.execute(
                "SELECT license FROM media WHERE media_id=?", (media_id,)
            ).fetchone()[0]
            if already is not None:
                continue
            conn.execute("UPDATE media SET commons_file=? WHERE media_id=?", (unique[0], media_id))
            _apply_license(conn, media_id, image_infos[unique[0]], "by_dimensions")
            counts["image_by_dimensions"] += 1
        conn.commit()
    return counts


_LICENCE_COLUMNS = (
    "commons_file, license, license_url, artist, description_url, license_match, media_id"
)


def saved_licences(database: Path) -> list[tuple[Any, ...]]:
    """Licence rows of an existing database: fetching them again takes an hour of API calls."""
    if not database.is_file():
        return []
    conn = sqlite3.connect(database)
    try:
        return conn.execute(
            f"SELECT {_LICENCE_COLUMNS} FROM media WHERE license IS NOT NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def restore_licences(conn: sqlite3.Connection, rows: list[tuple[Any, ...]]) -> None:
    conn.executemany(
        "UPDATE media SET commons_file=?, license=?, license_url=?, artist=?, description_url=?,"
        " license_match=? WHERE media_id=?",
        rows,
    )


def write_audit_files(report: dict[str, Any], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in report.items() if key != "missing_items"}
    (directory / "media_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (directory / "media_missing.jsonl").open("w", encoding="utf-8") as handle:
        for item in report["missing_items"]:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
