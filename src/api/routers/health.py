import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from src.api.deps import DbSessionDep, SettingsDep
from src.core.logging import get_logger
from src.repository.db.base import init_engine

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
async def health(settings: SettingsDep, session: DbSessionDep) -> dict[str, Any]:
    _ = init_engine(settings.database_url)
    db_started = time.perf_counter()
    db: dict[str, Any] = {
        "configured_url": settings.database_url.split("@")[-1],
        "connected": False,
        "latency_ms": None,
    }
    try:
        await session.execute(text("SELECT 1"))
        db["connected"] = True
    except Exception as exc:  # noqa: BLE001 — health probe
        logger.warning("Database health check failed: %s", exc)
    db["latency_ms"] = round((time.perf_counter() - db_started) * 1000, 2)

    zim = _zim_status(settings.zim_path)
    status = "ok" if zim["readable"] and db["connected"] else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "default_data_source": settings.default_data_source.value,
        "zim": zim,
        "db": db,
    }
