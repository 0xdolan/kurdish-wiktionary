"""Detect catalog checkpoints that no longer match PostgreSQL (e.g. after volume wipe)."""

from __future__ import annotations

from src.catalog.checkpoint import CatalogCheckpoint
from src.catalog.stats import CanonicalStats, CatalogStats


def extract_checkpoint_stale_reason(
    checkpoint: CatalogCheckpoint,
    *,
    db: CanonicalStats | CatalogStats,
    is_canonical: bool,
) -> str | None:
    if checkpoint.totals.attempted == 0 and checkpoint.batch_index == 0:
        return None

    if is_canonical:
        assert isinstance(db, CanonicalStats)
        db_total = db.total
        db_extracted = db.extracted
        db_skipped = db.skipped
        db_failed = db.failed
        db_pending = db.pending
    else:
        assert isinstance(db, CatalogStats)
        db_total = db.wordlist_total
        db_extracted = db.wordlist_extracted
        db_skipped = db.wordlist_skipped
        db_failed = db.wordlist_failed
        db_pending = db.wordlist_pending

    if checkpoint.db_corpus_total is not None and db_total != checkpoint.db_corpus_total:
        return (
            f"corpus size changed ({checkpoint.db_corpus_total:,} → {db_total:,}); "
            "database was likely re-synced or reset"
        )

    claimed_done = (
        checkpoint.totals.extracted + checkpoint.totals.skipped + checkpoint.totals.failed
    )
    actual_done = db_extracted + db_skipped + db_failed
    if claimed_done > 50 and actual_done + 20 < claimed_done:
        return (
            f"database progress behind checkpoint (db finished={actual_done:,}, "
            f"checkpoint finished={claimed_done:,}); likely fresh or restored empty database"
        )

    if (
        checkpoint.totals.attempted > 100
        and db_pending > 0
        and db_extracted < max(1, checkpoint.totals.extracted // 2)
    ):
        return (
            "most lemmas still pending in SQL but checkpoint records large progress; "
            "use --no-resume after a fresh database rebuild"
        )

    return None


def sync_checkpoint_stale_reason(
    checkpoint: CatalogCheckpoint,
    *,
    db_row_count: int,
) -> str | None:
    if checkpoint.upsert_offset == 0 and checkpoint.totals.attempted == 0:
        return None
    if db_row_count == 0 and checkpoint.upsert_offset > 0:
        return "database empty but checkpoint has sync progress (Postgres volume was likely wiped)"
    if (
        checkpoint.db_corpus_total is not None
        and db_row_count != checkpoint.db_corpus_total
        and checkpoint.upsert_offset >= db_row_count
        and db_row_count > 0
    ):
        return (
            f"corpus size changed ({checkpoint.db_corpus_total:,} → {db_row_count:,}) "
            "while sync checkpoint is ahead of the new corpus"
        )
    if checkpoint.upsert_offset > db_row_count + 1000 and db_row_count > 0:
        return "sync upsert offset exceeds current row count; checkpoint is stale"
    return None
