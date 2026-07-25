#!/usr/bin/env python3
"""Import user-supplied venue quality source exports (Scopus Sources list
and/or SCImago/SJR export) from data/raw/venue_quality_sources/ and
normalize them into a single lookup table:
data/processed/venue_quality_lookup.csv

Expected inputs (place in data/raw/venue_quality_sources/, any of):
  - scopus_sources_*.csv  (official Scopus Sources export; must contain at
    least: Source Title, Print-ISSN / E-ISSN, Citescore / SJR columns as
    provided by Scopus)
  - scimago_*.csv (SCImago Journal Rank export; contains Title, Issn,
    SJR, H index, Categories with quartile e.g. "Computer Science (Q1)")

This script does NOT fabricate or guess any value — rows that cannot be
parsed into ISSN + quartile are still imported but flagged
parse_status=needs_review so a human can inspect them before
06_match_venues_q1_q2.py consumes the lookup table.

Usage:
    python scripts/05_import_venue_quality_sources.py
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, normalize_issn, normalize_title, log_run_event  # noqa: E402

LOOKUP_FIELDS = [
    "source_file", "source_type", "journal_title", "journal_title_normalized",
    "issn_print", "issn_electronic", "category", "quartile", "year",
    "sjr_value", "h_index", "parse_status",
]

SCIMAGO_QUARTILE_RE = re.compile(r"\((Q[1-4])\)")


def parse_scimago_row(row: dict, source_file: str) -> dict:
    lower = {k.strip().lower(): v for k, v in row.items()}
    title = lower.get("title", "").strip()
    issn_raw = lower.get("issn", "")
    issns = [s.strip() for s in re.split(r"[,;]", issn_raw) if s.strip()]
    issn1 = normalize_issn(issns[0]) if len(issns) > 0 else None
    issn2 = normalize_issn(issns[1]) if len(issns) > 1 else None

    categories_field = lower.get("categories", "")
    quartiles = SCIMAGO_QUARTILE_RE.findall(categories_field)
    best_quartile = min(quartiles) if quartiles else None  # 'Q1' < 'Q2' lexically works here

    sjr_raw = lower.get("sjr", "").replace(",", ".").strip()
    try:
        sjr_value = float(sjr_raw) if sjr_raw else None
    except ValueError:
        sjr_value = None

    h_index_raw = lower.get("h index", "").strip()
    h_index = int(h_index_raw) if h_index_raw.isdigit() else None

    parse_status = "ok" if (title and (issn1 or issn2) and best_quartile) else "needs_review"

    return {
        "source_file": source_file,
        "source_type": "scimago",
        "journal_title": title,
        "journal_title_normalized": normalize_title(title),
        "issn_print": issn1 or "",
        "issn_electronic": issn2 or "",
        "category": categories_field,
        "quartile": best_quartile or "",
        "year": lower.get("year", ""),
        "sjr_value": sjr_value if sjr_value is not None else "",
        "h_index": h_index if h_index is not None else "",
        "parse_status": parse_status,
    }


def parse_scopus_sources_row(row: dict, source_file: str) -> dict:
    lower = {k.strip().lower(): v for k, v in row.items()}
    title = lower.get("source title", lower.get("title", "")).strip()
    issn1 = normalize_issn(lower.get("print-issn", lower.get("issn", "")))
    issn2 = normalize_issn(lower.get("e-issn", lower.get("eissn", "")))

    parse_status = "ok" if (title and (issn1 or issn2)) else "needs_review"
    # Scopus Sources exports do not carry a quartile column directly; quartile
    # must come from SCImago or a user-supplied percentile-to-quartile mapping.
    # Leave quartile blank here — never guess it.
    return {
        "source_file": source_file,
        "source_type": "scopus_sources",
        "journal_title": title,
        "journal_title_normalized": normalize_title(title),
        "issn_print": issn1 or "",
        "issn_electronic": issn2 or "",
        "category": lower.get("all science journal classification codes (asjc)", ""),
        "quartile": "",
        "year": "",
        "sjr_value": "",
        "h_index": lower.get("citescore", ""),
        "parse_status": parse_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default=str(DATA_DIR / "raw" / "venue_quality_sources"))
    parser.add_argument("--output", default=str(DATA_DIR / "processed" / "venue_quality_lookup.csv"))
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    files = sorted(input_dir.glob("*.csv"))
    if not files:
        print(f"No venue quality source files found in {input_dir}.")
        print("Add a Scopus Sources export (scopus_sources_*.csv) and/or a "
              "SCImago export (scimago_*.csv), then re-run.")
        return 0

    all_rows = []
    for f in files:
        with f.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv_mod.DictReader(fh)
            for row in reader:
                if "scimago" in f.stem.lower():
                    all_rows.append(parse_scimago_row(row, f.name))
                else:
                    all_rows.append(parse_scopus_sources_row(row, f.name))
        print(f"Parsed {f.name}: {sum(1 for r in all_rows if r['source_file'] == f.name)} rows")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv_mod.DictWriter(fh, fieldnames=LOOKUP_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    needs_review = sum(1 for r in all_rows if r["parse_status"] == "needs_review")
    log_run_event({
        "stage": "import_venue_quality_sources",
        "files_processed": len(files),
        "rows_imported": len(all_rows),
        "needs_review": needs_review,
        "output": str(out_path),
    })
    print(f"\nTotal venue rows imported: {len(all_rows)} ({needs_review} need manual review)")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
