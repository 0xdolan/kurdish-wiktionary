import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from src.api.deps import SettingsDep
from src.core.logging import get_logger

logger = get_logger("uvicorn.error")
router = APIRouter(tags=["health"])


def _zim_status(zim_path: Path) -> dict[str, Any]:
    readable = zim_path.is_file() and zim_path.stat().st_size > 0
    uuid: str | None = None
    if readable:
        try:
            import libzim

            archive = libzim.Archive(str(zim_path))
            uuid = str(archive.uuid)
        except Exception as exc:  # noqa: BLE001 — health probe must not fail the handler
            logger.warning("ZIM metadata read failed: %s", exc)
            readable = False
    return {
        "path": str(zim_path.resolve()),
        "readable": readable,
        "uuid": uuid,
    }


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, Any]:
    started = time.perf_counter()
    db: dict[str, Any] = {
        "configured_url": settings.database_url.split("@")[-1],
        "connected": False,
        "latency_ms": None,
    }
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    db["latency_ms"] = latency_ms

    zim = _zim_status(settings.zim_path)
    status = "ok" if zim["readable"] else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "default_data_source": settings.default_data_source.value,
        "zim": zim,
        "db": db,
    }
