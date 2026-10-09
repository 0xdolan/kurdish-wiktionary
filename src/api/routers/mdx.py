import io
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.api.deps import AppStateDep, DbSessionDep, SettingsDep
from src.api.schemas_mdx import (
    JobCreatedResponse,
    JobStatusResponse,
    MdxAboutResponse,
    MdxBuildRequest,
    MdxExtractRequest,
    MdxKeysResponse,
    MdxLookupResponse,
    MdxMetaResponse,
)
from src.config import DataSource
from src.core.exceptions import NotFoundError
from src.core.services.wiktionary_service import WiktionaryService
from src.mdict.export import build_mdict_artifacts, collect_entries, default_template_paths
from src.mdict.extract import unpack_to_job_dir
from src.mdict.jobs import JobKind, JobRecord, JobRegistry
from src.mdict.pack import list_keys, query_key, read_meta
from src.mdict.paths import UnsafePathError, resolve_under_work_dir
from src.mdict.renderer import render_entry_html
from src.repository.db.base import get_session_factory, init_engine
from src.repository.factory import build_repository
from src.repository.protocol import WiktionaryRepositoryProto
from src.repository.zim_repository import ZimRepository

router = APIRouter(prefix="/mdx", tags=["mdx"])

_ABOUT_BODY = """# MDX / MDD export

This API builds **MDict 2.0** `.mdx` / `.mdd` files from Wiktionary entries using [mdict-utils](https://pypi.org/project/mdict-utils/).

- **MDX** — headword → HTML definitions
- **MDD** — optional resource package (CSS, media)

See the repository [MDX_MDD_GUIDE.md](https://github.com/) for operator steps and format notes.
"""


def _jobs(state: AppStateDep) -> JobRegistry:
    return state.mdict_jobs


def _job_response(record: JobRecord) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=record.id,
        kind=record.kind.value,
        status=record.status.value,
        progress=record.progress,
        error=record.error,
        artifact_dir=record.artifact_dir,
    )


def _safe_path(settings: SettingsDep, relative: str) -> Path:
    try:
        return resolve_under_work_dir(settings.mdx_work_dir, relative)
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/about", response_model=MdxAboutResponse)
async def mdx_about() -> MdxAboutResponse:
    return MdxAboutResponse(
        body=_ABOUT_BODY,
        references=[
            "https://pypi.org/project/mdict-utils/",
            "https://github.com/liuyug/mdict-utils",
            "https://bitbucket.org/xwang/mdict-analysis/src/master/",
        ],
    )


@router.get("/meta", response_model=MdxMetaResponse)
async def mdx_meta(
    settings: SettingsDep,
    path: Annotated[str, Query(min_length=1)],
) -> MdxMetaResponse:
    target = _safe_path(settings, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="MDX/MDD file not found.")
    meta = await read_meta(target)
    return MdxMetaResponse(path=path, meta=meta)


@router.get("/keys", response_model=MdxKeysResponse)
async def mdx_keys(
    settings: SettingsDep,
    path: Annotated[str, Query(min_length=1)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=5000)] = 100,
) -> MdxKeysResponse:
    target = _safe_path(settings, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="MDX file not found.")
    keys = await list_keys(target)
    window = keys[offset : offset + limit]
    return MdxKeysResponse(path=path, total=len(keys), offset=offset, limit=limit, keys=window)


@router.get("/lookup/{headword}", response_model=MdxLookupResponse)
async def mdx_lookup(
    headword: str,
    settings: SettingsDep,
    session: DbSessionDep,
    app_state: AppStateDep,
    path: Annotated[str | None, Query()] = None,
    data_source: Annotated[DataSource | None, Query()] = None,
) -> MdxLookupResponse:
    if path is not None:
        target = _safe_path(settings, path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="MDX file not found.")
        html = await query_key(target, headword)
        return MdxLookupResponse(headword=headword, html=html, source="mdx")

    source = data_source or settings.default_data_source
    repository: WiktionaryRepositoryProto
    if source is DataSource.ZIM:
        repository = ZimRepository(settings.zim_path, reader=app_state.zim_reader)
    else:
        repository = build_repository(settings, source_override=DataSource.SQL, session=session)
    service = WiktionaryService(repository)
    try:
        entry = await service.get_entry(headword)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MdxLookupResponse(
        headword=headword,
        html=render_entry_html(entry),
        source="repository",
    )


