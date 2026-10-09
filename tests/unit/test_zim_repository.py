from pathlib import Path

import pytest
from src.extraction.zim_reader import ZimArticle, ZimMetadata, ZimReader
from src.repository.zim_repository import ZimRepository

HEVAL_HTML = """
<div class="mw-parser-output">
  <h3><span>Navdêr</span></h3>
  <ol><li>heval</li></ol>
  <span class="IPA">/heval/</span>
</div>
"""


class FakeZimReader:
    def metadata(self) -> ZimMetadata:
        return ZimMetadata(
            uuid="test-uuid",
            date="2026-06-23",
            source="ku.wiktionary.org",
            title="Wîkîferheng",
            path=Path("fake.zim"),
        )

    def get_article_by_title(self, title: str) -> ZimArticle | None:
        if title != "heval":
            return None
        return ZimArticle(title="heval", path="heval", html=HEVAL_HTML)

    def iter_articles(self):
        yield ZimArticle(title="heval", path="heval", html=HEVAL_HTML)


@pytest.mark.asyncio
async def test_zim_repository_get_entry() -> None:
    repo = ZimRepository(Path("fake.zim"), reader=FakeZimReader())  # type: ignore[arg-type]
    entry = await repo.get_entry("heval")
    assert entry is not None
    assert entry.entry == "heval"
    assert entry.phonetic_transcriptions == ["/heval/"]


@pytest.mark.asyncio
async def test_zim_repository_list_entries() -> None:
    repo = ZimRepository(Path("fake.zim"), reader=FakeZimReader())  # type: ignore[arg-type]
    items, total = await repo.list_entries(limit=10, offset=0)
    assert total >= 1
    assert items[0].entry == "heval"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_zim_repository_live_heval() -> None:
    zim = Path("zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim")
    if not zim.is_file():
        pytest.skip("ZIM file not present")
    repo = ZimRepository(zim, reader=ZimReader(zim))
    entry = await repo.get_entry("heval")
    assert entry is not None
    assert entry.definitions or entry.phonetic_transcriptions
