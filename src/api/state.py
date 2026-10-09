from dataclasses import dataclass, field

from src.extraction.zim_reader import ZimReader
from src.mdict.jobs import JobRegistry


@dataclass(slots=True)
class AppState:
    zim_reader: ZimReader | None = None
    mdict_jobs: JobRegistry = field(default_factory=JobRegistry)
