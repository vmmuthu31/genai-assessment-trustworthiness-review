#!/usr/bin/env python3
"""Phase 4: Initialize quality appraisal CSV from extracted records.

Creates outputs/csv/quality_appraisal.csv with one row per extracted
record and all 14 quality dimensions initialized to 'NR'. This is the
template that the Quality Appraisal Agent (prompts/09_quality_appraiser.md)
fills in after reading each PDF.

Reads evidence_extraction.csv for records with extraction_status in
{pending, ai_draft, human_verified} and creates a blank appraisal row.

Usage:
    python scripts/16_initialize_quality_appraisal.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_DIR,
    load_yaml,
    log_run_event,
    read_csv_rows,
    write_csv_rows,
)

QUALITY_OUTPUT = OUTPUTS_DIR / "csv" / "quality_appraisal.csv"

QUALITY_FIELDS_BASE = [
    "record_id", "doi_normalized", "citation_key",
]

QUALITY_FIELDS_DIMENSIONS = [
    "dataset_and_consent", "ground_truth_construction", "leakage_safeguards",
    "baseline_comparisons", "evaluation_metrics", "calibration",
    "grounding", "hallucination_testing", "fairness",
    "robustness", "human_evaluation", "reproducibility",
    "limitations_reporting", "funding_conflicts",
]

QUALITY_FIELDS_META = [
    "narrative_summary_draft",
    "quality_appraisal_status",
    "human_verified",
    "reviewer_name",
    "review_date",
]

ALL_QUALITY_FIELDS = QUALITY_FIELDS_BASE + QUALITY_FIELDS_DIMENSIONS + QUALITY_FIELDS_META


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=str(OUTPUTS_DIR / "csv" / "evidence_extraction.csv"),
                        help="Evidence extraction CSV (input).")
    parser.add_argument("--output", default=str(QUALITY_OUTPUT),
                        help="Output quality appraisal CSV.")
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.input))
    if not rows:
        print(f"No rows in {args.input}. Run 15_initialize_extraction.py first.")
        return 0

    # Include records that have been extracted or are pending
    eligible = [r for r in rows if r.get("extraction_status") in ("pending", "ai_draft", "human_verified")]
    print(f"Extraction rows: {len(rows)}")
    print(f"Eligible for appraisal: {len(eligible)}")

    if not eligible:
        print("No eligible records.")
        return 0

    appraisal_rows = []
    for r in eligible:
        row = {f: "NR" for f in ALL_QUALITY_FIELDS}
        row["record_id"] = r.get("record_id", "")
        row["doi_normalized"] = r.get("doi_normalized", "")
        row["citation_key"] = r.get("citation_key", "")
        row["quality_appraisal_status"] = "pending"
        row["human_verified"] = ""
        appraisal_rows.append(row)

    # Check if output already exists
    if Path(args.output).exists():
        existing = read_csv_rows(Path(args.output))
        existing_ids = {r.get("record_id") for r in existing}
        new_rows = [r for r in appraisal_rows if r["record_id"] not in existing_ids]
        skipped = len(appraisal_rows) - len(new_rows)
        appraisal_rows = existing + new_rows
        print(f"\nOutput exists with {len(existing)} rows. Added {len(new_rows)} new, skipped {skipped} existing.")
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    write_csv_rows(Path(args.output), appraisal_rows, ALL_QUALITY_FIELDS)
    print(f"Wrote {len(appraisal_rows)} rows to {args.output}")
    print(f"  14 dimensions: all set to 'NR' (awaiting PDF + agent appraisal)")
    print(f"  quality_appraisal_status: all set to 'pending'")

    log_run_event({
        "stage": "initialize_quality_appraisal",
        "extraction_rows": len(rows),
        "eligible_rows": len(eligible),
        "appraisal_rows": len(appraisal_rows),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
