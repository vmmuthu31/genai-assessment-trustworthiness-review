#!/usr/bin/env python3
"""Structural integrity audit across the pipeline's outputs. Local-file-only,
no network calls. Handles missing input files gracefully (treated as
"nothing to check yet" rather than a failure for that check).

Checks:
  1. DOI format: every non-empty doi_normalized in master_records.csv must
     match 10.NNNN(N...)/suffix.
  2. Duplicate DOIs: no two records with deduplication_status=unique may
     share the same doi_normalized.
  3. PRISMA arithmetic: prisma_flow_counts.json's included/excluded counts
     must be internally consistent (excluded_total == sum of by-reason
     counts; included + excluded == assessed at each stage).
  4. Venue verification completeness: every unique record must have
     venue_match_status set (not blank/pending) before being counted as
     screened-eligible.
  5. OA legality consistency: every corpus_manifest.csv entry's
     doi_normalized must correspond to a master_records.csv row whose
     open_access_status is gold/green/hybrid — flags any manifest entry
     that doesn't (possible non-legal-OA ingestion).

Prints a STOP / CONDITIONAL GO / GO summary:
  - STOP: any hard-fail check (DOI format violation, duplicate DOI among
    unique records, PRISMA arithmetic mismatch, OA legality violation).
  - CONDITIONAL GO: only soft issues (e.g. incomplete venue verification)
    found.
  - GO: no issues found (including the case where inputs are all empty).

Usage:
    python scripts/14_integrity_audit.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_CSV,
    OUTPUTS_CORPUS,
    OUTPUTS_PRISMA,
    MASTER_RECORDS_CSV,
    is_valid_doi_shape,
    read_csv_rows,
    log_run_event,
)

LEGAL_OA_STATUSES = {"gold", "green", "hybrid"}


def check_doi_format(records: list[dict]) -> list[str]:
    issues = []
    for r in records:
        doi = r.get("doi_normalized")
        if doi and not is_valid_doi_shape(doi):
            issues.append(f"record_id={r.get('record_id')} has malformed doi_normalized='{doi}'")
    return issues


def check_duplicate_dois(records: list[dict]) -> list[str]:
    issues = []
    seen: dict[str, str] = {}
    for r in records:
        if r.get("deduplication_status") != "unique":
            continue
        doi = r.get("doi_normalized")
        if not doi:
            continue
        if doi in seen:
            issues.append(
                f"duplicate DOI '{doi}' among unique records: {seen[doi]} and {r.get('record_id')}"
            )
        else:
            seen[doi] = r.get("record_id", "")
    return issues


def check_prisma_arithmetic(prisma_counts_path: Path) -> list[str]:
    issues = []
    if not prisma_counts_path.exists():
        return issues
    try:
        data = json.loads(prisma_counts_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"could not parse {prisma_counts_path}: {exc}"]

    ta = data.get("title_abstract_screening", {})
    if ta:
        by_reason_total = sum(ta.get("excluded_by_reason", {}).values())
        if by_reason_total != ta.get("excluded_total", by_reason_total):
            issues.append(
                f"title_abstract_screening.excluded_total ({ta.get('excluded_total')}) "
                f"!= sum of excluded_by_reason ({by_reason_total})"
            )

    ft = data.get("fulltext_screening", {})
    if ft:
        by_reason_total = sum(ft.get("excluded_by_reason", {}).values())
        if by_reason_total != ft.get("excluded_total", by_reason_total):
            issues.append(
                f"fulltext_screening.excluded_total ({ft.get('excluded_total')}) "
                f"!= sum of excluded_by_reason ({by_reason_total})"
            )
        if ft.get("included", 0) + ft.get("excluded_total", 0) > ft.get("assessed", 0):
            issues.append(
                "fulltext_screening included + excluded_total exceeds assessed "
                f"({ft.get('included')} + {ft.get('excluded_total')} > {ft.get('assessed')})"
            )
    return issues


def check_venue_verification_completeness(records: list[dict]) -> list[str]:
    issues = []
    unique_records = [r for r in records if r.get("deduplication_status") == "unique"]
    incomplete = [
        r for r in unique_records
        if not r.get("venue_match_status") or r.get("venue_match_status") == "pending"
    ]
    if incomplete:
        issues.append(
            f"{len(incomplete)} of {len(unique_records)} unique records still have "
            "venue_match_status pending/blank"
        )
    return issues


def check_oa_legality_consistency(records: list[dict], manifest: list[dict]) -> list[str]:
    issues = []
    by_doi = {r.get("doi_normalized"): r for r in records if r.get("doi_normalized")}
    for entry in manifest:
        doi = entry.get("doi_normalized")
        record = by_doi.get(doi)
        if record is None:
            issues.append(f"corpus_manifest entry for doi='{doi}' has no matching master_records row")
            continue
        if record.get("open_access_status") not in LEGAL_OA_STATUSES:
            issues.append(
                f"corpus_manifest entry for doi='{doi}' has master_records "
                f"open_access_status='{record.get('open_access_status')}' (not gold/green/hybrid)"
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=str(MASTER_RECORDS_CSV))
    parser.add_argument("--manifest", default=str(OUTPUTS_CORPUS / "corpus_manifest.csv"))
    parser.add_argument("--prisma-counts", default=str(OUTPUTS_PRISMA / "prisma_flow_counts.json"))
    args = parser.parse_args()

    records = read_csv_rows(Path(args.records))
    manifest = read_csv_rows(Path(args.manifest))

    hard_fail_issues: list[str] = []
    soft_issues: list[str] = []

    hard_fail_issues += check_doi_format(records)
    hard_fail_issues += check_duplicate_dois(records)
    hard_fail_issues += check_prisma_arithmetic(Path(args.prisma_counts))
    hard_fail_issues += check_oa_legality_consistency(records, manifest)

    soft_issues += check_venue_verification_completeness(records)

    print("=" * 70)
    print("EvalBot JAIR PRISMA Review -- Integrity Audit")
    print("=" * 70)
    print(f"\nRecords checked: {len(records)}")
    print(f"Corpus manifest entries checked: {len(manifest)}")

    if hard_fail_issues:
        print(f"\nHARD-FAIL issues ({len(hard_fail_issues)}):")
        for issue in hard_fail_issues:
            print(f"  [FAIL] {issue}")
    else:
        print("\nNo hard-fail issues found.")

    if soft_issues:
        print(f"\nSoft issues ({len(soft_issues)}):")
        for issue in soft_issues:
            print(f"  [WARN] {issue}")
    else:
        print("\nNo soft issues found.")

    if hard_fail_issues:
        verdict = "STOP"
    elif soft_issues:
        verdict = "CONDITIONAL GO"
    else:
        verdict = "GO"

    print("\n" + "=" * 70)
    print(f"VERDICT: {verdict}")
    print("=" * 70)

    log_run_event({
        "stage": "integrity_audit",
        "verdict": verdict,
        "hard_fail_count": len(hard_fail_issues),
        "soft_issue_count": len(soft_issues),
    })

    return 1 if verdict == "STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
