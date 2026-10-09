from dataclasses import dataclass

from src.extraction.zim_reader import ZimReader


@dataclass(slots=True)
class AppState:
    zim_reader: ZimReader | None = None
