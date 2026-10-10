import json

from src.catalog.outcomes import OutcomeCategoryCount, OutcomeReport, OutcomeRow, report_to_json


def test_report_to_json_serializes_slotted_outcome_rows() -> None:
    report = OutcomeReport(
        scope="canonical",
        generated_at="2026-01-01T00:00:00+00:00",
        skipped_total=1,
        failed_total=0,
        categories=[
            OutcomeCategoryCount(
                status="skipped",
                category="no_definitions_or_phonetics",
                count=1,
                sample_titles=["'eyne"],
            )
        ],
        rows=[
            OutcomeRow(
                title="'eyne",
                title_normalized="eyne",
                status="skipped",
                reason="No definitions or phonetics",
                category="no_definitions_or_phonetics",
                entry_id=None,
                extracted_at=None,
                retry_hint="Expected for empty pages",
            )
        ],
    )
    payload = json.loads(report_to_json(report))
    assert payload["skipped_total"] == 1
    assert payload["rows"][0]["title"] == "'eyne"
    assert payload["rows"][0]["category"] == "no_definitions_or_phonetics"
