from __future__ import annotations

from pathlib import Path

import httpx

from src.extraction.zim_media import local_media_relative_path, resolve_media_href
from src.extraction.zim_reader import ZimReader


async def fetch_remote_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def read_zim_bytes(zim_path: Path, zim_entry_path: str) -> bytes | None:
    return ZimReader(zim_path).read_entry_bytes_by_path(zim_entry_path)


async def download_media_item(
    *,
    export_dir: Path,
    entry_normalized: str,
    kind: str,
    url: str,
    zim_path: Path | None,
    article_zim_path: str | None,
) -> dict[str, str | None]:
    """
    Write one asset under ``export_dir`` and return ``local_path`` (relative to export_dir).
    """
    resolved: dict[str, str] = {"source": "remote", "fetch_url": url, "url": url}
    if zim_path is not None and article_zim_path:
        reader = ZimReader(zim_path)
        resolved = resolve_media_href(
            article_zim_path=article_zim_path,
            href=url,
            has_zim_path=reader.has_path,
        )

    rel = local_media_relative_path(entry_normalized=entry_normalized, kind=kind, url=url)
    target = export_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    if resolved.get("source") == "zim" and zim_path is not None:
        zim_entry = resolved.get("zim_path")
        if not zim_entry:
            return {"local_path": None, "error": "missing zim_path", "source": "zim"}
        payload = read_zim_bytes(zim_path, zim_entry)
        if payload is None:
            return {"local_path": None, "error": "zim read failed", "source": "zim"}
        target.write_bytes(payload)
        return {"local_path": rel, "source": "zim", "zim_path": zim_entry}

    if resolved.get("source") == "remote":
        fetch_url = resolved.get("fetch_url", url)
        payload = await fetch_remote_bytes(fetch_url)
        target.write_bytes(payload)
        return {"local_path": rel, "source": "remote", "fetch_url": fetch_url}

    return {
        "local_path": None,
        "source": "unresolved",
        "error": resolved.get("hint", "could not resolve media href"),
    }
