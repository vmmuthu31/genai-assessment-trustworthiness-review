#!/usr/bin/env python3
"""Phase 2: Deduplication of master_records.csv.

Two-pass deduplication:
  Pass 1 — DOI: exact match on normalized DOI (lowercase, no prefix). The
           first-seen record with a given DOI is marked "unique"; later
           records sharing that DOI are marked "duplicate" and point back to
           the first via duplicate_of_record_id.
  Pass 2 — Fuzzy title: for records WITHOUT a DOI, compare titles within the
           same publication year using difflib.SequenceMatcher. Pairs above
           --threshold (default 91%) are flagged "needs_manual_review" (never
           auto-merged — human must decide). Records with a DOI are excluded
           from this pass.

After both passes, any DOI-missing record still at "pending" / "" is set to
"needs_manual_review" (cannot be auto-deduplicated without a DOI).

Usage:
    python scripts/04_normalize_deduplicate.py --write
    python scripts/04_normalize_deduplicate.py --write --threshold 93
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    MASTER_RECORDS_CSV,
    master_records_fieldnames,
    normalize_doi,
    doi_url,
    read_csv_rows,
    write_csv_rows,
    log_run_event,
)


# ---------------------------------------------------------------------------
# Pass 1: DOI normalization + DOI-based dedup
# ---------------------------------------------------------------------------

def normalize_all_dois(rows: list[dict]) -> None:
    """Normalize doi_raw -> doi_normalized + doi_url for every row in-place."""
    for row in rows:
        raw = row.get("doi_raw") or ""
        norm = normalize_doi(raw) if raw else ""
        row["doi_normalized"] = norm or ""
        row["doi_url"] = doi_url(norm) if norm else ""


def dedup_by_doi(rows: list[dict]) -> list[dict]:
    """Group rows by doi_normalized; mark first-seen as 'unique', later as
    'duplicate' pointing to the first.  Returns a list of dedup event dicts
    for logging.  Rows without a DOI are left untouched."""
    seen: dict[str, str] = {}  # doi_normalized -> record_id (first-seen)
    events: list[dict] = []
    for row in rows:
        doi = row.get("doi_normalized") or ""
        if not doi:
            continue
        rid = row.get("record_id", "")
        status = row.get("deduplication_status") or ""
        if doi not in seen:
            seen[doi] = rid
            if not status or status == "pending":
                row["deduplication_status"] = "unique"
        else:
            row["deduplication_status"] = "duplicate"
            row["duplicate_of_record_id"] = seen[doi]
            events.append({
                "stage": "dedup_by_doi",
                "record_id_1": seen[doi],
                "record_id_2": rid,
                "doi_normalized": doi,
            })
    return events


# ---------------------------------------------------------------------------
# Pass 2: Fuzzy title matching for DOI-missing records
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def dedup_by_fuzzy_title(rows: list[dict], threshold: float = 91.0) -> list[dict]:
    """For DOI-missing records only: compare titles within the same publication
    year.  Pairs above *threshold* are flagged 'needs_manual_review' (never
    auto-merged).  Returns event dicts for logging."""
    no_doi = [
        r for r in rows
        if not (r.get("doi_normalized") or "")
        and (r.get("deduplication_status") or "") not in ("duplicate", "unique")
    ]
    by_year: dict[str, list[dict]] = defaultdict(list)
    for r in no_doi:
        yr = r.get("publication_year") or ""
        if yr:
            by_year[yr].append(r)

    events: list[dict] = []
    for year, group in by_year.items():
        for i in range(len(group)):
            a = group[i]
            if (a.get("deduplication_status") or "") in ("duplicate", "unique"):
                continue
            ta = _normalize_title(a.get("title") or "")
            if not ta:
                continue
            for j in range(i + 1, len(group)):
                b = group[j]
                if (b.get("deduplication_status") or "") in ("duplicate", "unique"):
                    continue
                tb = _normalize_title(b.get("title") or "")
                if not tb:
                    continue
                sim = SequenceMatcher(None, ta, tb).ratio() * 100
                if sim >= threshold:
                    b["deduplication_status"] = "needs_manual_review"
                    b["duplicate_of_record_id"] = a.get("record_id", "")
                    events.append({
                        "stage": "dedup_by_fuzzy_title",
                        "record_id_1": a.get("record_id", ""),
                        "record_id_2": b.get("record_id", ""),
                        "similarity": round(sim, 1),
                        "auto_merged": False,
                    })
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true",
                        help="Write deduplicated master_records.csv (without flag: dry-run).")
    parser.add_argument("--threshold", type=float, default=91.0,
                        help="Fuzzy title similarity threshold (%%) for DOI-missing records "
                             "(default: 91).")
    args = parser.parse_args()

    rows = read_csv_rows(MASTER_RECORDS_CSV)
    if not rows:
        print(f"No rows in {MASTER_RECORDS_CSV}.")
        return 0

    total = len(rows)
    print(f"Loaded {total} rows from {MASTER_RECORDS_CSV}")

    # Pass 1: DOI
    normalize_all_dois(rows)
    doi_events = dedup_by_doi(rows)
    n_dup_doi = sum(1 for r in rows if r.get("deduplication_status") == "duplicate")
    n_unique_doi = sum(1 for r in rows if r.get("deduplication_status") == "unique")
    print(f"Pass 1 (DOI): {n_unique_doi} unique, {n_dup_doi} duplicate "
          f"({len(doi_events)} DOI-group merges)")

    # Pass 2: fuzzy title (DOI-missing only)
    fuzzy_events = dedup_by_fuzzy_title(rows, threshold=args.threshold)
    n_manual = sum(1 for r in rows if r.get("deduplication_status") == "needs_manual_review")
    print(f"Pass 2 (fuzzy title, threshold={args.threshold}%): "
          f"{len(fuzzy_events)} pairs flagged, {n_manual} total needs_manual_review")

    # Final: DOI-missing records still at pending/"" -> needs_manual_review
    n_pending = 0
    for r in rows:
        status = r.get("deduplication_status") or ""
        if not (r.get("doi_normalized") or "") and status not in (
            "unique", "duplicate", "needs_manual_review"
        ):
            r["deduplication_status"] = "needs_manual_review"
            n_pending += 1
    if n_pending:
        print(f"Final pass: {n_pending} DOI-missing records -> needs_manual_review")

    # Summary
    counts = defaultdict(int)
    for r in rows:
        counts[r.get("deduplication_status", "")] += 1
    print(f"\nFinal status breakdown:")
    for status in ("unique", "duplicate", "needs_manual_review", "pending"):
        if counts[status]:
            print(f"  {status or '(empty)'}: {counts[status]}")
    print(f"  TOTAL: {total}")

    if args.write:
        write_csv_rows(MASTER_RECORDS_CSV, rows, master_records_fieldnames())
        print(f"\nWrote {total} rows to {MASTER_RECORDS_CSV}")
        log_run_event({
            "stage": "deduplicate",
            "total_rows": total,
            "doi_unique": counts.get("unique", 0),
            "doi_duplicate": counts.get("duplicate", 0),
            "fuzzy_pairs": len(fuzzy_events),
            "needs_manual_review": counts.get("needs_manual_review", 0),
            "threshold": args.threshold,
        })
    else:
        print("\nDry run (no --write): master_records.csv was not modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
