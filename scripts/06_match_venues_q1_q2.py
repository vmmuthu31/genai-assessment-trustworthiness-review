#!/usr/bin/env python3
"""Match master_records.csv journals against the venue quality lookup table
(data/processed/venue_quality_lookup.csv, built by
05_import_venue_quality_sources.py) to fill scimago_quartile, sjr_value,
journal_h_index, venue_match_status, and venue_match_confidence.

Matching strategy (never guesses):
  1. ISSN match (print or electronic) against lookup rows with parse_status=ok
     -> venue_match_confidence=high.
  2. If no ISSN match, fuzzy title match (rapidfuzz) against lookup journal
     titles, threshold DEFAULT_FUZZY_VENUE_THRESHOLD -> venue_match_confidence=medium.
  3. No match -> venue_match_status=unmatched, scimago_quartile left blank.
     Per config/inclusion_exclusion.yaml, unmatched records cannot be part of
     the Q1/Q2 core set (exclusion reason E10) until manually verified.

Usage:
    python scripts/06_match_venues_q1_q2.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA_DIR,
    OUTPUTS_DIR,
    DEFAULT_FUZZY_VENUE_THRESHOLD,
    fuzzy_title_score,
    log_run_event,
    master_records_fieldnames,
    normalize_issn,
    read_csv_rows,
    write_csv_rows,
)
from datetime import date


def load_lookup(path: Path) -> list[dict]:
    rows = read_csv_rows(path)
    return [r for r in rows if r.get("parse_status") == "ok"]


def match_by_issn(record: dict, lookup: list[dict]) -> dict | None:
    r_issns = {
        normalize_issn(record.get("issn_print", "")),
        normalize_issn(record.get("issn_electronic", "")),
    }
    r_issns.discard(None)
    if not r_issns:
        return None
    for entry in lookup:
        l_issns = {entry.get("issn_print") or None, entry.get("issn_electronic") or None}
        l_issns.discard(None)
        if r_issns & l_issns:
            return entry
    return None


def match_by_title(record: dict, lookup: list[dict], threshold: float) -> tuple[dict | None, float]:
    best_entry, best_score = None, 0.0
    for entry in lookup:
        score = fuzzy_title_score(record.get("journal_name", ""), entry.get("journal_title", ""))
        if score > best_score:
            best_entry, best_score = entry, score
    if best_entry and best_score >= threshold:
        return best_entry, best_score
    return None, best_score


def apply_match(record: dict, entry: dict | None, confidence: str) -> None:
    if entry is None:
        record["venue_match_status"] = "unmatched"
        record["venue_match_confidence"] = "NR"
        return
    record["venue_match_status"] = "matched"
    record["venue_match_confidence"] = confidence
    if entry.get("quartile"):
        record["scimago_quartile"] = entry["quartile"]
        record["scimago_category"] = entry.get("category", "")
        record["scimago_year"] = entry.get("year", "")
    if entry.get("sjr_value"):
        record["sjr_value"] = entry["sjr_value"]
    if entry.get("h_index"):
        record["journal_h_index"] = entry["h_index"]
    record["scopus_verification_date"] = date.today().isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=str(OUTPUTS_DIR / "csv" / "master_records.csv"))
    parser.add_argument("--lookup", default=str(DATA_DIR / "processed" / "venue_quality_lookup.csv"))
    parser.add_argument("--fuzzy-threshold", type=float, default=DEFAULT_FUZZY_VENUE_THRESHOLD)
    args = parser.parse_args()

    records = read_csv_rows(Path(args.records))
    if not records:
        print(f"No records found in {args.records}.")
        return 0

    lookup = load_lookup(Path(args.lookup))
    if not lookup:
        print(f"No usable (parse_status=ok) rows in {args.lookup}. "
              f"Run 05_import_venue_quality_sources.py first with real venue data.")
        return 0

    n_high = n_medium = n_unmatched = 0
    for record in records:
        entry = match_by_issn(record, lookup)
        if entry:
            apply_match(record, entry, "high")
            n_high += 1
            continue
        entry, score = match_by_title(record, lookup, args.fuzzy_threshold)
        if entry:
            apply_match(record, entry, "medium")
            n_medium += 1
        else:
            apply_match(record, None, "NR")
            n_unmatched += 1

    write_csv_rows(Path(args.records), records, master_records_fieldnames())
    log_run_event({
        "stage": "match_venues_q1_q2",
        "total_records": len(records),
        "matched_high_confidence_issn": n_high,
        "matched_medium_confidence_title": n_medium,
        "unmatched": n_unmatched,
    })

    print(f"Total records: {len(records)}")
    print(f"  matched (ISSN, high confidence):   {n_high}")
    print(f"  matched (fuzzy title, medium conf): {n_medium}")
    print(f"  unmatched (excluded from Q1/Q2 core until manually verified): {n_unmatched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
