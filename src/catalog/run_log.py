"""Append-only JSONL logs for extract batches (skipped/failed lemmas)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from src.catalog.outcomes import LemmaOutcome


class ExtractRunLogger:
    def __init__(
        self,
        state_dir: Path,
        *,
        command: str,
        fingerprint: str,
    ) -> None:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = state_dir / "runs" / f"{command}-{fingerprint[:12]}-{stamp}"
        self.batches_dir = self.run_dir / "batches"
        self.batches_dir.mkdir(parents=True, exist_ok=True)
        self.command = command
        self.fingerprint = fingerprint
        self.started_at = datetime.now(tz=UTC).isoformat()
        self.batch_summaries: list[dict[str, object]] = []

    def log_batch(
        self,
        *,
        batch_index: int,
        attempted: int,
        extracted: int,
        skipped: int,
        failed: int,
        outcomes: list[LemmaOutcome],
    ) -> Path:
        summary = {
            "batch_index": batch_index,
            "attempted": attempted,
            "extracted": extracted,
            "skipped": skipped,
            "failed": failed,
            "outcome_count": len(outcomes),
        }
        self.batch_summaries.append(cast(dict[str, object], summary))
        batch_path = self.batches_dir / f"batch-{batch_index:05d}.jsonl"
        with batch_path.open("w", encoding="utf-8") as handle:
            for item in outcomes:
                handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
        return batch_path

    def finalize(
        self,
        *,
        totals: dict[str, int],
        pending_left: int,
        report_path: str | None = None,
    ) -> Path:
        manifest = {
            "command": self.command,
            "fingerprint": self.fingerprint,
            "started_at": self.started_at,
            "finished_at": datetime.now(tz=UTC).isoformat(),
            "batches": self.batch_summaries,
            "totals": totals,
            "pending_left": pending_left,
            "report_path": report_path,
        }
        path = self.run_dir / "run-manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
