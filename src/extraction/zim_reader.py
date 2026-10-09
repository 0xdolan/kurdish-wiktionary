from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import libzim

from src.extraction.normalize import is_wiktionary_article_title


@dataclass(frozen=True, slots=True)
class ZimArticle:
    title: str
    path: str
    html: str


@dataclass(frozen=True, slots=True)
class ZimMetadata:
    uuid: str
    date: str | None
    source: str | None
    title: str | None
    path: Path


class ZimReader:
    def __init__(self, zim_path: Path) -> None:
        self._path = zim_path
        self._archive = libzim.Archive(str(zim_path))

    @property
    def path(self) -> Path:
        return self._path

    def metadata(self) -> ZimMetadata:
        def meta_text(key: str) -> str | None:
            if key not in self._archive.metadata_keys:
                return None
            raw = self._archive.get_metadata(key)
            return raw.decode("utf-8", errors="replace") if raw else None

        return ZimMetadata(
            uuid=str(self._archive.uuid),
            date=meta_text("Date"),
            source=meta_text("Source"),
            title=meta_text("Title"),
            path=self._path,
        )

    def has_path(self, path: str) -> bool:
        if not self._path.is_file():
            return False
        return bool(self._archive.has_entry_by_path(path))

    def read_entry_bytes_by_path(self, path: str) -> bytes | None:
        if not self.has_path(path):
            return None
        entry = self._archive.get_entry_by_path(path)
        if entry.is_redirect:
            entry = entry.get_redirect_entry()
        try:
            item = entry.get_item()
        except RuntimeError:
            return None
        raw: bytes = item.content.tobytes()
        return raw

    def get_article_by_title(self, title: str) -> ZimArticle | None:
        if not self._path.is_file():
            return None
        if not self._archive.has_entry_by_title(title):
            return None
        entry = self._archive.get_entry_by_title(title)
        if entry.is_redirect:
            entry = entry.get_redirect_entry()
        try:
            item = entry.get_item()
        except RuntimeError:
            return None
        if item.mimetype != "text/html":
            return None
        html = item.content.tobytes().decode("utf-8", errors="replace")
        return ZimArticle(title=entry.title, path=entry.path, html=html)

    def iter_article_titles(self) -> Iterator[str]:
        """Lemma titles only (no HTML load) — used for wordlist indexing."""
        for entry_id in range(self._archive.all_entry_count):
            entry = self._archive._get_entry_by_id(entry_id)
            if entry.is_redirect:
                continue
            title = entry.title
            if is_wiktionary_article_title(title):
                yield title

    def count_article_titles(self) -> int:
        return sum(1 for _ in self.iter_article_titles())

    def iter_articles(self) -> Iterator[ZimArticle]:
        total = self._archive.all_entry_count
        for entry_id in range(total):
            entry = self._archive._get_entry_by_id(entry_id)
            if entry.is_redirect:
                continue
            title = entry.title
            if not is_wiktionary_article_title(title):
                continue
            try:
                item = entry.get_item()
            except RuntimeError:
                continue
            if item.mimetype != "text/html":
                continue
            html = item.content.tobytes().decode("utf-8", errors="replace")
            yield ZimArticle(title=title, path=entry.path, html=html)
