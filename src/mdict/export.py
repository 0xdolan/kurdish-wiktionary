import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import DataSource, Settings
from src.core.models import WiktionaryEntry
from src.extraction.zim_reader import ZimReader
from src.mdict.pack import pack_mdd, pack_mdx, read_meta
from src.mdict.resources import stage_resource_tree
from src.mdict.txt_writer import write_dict_txt
from src.repository.factory import build_repository
from src.repository.protocol import WiktionaryRepositoryProto
from src.repository.zim_repository import ZimRepository


@dataclass(frozen=True)
class BuildArtifacts:
    staging_dir: Path
    dict_txt: Path
    mdx_path: Path
    mdd_path: Path | None
    entry_count: int
    manifest_path: Path


def default_template_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    templates = root / "assets" / "mdict" / "templates"
    return templates / "title.html", templates / "description.html"


async def collect_entries(
    settings: Settings,
    *,
    data_source: DataSource,
    limit: int | None,
    session: AsyncSession | None,
    zim_reader: ZimReader | None,
) -> list[WiktionaryEntry]:
    repository: WiktionaryRepositoryProto
    if data_source is DataSource.ZIM:
        repository = ZimRepository(settings.zim_path, reader=zim_reader)
    else:
        if session is None:
            msg = "SQL export requires a database session."
            raise RuntimeError(msg)
        repository = build_repository(settings, source_override=DataSource.SQL, session=session)

    cap = limit if limit is not None else 500
    cap = max(1, min(cap, 500_000))
    items, _total = await repository.list_entries(limit=cap, offset=0)
    return items


async def build_mdict_artifacts(
    settings: Settings,
    *,
    entries: list[WiktionaryEntry],
    output_dir: Path,
    include_media: bool,
    title_html: Path | None = None,
    description_html: Path | None = None,
    basename: str = "wikiferheng",
) -> BuildArtifacts:
    default_title, default_description = default_template_paths()
    title_path = title_html or default_title
    description_path = description_html or default_description

    staging_dir = output_dir / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    dict_txt = staging_dir / "dict.txt"
    entry_count = write_dict_txt(entries, dict_txt)

    resources_dir = stage_resource_tree(staging_dir, include_media=include_media)

    mdx_path = output_dir / f"{basename}.mdx"
    await pack_mdx(
        title_html=title_path,
        description_html=description_path,
        dict_txt=dict_txt,
        output_mdx=mdx_path,
    )

    mdd_path: Path | None = None
    if include_media:
        candidate = output_dir / f"{basename}.mdd"
        await pack_mdd(
            title_html=title_path,
            description_html=description_path,
            resources_dir=resources_dir,
            output_mdd=candidate,
        )
        if candidate.is_file():
            mdd_path = candidate

    manifest = {
        "entry_count": entry_count,
        "built_at": datetime.now(tz=UTC).isoformat(),
        "mdx": str(mdx_path.name),
        "mdd": str(mdd_path.name) if mdd_path else None,
        "title_html": str(title_path),
        "description_html": str(description_path),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Smoke metadata read
    _ = await read_meta(mdx_path)

    return BuildArtifacts(
        staging_dir=staging_dir,
        dict_txt=dict_txt,
        mdx_path=mdx_path,
        mdd_path=mdd_path,
        entry_count=entry_count,
        manifest_path=manifest_path,
    )
