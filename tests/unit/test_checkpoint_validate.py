from src.catalog.checkpoint import CatalogCheckpoint
from src.catalog.checkpoint_validate import (
    extract_checkpoint_stale_reason,
    sync_checkpoint_stale_reason,
)
from src.catalog.cli_progress import BatchRunTotals
from src.catalog.stats import CanonicalStats


def test_extract_stale_when_db_empty_but_checkpoint_has_progress() -> None:
    checkpoint = CatalogCheckpoint(
        command="extract-canonical",
        fingerprint="abc",
        limit=10_000,
        run_all=True,
        batch_index=4,
        pending_at_start=1_034_709,
        db_corpus_total=1_034_709,
        totals=BatchRunTotals(batches=4, attempted=40_000, extracted=40_754, skipped=19, failed=2),
    )
    db = CanonicalStats(
        total=1_034_709,
        pending=1_034_709,
        extracted=0,
        skipped=0,
        failed=0,
        in_all_configured_zims=0,
        in_one_zim_only=0,
        entries_total=0,
    )
    reason = extract_checkpoint_stale_reason(checkpoint, db=db, is_canonical=True)
    assert reason is not None
    assert "fresh" in reason.lower() or "behind" in reason.lower()


def test_extract_valid_when_db_matches_checkpoint() -> None:
    checkpoint = CatalogCheckpoint(
        command="extract-canonical",
        fingerprint="abc",
        limit=10_000,
        run_all=True,
        batch_index=4,
        pending_at_start=1_034_709,
        db_corpus_total=1_034_709,
        totals=BatchRunTotals(batches=4, attempted=40_000, extracted=40_000, skipped=0, failed=0),
    )
    db = CanonicalStats(
        total=1_034_709,
        pending=994_709,
        extracted=40_000,
        skipped=0,
        failed=0,
        in_all_configured_zims=0,
        in_one_zim_only=0,
        entries_total=40_000,
    )
    assert extract_checkpoint_stale_reason(checkpoint, db=db, is_canonical=True) is None


def test_sync_stale_when_db_empty() -> None:
    checkpoint = CatalogCheckpoint(
        command="sync-canonical",
        fingerprint="abc",
        limit=0,
        run_all=False,
        upsert_offset=500_000,
    )
    reason = sync_checkpoint_stale_reason(checkpoint, db_row_count=0)
    assert reason is not None
    assert "empty" in reason.lower()
