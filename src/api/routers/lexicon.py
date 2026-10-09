from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from src.api.deps import DbSessionDep, SettingsDep
from src.api.schemas_lexicon import (
    FieldName,
    LexiconDuplicatesResponse,
    LexiconEntryListResponse,
    LexiconExtractResponse,
    LexiconFieldListResponse,
    LexiconFieldValuesResponse,
    LexiconHtmlIndexResponse,
    LexiconHtmlResponse,
    LexiconMediaCorpusResponse,
    LexiconMediaDownloadResponse,
    LexiconMediaListResponse,
    LexiconPreviewResponse,
    LexiconSectionCorpusResponse,
    LexiconSectionHtmlResponse,
    LexiconSparseResponse,
    LexiconZimFieldPreviewResponse,
)
from src.core.models import WiktionaryEntry
from src.lexicon import service as lexicon_service

router = APIRouter(prefix="/lexicon", tags=["lexicon"])


@router.get("/entries", response_model=LexiconEntryListResponse)
async def lexicon_list_entries(
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LexiconEntryListResponse:
    items, total = await lexicon_service.list_entries(session, limit=limit, offset=offset)
    return LexiconEntryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/entries/{word}", response_model=WiktionaryEntry)
async def lexicon_get_entry(word: str, session: DbSessionDep) -> WiktionaryEntry:
    entry = await lexicon_service.get_entry(session, word)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found in SQL.")
    return entry


@router.get("/entries/{word}/fields/{field}", response_model=LexiconFieldValuesResponse)
async def lexicon_get_entry_field(
    word: str,
    field: FieldName,
    session: DbSessionDep,
) -> LexiconFieldValuesResponse:
    values = await lexicon_service.get_entry_field(session, word, field)
    if values is None:
        raise HTTPException(status_code=404, detail="Entry not found in SQL.")
    return LexiconFieldValuesResponse(entry=word, field=field, values=values)


@router.get("/fields/{field}", response_model=LexiconFieldListResponse)
async def lexicon_list_field_across_entries(
    field: FieldName,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LexiconFieldListResponse:
    items, total = await lexicon_service.list_field_values(
        session,
        field,
        limit=limit,
        offset=offset,
    )
    return LexiconFieldListResponse(
        field=field,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/entries/{word}/html", response_model=LexiconHtmlResponse)
async def lexicon_get_html(word: str, session: DbSessionDep) -> LexiconHtmlResponse:
    html = await lexicon_service.get_entry_html_full(session, word)
    if html is None:
        raise HTTPException(status_code=404, detail="HTML not stored; run preview/extract first.")
    return LexiconHtmlResponse(entry=word, html=html)


@router.get("/entries/{word}/html/sections/{section}", response_model=LexiconSectionHtmlResponse)
async def lexicon_get_section_html(
    word: str,
    section: str,
    session: DbSessionDep,
) -> LexiconSectionHtmlResponse:
    html = await lexicon_service.get_entry_html_section(session, word, section)
    if html is None:
        raise HTTPException(status_code=404, detail="Section HTML not found.")
    return LexiconSectionHtmlResponse(entry=word, section=section, html=html)


@router.get("/entries/{word}/media", response_model=LexiconMediaListResponse)
async def lexicon_get_media(word: str, session: DbSessionDep) -> LexiconMediaListResponse:
    items = await lexicon_service.list_entry_media(session, word)
    if items is None:
        raise HTTPException(status_code=404, detail="Entry not found in SQL.")
    return LexiconMediaListResponse(entry=word, items=items)


@router.post("/entries/{word}/preview", response_model=LexiconPreviewResponse)
async def lexicon_preview(word: str, settings: SettingsDep) -> LexiconPreviewResponse:
    try:
        result = await lexicon_service.preview_entry(settings, word)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LexiconPreviewResponse(
        title=result.title,
        entry=result.entry,
        html_bytes=result.html_bytes,
        section_html_keys=result.section_html_keys,
        media_count=result.media_count,
        media=result.media,
        counts=result.counts,
        warnings=result.warnings,
    )


@router.post("/entries/{word}/extract", response_model=LexiconExtractResponse)
async def lexicon_extract(
    word: str,
    settings: SettingsDep,
    session: DbSessionDep,
    confirm: Annotated[bool, Query(description="Must be true to persist")] = False,
) -> LexiconExtractResponse:
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Preview first via POST /lexicon/entries/{word}/preview, then ?confirm=true",
        )
    try:
        row = await lexicon_service.extract_entry_confirmed(session, settings, word)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LexiconExtractResponse(entry=row.entry, entry_id=row.id)


@router.get("/diagnostics/sparse", response_model=LexiconSparseResponse)
async def lexicon_sparse_entries(
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    mode: Annotated[
        Literal["all_empty", "missing_relations"],
        Query(description="all_empty | missing_relations (defs but no syn/ant)"),
    ] = "missing_relations",
) -> LexiconSparseResponse:
    items = await lexicon_service.list_sparse_entries(session, limit=limit, mode=mode)
    return LexiconSparseResponse(items=items)


@router.get("/diagnostics/duplicates", response_model=LexiconDuplicatesResponse)
async def lexicon_duplicate_rows(
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> LexiconDuplicatesResponse:
    items = await lexicon_service.duplicate_field_diagnostics(session, limit=limit)
    return LexiconDuplicatesResponse(items=items)


@router.get("/entries/{word}/zim/fields/{field}", response_model=LexiconZimFieldPreviewResponse)
async def lexicon_zim_field_preview(
    word: str,
    field: FieldName,
    settings: SettingsDep,
) -> LexiconZimFieldPreviewResponse:
    try:
        payload = await lexicon_service.zim_field_preview(settings, word, field)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LexiconZimFieldPreviewResponse(**payload)


@router.get("/entries/{word}/zim/html", response_model=LexiconHtmlResponse)
async def lexicon_zim_html(word: str, settings: SettingsDep) -> LexiconHtmlResponse:
    try:
        payload = await lexicon_service.zim_html_full(settings, word)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LexiconHtmlResponse(entry=payload["entry"], html=payload["html"])


@router.get(
    "/entries/{word}/zim/html/sections/{section}",
    response_model=LexiconSectionHtmlResponse,
)
async def lexicon_zim_section_html(
    word: str,
    section: str,
    settings: SettingsDep,
) -> LexiconSectionHtmlResponse:
    try:
        payload = await lexicon_service.zim_html_section(settings, word, section)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Section HTML not found in ZIM parse.")
    return LexiconSectionHtmlResponse(
        entry=payload["entry"],
        section=payload["section"],
        html=payload["html"],
    )


@router.get("/html", response_model=LexiconHtmlIndexResponse)
async def lexicon_list_stored_html(
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_html: Annotated[bool, Query(description="Include full raw HTML per row")] = False,
) -> LexiconHtmlIndexResponse:
    items, total = await lexicon_service.list_stored_html_pages(
        session,
        limit=limit,
        offset=offset,
        include_html=include_html,
    )
    return LexiconHtmlIndexResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        include_html=include_html,
    )


@router.get("/html/sections/{section}", response_model=LexiconSectionCorpusResponse)
async def lexicon_list_section_html_corpus(
    section: str,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LexiconSectionCorpusResponse:
    items, total = await lexicon_service.list_stored_section_html_corpus(
        session,
        section,
        limit=limit,
        offset=offset,
    )
    return LexiconSectionCorpusResponse(
        section=section,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/media", response_model=LexiconMediaCorpusResponse)
async def lexicon_list_media_corpus(
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: Annotated[str | None, Query(description="audio | image | other")] = None,
) -> LexiconMediaCorpusResponse:
    items, total = await lexicon_service.list_media_corpus(
        session,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    return LexiconMediaCorpusResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        kind=kind,
    )


@router.post("/entries/{word}/media/download", response_model=LexiconMediaDownloadResponse)
async def lexicon_download_media(
    word: str,
    settings: SettingsDep,
    session: DbSessionDep,
    confirm: Annotated[bool, Query(description="Must be true to write files")] = False,
) -> LexiconMediaDownloadResponse:
    try:
        payload = await lexicon_service.download_entry_media(
            session,
            settings,
            word,
            confirm=confirm,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LexiconMediaDownloadResponse(**payload)


@router.get("/export")
async def lexicon_export(
    session: DbSessionDep,
    format: Annotated[Literal["json", "txt"], Query(alias="format")] = "json",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    if format == "json":
        body = await lexicon_service.export_entries_json(session, limit=limit, offset=offset)
        return Response(content=body, media_type="application/json")
    body = await lexicon_service.export_entries_txt(session, limit=limit, offset=offset)
    return PlainTextResponse(content=body)