@router.post("/build", response_model=JobCreatedResponse, status_code=202)
async def mdx_build(
    body: MdxBuildRequest,
    settings: SettingsDep,
    app_state: AppStateDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobCreatedResponse:
    record = jobs.create(JobKind.BUILD)
    job_dir = settings.mdx_work_dir / "jobs" / record.id
    job_dir.mkdir(parents=True, exist_ok=True)
    record.artifact_dir = str(job_dir)

    include_media = (
        settings.mdx_include_media if body.include_media is None else body.include_media
    )
    title_path, description_path = default_template_paths()
    if body.title:
        title_path = Path(body.title)
    if body.description:
        description_path = Path(body.description)

    async def _run(job_record: JobRecord) -> None:
        job_record.progress = {"phase": "collecting"}
        init_engine(settings.database_url)
        if body.data_source is DataSource.SQL:
            async with get_session_factory()() as bg_session:
                entries = await collect_entries(
                    settings,
                    data_source=body.data_source,
                    limit=body.limit,
                    session=bg_session,
                    zim_reader=None,
                )
        else:
            entries = await collect_entries(
                settings,
                data_source=body.data_source,
                limit=body.limit,
                session=None,
                zim_reader=app_state.zim_reader,
            )
        job_record.progress = {"phase": "packing", "entries": len(entries)}
        artifacts = await build_mdict_artifacts(
            settings,
            entries=entries,
            output_dir=job_dir,
            include_media=include_media,
            title_html=title_path,
            description_html=description_path,
        )
        job_record.progress = {
            "phase": "completed",
            "entries": artifacts.entry_count,
            "mdx": str(artifacts.mdx_path.name),
            "mdd": artifacts.mdd_path.name if artifacts.mdd_path else None,
        }

    jobs.start_background(record.id, _run)
    return JobCreatedResponse(job_id=record.id)


@router.get("/build/{job_id}", response_model=JobStatusResponse)
async def mdx_build_status(
    job_id: str,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobStatusResponse:
    record = jobs.get(job_id)
    if record is None or record.kind is not JobKind.BUILD:
        raise HTTPException(status_code=404, detail="Build job not found.")
    return _job_response(record)


@router.get("/build/{job_id}/download")
async def mdx_build_download(
    job_id: str,
    settings: SettingsDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> StreamingResponse:
    record = jobs.get(job_id)
    if record is None or record.kind is not JobKind.BUILD:
        raise HTTPException(status_code=404, detail="Build job not found.")
    if record.status.value != "completed" or not record.artifact_dir:
        raise HTTPException(status_code=409, detail="Build job not completed.")

    job_dir = Path(record.artifact_dir)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in job_dir.iterdir():
            if path.is_file() and path.suffix in {".mdx", ".mdd", ".json"}:
                archive.write(path, arcname=path.name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="mdx-build-{job_id}.zip"'},
    )


@router.post("/extract", response_model=JobCreatedResponse, status_code=202)
async def mdx_extract(
    body: MdxExtractRequest,
    settings: SettingsDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobCreatedResponse:
    mdx_target = _safe_path(settings, body.mdx_path)
    if not mdx_target.is_file():
        raise HTTPException(status_code=404, detail="MDX file not found.")

    record = jobs.create(JobKind.EXTRACT)
    job_dir = settings.mdx_work_dir / "jobs" / record.id
    job_dir.mkdir(parents=True, exist_ok=True)
    record.artifact_dir = str(job_dir)

    async def _run(job_record: JobRecord) -> None:
        job_record.progress = {"phase": "extracting_mdx"}
        out = await unpack_to_job_dir(mdx_target, job_dir)
        job_record.progress = {"phase": "completed", "mdx_extracted": str(out)}
        if body.mdd_path:
            mdd_target = _safe_path(settings, body.mdd_path)
            if mdd_target.is_file():
                job_record.progress["phase"] = "extracting_mdd"
                mdd_out = await unpack_to_job_dir(mdd_target, job_dir / "mdd")
                job_record.progress["mdd_extracted"] = str(mdd_out)

    jobs.start_background(record.id, _run)
    return JobCreatedResponse(job_id=record.id)


@router.get("/extract/{job_id}", response_model=JobStatusResponse)
async def mdx_extract_status(
    job_id: str,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobStatusResponse:
    record = jobs.get(job_id)
    if record is None or record.kind is not JobKind.EXTRACT:
        raise HTTPException(status_code=404, detail="Extract job not found.")
    return _job_response(record)
