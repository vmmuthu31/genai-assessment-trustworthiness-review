#!/usr/bin/env python3
"""Prepare the title/abstract screening worklist.

Filters outputs/csv/master_records.csv to records that are:
  - DOI-valid (doi_normalized present and shape-valid)
  - deduplication_status in {unique} (duplicates and needs_manual_review
    are excluded from screening until deduplication is resolved)
  - venue_match_status in {matched, pending} (fully unmatched records are
    still listed but flagged, since venue verification may lag screening)

Writes outputs/csv/title_abstract_screening_worklist.csv with all AI
decision columns pre-populated as "pending" — ready for the Screening
Agent (prompts/06_title_abstract_screener.md) to fill in AI drafts, and
for the human reviewer to make final calls.

Usage:
    python scripts/07_prepare_screening_worklist.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_DIR,
    is_valid_doi_shape,
    log_run_event,
    read_csv_rows,
    write_csv_rows,
)

WORKLIST_FIELDS = [
    "record_id", "doi_normalized", "doi_url", "title", "authors",
    "publication_year", "journal_name", "abstract", "venue_match_status",
    "scimago_quartile", "title_abstract_ai_decision", "title_abstract_ai_reason",
    "title_abstract_ai_rationale", "title_abstract_human_decision", "notes",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=str(OUTPUTS_DIR / "csv" / "master_records.csv"))
    parser.add_argument("--output", default=str(OUTPUTS_DIR / "csv" / "title_abstract_screening_worklist.csv"))
    args = parser.parse_args()

    records = read_csv_rows(Path(args.records))
    if not records:
        print(f"No records found in {args.records}. Run import/dedup/venue steps first.")
        return 0

    eligible = []
    skipped_no_doi = skipped_dup = 0
    for r in records:
        if not is_valid_doi_shape(r.get("doi_normalized")):
            skipped_no_doi += 1
            continue
        if r.get("deduplication_status") in ("duplicate", "needs_manual_review"):
            skipped_dup += 1
            continue
        row = {k: r.get(k, "") for k in WORKLIST_FIELDS}
        row["title_abstract_ai_decision"] = row.get("title_abstract_ai_decision") or "pending"
        row["title_abstract_human_decision"] = "pending"
        eligible.append(row)

    write_csv_rows(Path(args.output), eligible, WORKLIST_FIELDS)
    log_run_event({
        "stage": "prepare_screening_worklist",
        "total_input_records": len(records),
        "eligible_for_screening": len(eligible),
        "skipped_invalid_doi": skipped_no_doi,
        "skipped_duplicate_or_review": skipped_dup,
    })

    print(f"Total input records: {len(records)}")
    print(f"  eligible for screening: {len(eligible)}")
    print(f"  skipped (invalid/missing DOI): {skipped_no_doi}")
    print(f"  skipped (duplicate/needs manual review): {skipped_dup}")
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
