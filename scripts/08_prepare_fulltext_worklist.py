#!/usr/bin/env python3
"""Prepare the full-text eligibility worklist.

Filters outputs/csv/master_records.csv to records where
title_abstract_human_decision == "include" (i.e., the researcher has
already approved title/abstract screening — Phase 3 must be complete
before this is meaningful). For each, checks whether a legal OA PDF is
already present in outputs/corpus/ (per outputs/corpus/corpus_manifest.csv)
and flags pdf_available accordingly.

Writes outputs/csv/fulltext_eligibility_worklist.csv.

Usage:
    python scripts/08_prepare_fulltext_worklist.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, log_run_event, read_csv_rows, write_csv_rows  # noqa: E402

WORKLIST_FIELDS = [
    "record_id", "doi_normalized", "doi_url", "title", "authors",
    "publication_year", "journal_name", "open_access_status", "open_access_url",
    "pdf_available", "fulltext_ai_decision", "fulltext_ai_reason",
    "fulltext_ai_rationale", "fulltext_human_decision", "notes",
]


def load_corpus_dois(manifest_path: Path) -> set[str]:
    rows = read_csv_rows(manifest_path)
    return {r.get("doi_normalized", "") for r in rows if r.get("doi_normalized")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=str(OUTPUTS_DIR / "csv" / "master_records.csv"))
    parser.add_argument("--corpus-manifest", default=str(OUTPUTS_DIR / "corpus" / "corpus_manifest.csv"))
    parser.add_argument("--output", default=str(OUTPUTS_DIR / "csv" / "fulltext_eligibility_worklist.csv"))
    args = parser.parse_args()

    records = read_csv_rows(Path(args.records))
    included = [r for r in records if r.get("title_abstract_human_decision") == "include"]

    if not included:
        print("No records with title_abstract_human_decision == 'include' found.")
        print("Complete and approve Phase 3 (title/abstract screening) first.")
        return 0

    corpus_dois = load_corpus_dois(Path(args.corpus_manifest))

    rows = []
    for r in included:
        row = {k: r.get(k, "") for k in WORKLIST_FIELDS if k != "pdf_available"}
        row["pdf_available"] = "yes" if r.get("doi_normalized") in corpus_dois else "no"
        row["fulltext_ai_decision"] = row.get("fulltext_ai_decision") or "pending"
        row["fulltext_human_decision"] = "pending"
        rows.append(row)

    write_csv_rows(Path(args.output), rows, WORKLIST_FIELDS)
    n_with_pdf = sum(1 for r in rows if r["pdf_available"] == "yes")
    log_run_event({
        "stage": "prepare_fulltext_worklist",
        "total_included_title_abstract": len(included),
        "with_legal_oa_pdf": n_with_pdf,
        "without_pdf": len(rows) - n_with_pdf,
    })

    print(f"Records approved at title/abstract stage: {len(included)}")
    print(f"  with legal OA PDF already in corpus: {n_with_pdf}")
    print(f"  without PDF (need 09_download_legal_oa_pdfs.py or manual supply): {len(rows) - n_with_pdf}")
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
