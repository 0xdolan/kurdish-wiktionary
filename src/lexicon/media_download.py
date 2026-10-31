from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Literal

import httpx

from src.extraction.zim_media import local_media_relative_path, resolve_media_href_in_archives
from src.extraction.zim_reader import ZimReader

MediaFetchMode = Literal["all", "zim_only", "remote_only"]

_WIKIMEDIA_USER_AGENT = (
    "wiktionary-to-mdx/1.0 (https://github.com/0xdolan/kurdish-wiktionary) httpx"
)
_MAX_REMOTE_RETRIES = 6
_REMOTE_MIN_INTERVAL_S = 0.35
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_client: httpx.AsyncClient | None = None
_rate_lock = asyncio.Lock()
_last_remote_monotonic = 0.0


def file_matches_expected_size(file_size: int, expected_size: int | None) -> bool:
    if expected_size is None or expected_size <= 0:
        return False
    return file_size == expected_size


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0, connect=20.0),
            headers={"User-Agent": _WIKIMEDIA_USER_AGENT},
        )
    return _client


async def close_media_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _retry_delay_seconds(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                return max(float(raw), _REMOTE_MIN_INTERVAL_S)
            except ValueError:
                pass
    return min(60.0, _REMOTE_MIN_INTERVAL_S * 2.0**attempt)


async def _throttle_remote() -> None:
    global _last_remote_monotonic
    async with _rate_lock:
        now = time.monotonic()
        wait = _REMOTE_MIN_INTERVAL_S - (now - _last_remote_monotonic)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_remote_monotonic = time.monotonic()


async def fetch_remote_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    client = await _get_client()
    last_error: str | None = None
    for attempt in range(_MAX_REMOTE_RETRIES):
        await _throttle_remote()
        try:
            response = await client.get(url, timeout=timeout)
            if response.status_code in _RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}"
                await asyncio.sleep(_retry_delay_seconds(response, attempt))
                continue
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            last_error = f"HTTP {status}"
            if status in _RETRYABLE_STATUS:
                await asyncio.sleep(_retry_delay_seconds(exc.response, attempt))
                continue
            raise
        except httpx.HTTPError as exc:
            last_error = str(exc)
            await asyncio.sleep(_retry_delay_seconds(None, attempt))
    raise httpx.HTTPError(last_error or "remote fetch failed after retries")


async def remote_content_length(url: str) -> int | None:
    client = await _get_client()
    for attempt in range(_MAX_REMOTE_RETRIES):
        await _throttle_remote()
        try:
            response = await client.head(url)
            if response.status_code in _RETRYABLE_STATUS:
                await asyncio.sleep(_retry_delay_seconds(response, attempt))
                continue
            response.raise_for_status()
            raw = response.headers.get("content-length")
            if not raw:
                return None
            return int(raw)
        except (httpx.HTTPError, ValueError):
            await asyncio.sleep(_retry_delay_seconds(None, attempt))
    return None


def read_zim_bytes(zim_path: Path, zim_entry_path: str) -> bytes | None:
    return ZimReader(zim_path).read_entry_bytes_by_path(zim_entry_path)


async def download_media_item(
    *,
    export_dir: Path,
    entry_normalized: str,
    kind: str,
    url: str,
    zim_paths: list[Path],
    article_zim_path: str | None,
    reuse_if_same_size: bool = True,
    fetch_mode: MediaFetchMode = "all",
) -> dict[str, str | int | None]:
    """
    Write one asset under ``export_dir`` and return ``local_path`` (relative to export_dir).
    """
    resolved: dict[str, str] = {"source": "remote", "fetch_url": url, "url": url}
    if zim_paths and article_zim_path:
        resolved = resolve_media_href_in_archives(
            article_zim_path=article_zim_path,
            href=url,
            zim_paths=zim_paths,
        )

    source = resolved.get("source")
    if fetch_mode == "zim_only" and source != "zim":
        return {
            "local_path": None,
            "source": source or "remote",
            "status": "deferred",
            "error": "skipped in zim_only mode (needs remote or unresolved)",
        }
    if fetch_mode == "remote_only" and source == "zim":
        return {
            "local_path": None,
            "source": "zim",
            "status": "deferred",
            "error": "skipped in remote_only mode (available in ZIM)",
        }

    rel = local_media_relative_path(entry_normalized=entry_normalized, kind=kind, url=url)
    target = export_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    if source == "zim":
        zim_entry = resolved.get("zim_path")
        archive_raw = resolved.get("zim_archive")
        archive = Path(str(archive_raw)) if archive_raw else (zim_paths[0] if zim_paths else None)
        if not zim_entry or archive is None:
            return {"local_path": None, "error": "missing zim_path", "source": "zim"}
        payload = read_zim_bytes(archive, zim_entry)
        if payload is None:
            return {"local_path": None, "error": "zim read failed", "source": "zim"}
        if reuse_if_same_size and target.is_file():
            size = target.stat().st_size
            if file_matches_expected_size(size, len(payload)):
                return {
                    "local_path": rel,
                    "source": "zim",
                    "zim_path": zim_entry,
                    "status": "reused",
                    "bytes": len(payload),
                }
        target.write_bytes(payload)
        return {
            "local_path": rel,
            "source": "zim",
            "zim_path": zim_entry,
            "bytes": len(payload),
        }

    if source == "remote":
        fetch_url = resolved.get("fetch_url", url)
        if reuse_if_same_size and target.is_file():
            expected = await remote_content_length(fetch_url)
            size = target.stat().st_size
            if file_matches_expected_size(size, expected):
                return {
                    "local_path": rel,
                    "source": "remote",
                    "fetch_url": fetch_url,
                    "status": "reused",
                    "bytes": size,
                }
        try:
            payload = await fetch_remote_bytes(fetch_url)
        except httpx.HTTPError as exc:
            return {
                "local_path": None,
                "source": "remote",
                "fetch_url": fetch_url,
                "error": str(exc),
            }
        if reuse_if_same_size and target.is_file():
            size = target.stat().st_size
            if file_matches_expected_size(size, len(payload)):
                return {
                    "local_path": rel,
                    "source": "remote",
                    "fetch_url": fetch_url,
                    "status": "reused",
                    "bytes": size,
                }
        target.write_bytes(payload)
        return {
            "local_path": rel,
            "source": "remote",
            "fetch_url": fetch_url,
            "bytes": len(payload),
        }

    return {
        "local_path": None,
        "source": "unresolved",
        "error": resolved.get("hint", "could not resolve media href"),
    }
