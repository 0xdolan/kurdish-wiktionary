"""Persist catalog CLI job state so sync/extract runs can resume after interrupt."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.catalog.cli_progress import BatchRunTotals


def fingerprint_zim_paths(paths: list[Path]) -> str:
    normalized = sorted(str(p.expanduser().resolve()) for p in paths)
    payload = "\n".join(normalized)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def fingerprint_single_zim(path: Path) -> str:
    return fingerprint_zim_paths([path])


@dataclass
class CatalogCheckpoint:
    command: str
    fingerprint: str
    limit: int
    run_all: bool
    batch_index: int = 0
    upsert_offset: int = 0
    pending_at_start: int | None = None
    db_corpus_total: int | None = None
    totals: BatchRunTotals = field(default_factory=BatchRunTotals)
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now(tz=UTC).isoformat()

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CatalogCheckpoint:
        totals_raw = data.get("totals") or {}
        totals = BatchRunTotals(
            batches=int(totals_raw.get("batches", 0)),
            attempted=int(totals_raw.get("attempted", 0)),
            extracted=int(totals_raw.get("extracted", 0)),
            skipped=int(totals_raw.get("skipped", 0)),
            failed=int(totals_raw.get("failed", 0)),
        )
        return cls(
            command=str(data["command"]),
            fingerprint=str(data["fingerprint"]),
            limit=int(data["limit"]),
            run_all=bool(data.get("run_all", False)),
            batch_index=int(data.get("batch_index", 0)),
            upsert_offset=int(data.get("upsert_offset", 0)),
            pending_at_start=data.get("pending_at_start"),
            db_corpus_total=data.get("db_corpus_total"),
            totals=totals,
            updated_at=str(data.get("updated_at", "")),
        )


def checkpoint_dir(state_dir: Path) -> Path:
    path = state_dir / "checkpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def checkpoint_path(state_dir: Path, command: str, fingerprint: str) -> Path:
    safe_cmd = command.replace("/", "-")
    return checkpoint_dir(state_dir) / f"{safe_cmd}-{fingerprint}.json"


def load_checkpoint(state_dir: Path, command: str, fingerprint: str) -> CatalogCheckpoint | None:
    path = checkpoint_path(state_dir, command, fingerprint)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    cp = CatalogCheckpoint.from_json(data)
    if cp.command != command or cp.fingerprint != fingerprint:
        return None
    return cp


def save_checkpoint(state_dir: Path, checkpoint: CatalogCheckpoint) -> None:
    checkpoint.touch()
    path = checkpoint_path(state_dir, checkpoint.command, checkpoint.fingerprint)
    path.write_text(json.dumps(checkpoint.to_json(), indent=2), encoding="utf-8")


def clear_checkpoint(state_dir: Path, command: str, fingerprint: str) -> None:
    path = checkpoint_path(state_dir, command, fingerprint)
    if path.is_file():
        path.unlink()
