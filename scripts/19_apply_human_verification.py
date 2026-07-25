#!/usr/bin/env python3
"""Phase 4c: Apply real human verification decisions to evidence_extraction.csv
and quality_appraisal.csv.

This script does NOT decide anything and does NOT read PDFs. It only takes a
list of record_ids the researcher has personally checked against the PDF and
flips human_verified=true (+ reviewer_name/review_date) for exactly those rows.
Every other row is left untouched. This is intentionally the only path by
which human_verified can become true in this pipeline.

Usage:
    # Mark specific records verified after you've checked them against the PDF
    python scripts/19_apply_human_verification.py \\
        --ids REC-001072 REC-007641 REC-012475 \\
        --reviewer "Vairamuthu" --both

    # Or from a file (one record_id per line) -- e.g. everything you ticked
    # off in outputs/csv/human_review_worklist.csv
    python scripts/19_apply_human_verification.py \\
        --ids-file outputs/csv/verified_ids.txt \\
        --reviewer "Vairamuthu" --extraction-only

    # Check current progress toward the Phase 5 gate (60% human-verified)
    python scripts/19_apply_human_verification.py --status
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, log_run_event, read_csv_rows, write_csv_rows

EXTRACTION = OUTPUTS_DIR / "csv" / "evidence_extraction.csv"
APPRAISAL = OUTPUTS_DIR / "csv" / "quality_appraisal.csv"


def _apply(path: Path, ids: set[str], status_field: str, reviewer: str, today: str) -> tuple[int, int]:
    rows = read_csv_rows(path)
    fieldnames = list(rows[0].keys())
    if "pipeline_stage" not in fieldnames:
        fieldnames = fieldnames + ["pipeline_stage"]
    changed = 0
    for r in rows:
        if r["record_id"] not in ids:
            continue
        r["human_verified"] = "true"
        r["pipeline_stage"] = "RESEARCHER_CONFIRMED"
        if "reviewer_name" in r:
            r["reviewer_name"] = reviewer
        if "review_date" in r:
            r["review_date"] = today
        changed += 1
    write_csv_rows(path, rows, fieldnames)
    return changed, len(rows)


def _status() -> None:
    from collections import Counter
    for path, status_field, label in [
        (EXTRACTION, "extraction_status", "evidence_extraction.csv"),
        (APPRAISAL, "quality_appraisal_status", "quality_appraisal.csv"),
    ]:
        if not path.exists():
            continue
        rows = read_csv_rows(path)
        included = [r for r in rows if r.get(status_field, "").startswith("ai_") or r.get(status_field) == "human_verified"]
        verified = [r for r in included if r.get("human_verified", "").lower() == "true"]
        n = len(included)
        v = len(verified)
        pct = (100 * v / n) if n else 0
        gate = "PASSES (>=60%)" if pct >= 60 else f"needs {int(0.6*n) - v} more to hit 60%"
        stages = Counter(r.get("pipeline_stage", "(unset)") for r in rows)
        print(f"{label}: {v}/{n} human-verified ({pct:.1f}%) — Phase 5 gate: {gate}")
        print(f"  pipeline_stage breakdown: {dict(stages)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", nargs="*", default=[], help="record_ids you have personally checked")
    parser.add_argument("--ids-file", help="Path to a file with one record_id per line")
    parser.add_argument("--reviewer", default="", help="Your name, recorded in reviewer_name")
    parser.add_argument("--extraction-only", action="store_true")
    parser.add_argument("--appraisal-only", action="store_true")
    parser.add_argument("--status", action="store_true", help="Just print current verified % (no changes)")
    args = parser.parse_args()

    if args.status:
        _status()
        return 0

    ids = set(args.ids)
    if args.ids_file:
        ids |= {line.strip() for line in Path(args.ids_file).read_text().splitlines() if line.strip()}

    if not ids:
        print("No record_ids given. Use --ids, --ids-file, or --status.")
        return 1
    if not args.reviewer:
        print("ERROR: --reviewer is required so verification is attributable (who actually checked this).")
        return 1

    today = dt.date.today().isoformat()
    total_changed = 0
    if not args.appraisal_only:
        n, total = _apply(EXTRACTION, ids, "extraction_status", args.reviewer, today)
        print(f"evidence_extraction.csv: {n} rows marked human_verified=true (of {len(ids)} ids given)")
        total_changed += n
    if not args.extraction_only:
        n, total = _apply(APPRAISAL, ids, "quality_appraisal_status", args.reviewer, today)
        print(f"quality_appraisal.csv:   {n} rows marked human_verified=true (of {len(ids)} ids given)")
        total_changed += n

    log_run_event({
        "stage": "apply_human_verification",
        "ids_submitted": len(ids),
        "reviewer": args.reviewer,
    })
    print()
    _status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
