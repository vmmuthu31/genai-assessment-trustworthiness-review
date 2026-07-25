#!/usr/bin/env python3
"""Phase 4: Initialize evidence extraction CSV from screened included records.

Creates outputs/csv/evidence_extraction.csv with one row per included
record and all extraction fields initialized to 'NR' (not reported).
This is the template that the Evidence Extraction Agent
(prompts/08_evidence_extractor.md) fills in after reading each PDF.

The script reads the screening worklist (or shortlist) for records with
title_abstract_ai_decision == 'include' (or title_abstract_human_decision
if available) and creates a blank extraction row for each.

Usage:
    python scripts/15_initialize_extraction.py
    python scripts/15_initialize_extraction.py --input outputs/csv/title_abstract_screening_worklist.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_DIR,
    evidence_extraction_fieldnames,
    log_run_event,
    read_csv_rows,
    write_csv_rows,
)

EXTRACTION_OUTPUT = OUTPUTS_DIR / "csv" / "evidence_extraction.csv"


def _citation_key(row: dict) -> str:
    """Generate citation key from first author surname + year. e.g. Smith2025."""
    authors = row.get("authors", "")
    year = row.get("publication_year", "")
    if not authors or not year:
        return ""
    first = authors.split(";")[0].strip()
    parts = first.split()
    surname = parts[-1] if parts else ""
    return f"{surname}{year}" if surname else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=str(OUTPUTS_DIR / "csv" / "title_abstract_screening_worklist.csv"),
                        help="Screening worklist CSV (default: title_abstract_screening_worklist.csv).")
    parser.add_argument("--output", default=str(EXTRACTION_OUTPUT),
                        help="Output extraction CSV.")
    args = parser.parse_args()

    # Read input
    rows = read_csv_rows(Path(args.input))
    if not rows:
        print(f"No rows in {args.input}.")
        return 0

    # Filter to included records. Human decision takes precedence if
    # explicitly set (not "pending"); otherwise use AI draft decision.
    included = []
    for r in rows:
        human = (r.get("title_abstract_human_decision") or "").strip().lower()
        ai = (r.get("title_abstract_ai_decision") or "").strip().lower()
        decision = human if human and human != "pending" else ai
        if decision == "include":
            included.append(r)

    print(f"Input rows: {len(rows)}")
    print(f"Included (AI or human): {len(included)}")

    if not included:
        print("No included records — nothing to extract.")
        return 0

    # Build extraction rows
    fieldnames = evidence_extraction_fieldnames()

    # Enrich with author data from master (needed for citation_key)
    master_rows = read_csv_rows(OUTPUTS_DIR / "csv" / "master_records.csv")
    master_by_id = {r.get("record_id"): r for r in master_rows}

    extraction_rows = []
    for r in included:
        master = master_by_id.get(r.get("record_id"), {})
        merged = {**master, **{k: v for k, v in r.items() if v}}  # worklist overrides master, but only non-empty
        row = {f: "NR" for f in fieldnames}  # all fields default to NR
        # Populate known bibliographic fields
        row["record_id"] = merged.get("record_id", "")
        row["doi_normalized"] = merged.get("doi_normalized", "")
        row["citation_key"] = _citation_key(merged)
        row["extraction_status"] = "pending"
        extraction_rows.append(row)

    # Check if output already exists
    if Path(args.output).exists():
        existing = read_csv_rows(Path(args.output))
        existing_ids = {r.get("record_id") for r in existing}
        new_rows = [r for r in extraction_rows if r["record_id"] not in existing_ids]
        skipped = len(extraction_rows) - len(new_rows)
        extraction_rows = existing + new_rows
        print(f"\nOutput exists with {len(existing)} rows. Added {len(new_rows)} new, skipped {skipped} existing.")
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    write_csv_rows(Path(args.output), extraction_rows, fieldnames)
    print(f"Wrote {len(extraction_rows)} rows to {args.output}")
    print(f"  extraction_status: all set to 'pending' (awaiting PDF + agent extraction)")

    log_run_event({
        "stage": "initialize_extraction",
        "input_rows": len(rows),
        "included_rows": len(included),
        "extraction_rows": len(extraction_rows),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
