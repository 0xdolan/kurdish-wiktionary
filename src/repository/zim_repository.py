import asyncio
from pathlib import Path

from src.config import DataSource
from src.core.models import WiktionaryEntry
from src.extraction.html_parser import parse_wiktionary_html
from src.extraction.zim_reader import ZimReader
from src.repository.protocol import RepositoryHealth

# Listing scans the ZIM sequentially; large offsets are expensive.
_MAX_LIST_SCAN = 500_000


class ZimRepository:
    def __init__(self, zim_path: Path, *, reader: ZimReader | None = None) -> None:
        self._zim_path = zim_path
        self._reader = reader

    @property
    def source(self) -> DataSource:
        return DataSource.ZIM

    def _reader_instance(self) -> ZimReader:
        if self._reader is not None:
            return self._reader
        return ZimReader(self._zim_path)

    def _metadata_base(self, reader: ZimReader) -> dict[str, str | None]:
        meta = reader.metadata()
        return {
            "zim_uuid": meta.uuid,
            "zim_date": meta.date,
            "zim_source": meta.source,
            "zim_path": str(meta.path),
            "data_source": DataSource.ZIM.value,
        }

    def _get_entry_sync(self, word: str) -> WiktionaryEntry | None:
        reader = self._reader_instance()
        article = reader.get_article_by_title(word)
        if article is None:
            return None
        return parse_wiktionary_html(
            article.title,
            article.html,
            metadata_base=self._metadata_base(reader),
        )

    def _list_entries_sync(self, limit: int, offset: int) -> tuple[list[WiktionaryEntry], int]:
        reader = self._reader_instance()
        if self._reader is None and not self._zim_path.is_file():
            return [], 0

        metadata_base = self._metadata_base(reader)
        collected: list[WiktionaryEntry] = []
        matched = 0
        scanned = 0

        for article in reader.iter_articles():
            scanned += 1
            if scanned > _MAX_LIST_SCAN:
                break
            try:
                parsed = parse_wiktionary_html(
                    article.title,
                    article.html,
                    metadata_base=dict(metadata_base),
                )
            except Exception:
                continue
            if not parsed.definitions and not parsed.phonetic_transcriptions:
                continue
            if matched >= offset and len(collected) < limit:
                collected.append(parsed)
            matched += 1
            if len(collected) >= limit and matched >= offset + limit:
                break

        return collected, matched

    async def get_entry(self, word: str) -> WiktionaryEntry | None:
        return await asyncio.to_thread(self._get_entry_sync, word)

    async def list_entries(self, limit: int, offset: int) -> tuple[list[WiktionaryEntry], int]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        return await asyncio.to_thread(self._list_entries_sync, safe_limit, safe_offset)

    async def health_detail(self) -> RepositoryHealth:
        readable = self._zim_path.is_file() and self._zim_path.stat().st_size > 0
        return RepositoryHealth(
            source=DataSource.ZIM,
            ready=readable,
            detail=str(self._zim_path.resolve()),
        )
