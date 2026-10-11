"""JSONL failure logs for bulk media download runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class MediaDownloadRunLogger:
    def __init__(self, state_dir: Path) -> None:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = state_dir / "runs" / f"media-download-{stamp}"
        self.failures_path = self.run_dir / "failures.jsonl"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = datetime.now(tz=UTC).isoformat()
        self.failure_count = 0
        self.batch_summaries: list[dict[str, Any]] = []

    def log_failure(self, record: dict[str, Any]) -> None:
        self.failure_count += 1
        with self.failures_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_batch_summary(self, summary: dict[str, Any]) -> None:
        self.batch_summaries.append(summary)

    def finalize(self, *, totals: dict[str, Any], summary: dict[str, Any]) -> Path:
        manifest = {
            "command": "media-download-all",
            "started_at": self.started_at,
            "finished_at": datetime.now(tz=UTC).isoformat(),
            "failures_path": str(self.failures_path),
            "failure_count": self.failure_count,
            "batches": self.batch_summaries,
            "totals": totals,
            "corpus": summary,
        }
        path = self.run_dir / "run-manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
