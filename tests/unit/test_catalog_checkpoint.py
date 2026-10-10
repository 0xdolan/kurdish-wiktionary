from pathlib import Path

from src.catalog.checkpoint import (
    CatalogCheckpoint,
    clear_checkpoint,
    fingerprint_zim_paths,
    load_checkpoint,
    save_checkpoint,
)
from src.catalog.cli_progress import BatchRunTotals


def test_checkpoint_save_load_roundtrip(tmp_path: Path) -> None:
    fp = fingerprint_zim_paths([Path("/tmp/a.zim"), Path("/tmp/b.zim")])
    cp = CatalogCheckpoint(
        command="extract-canonical",
        fingerprint=fp,
        limit=5000,
        run_all=True,
        batch_index=3,
        totals=BatchRunTotals(batches=3, attempted=15000, extracted=14000, skipped=900, failed=100),
    )
    save_checkpoint(tmp_path, cp)
    loaded = load_checkpoint(tmp_path, "extract-canonical", fp)
    assert loaded is not None
    assert loaded.batch_index == 3
    assert loaded.totals.extracted == 14000
    clear_checkpoint(tmp_path, "extract-canonical", fp)
    assert load_checkpoint(tmp_path, "extract-canonical", fp) is None
