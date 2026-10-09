from typing import Any

from fastapi import APIRouter

from src.api.deps import AppStateDep, DbSessionDep, SettingsDep
from src.core.logging import get_logger
from src.repository.db.base import init_engine
from src.repository.sql_repository import SqlRepository
from src.repository.zim_repository import ZimRepository

logger = get_logger("uvicorn.error")
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    settings: SettingsDep,
    session: DbSessionDep,
    app_state: AppStateDep,
) -> dict[str, Any]:
    _ = init_engine(settings.database_url)

    zim_repo = ZimRepository(
        settings.zim_path,
        reader=app_state.zim_reader,
    )
    zim_health = await zim_repo.health_detail()
    zim = {
        "path": zim_health.detail,
        "readable": zim_health.ready,
        "uuid": None,
    }
    if app_state.zim_reader is not None:
        try:
            zim["uuid"] = app_state.zim_reader.metadata().uuid
        except Exception as exc:  # noqa: BLE001 — health probe
            logger.warning("ZIM metadata read failed: %s", exc)
            zim["readable"] = False

    sql_repo = SqlRepository(session)
    sql_health = await sql_repo.health_detail()
    db = {
        "configured_url": settings.database_url.split("@")[-1],
        "connected": sql_health.ready,
        "latency_ms": _parse_latency(sql_health.detail),
    }

    status = "ok" if zim["readable"] and db["connected"] else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "default_data_source": settings.default_data_source.value,
        "zim": zim,
        "db": db,
    }


def _parse_latency(detail: str) -> float | None:
    if not detail.startswith("latency_ms="):
        return None
    try:
        return float(detail.removeprefix("latency_ms="))
    except ValueError:
        return None
