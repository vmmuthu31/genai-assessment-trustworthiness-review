#!/usr/bin/env python3
"""Compute PRISMA 2020 flow counts from outputs/csv/master_records.csv and
outputs/csv/prisma_log.csv, and write:
  - outputs/prisma/prisma_flow_counts.json
  - outputs/prisma/prisma_flow_diagram.md

Local-file-only. Handles missing/empty input gracefully (zero counts).

Usage:
    python scripts/10_generate_prisma_counts.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_DIR,
    OUTPUTS_PRISMA,
    MASTER_RECORDS_CSV,
    PRISMA_LOG_CSV,
    read_csv_rows,
    log_run_event,
    utc_now_iso,
    load_yaml,
)


def count_by_reason(rows: list[dict], decision_field: str, reason_field: str, decision_value: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        if r.get(decision_field) == decision_value:
            reason = r.get(reason_field) or "unspecified"
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def compute_counts(records: list[dict], prisma_log: list[dict]) -> dict:
    identified_openalex = sum(1 for r in records if r.get("source_database") == "OpenAlex")
    identified_crossref = sum(1 for r in records if r.get("source_database") == "Crossref")
    identified_manual = sum(
        1 for r in records
        if r.get("source_database") not in ("OpenAlex", "Crossref")
    )
    total_identified = len(records)

    duplicates_removed = sum(1 for r in records if r.get("deduplication_status") == "duplicate")
    needs_manual_review = sum(1 for r in records if r.get("deduplication_status") == "needs_manual_review")
    screened = sum(1 for r in records if r.get("deduplication_status") == "unique")

    ta_excluded = count_by_reason(records, "title_abstract_human_decision", "title_abstract_ai_reason", "exclude")
    ta_included = sum(1 for r in records if r.get("title_abstract_human_decision") == "include")

    fulltext_assessed = sum(
        1 for r in records if r.get("title_abstract_human_decision") == "include"
    )
    fulltext_excluded = count_by_reason(records, "fulltext_human_decision", "fulltext_ai_reason", "exclude")
    fulltext_included = sum(1 for r in records if r.get("fulltext_human_decision") == "include")

    final_included = sum(1 for r in records if str(r.get("final_included")).lower() == "true")

    return {
        "generated_at": utc_now_iso(),
        "identification": {
            "records_from_openalex": identified_openalex,
            "records_from_crossref": identified_crossref,
            "records_from_other_manual_sources": identified_manual,
            "total_identified": total_identified,
        },
        "deduplication": {
            "duplicates_removed": duplicates_removed,
            "flagged_needs_manual_review": needs_manual_review,
            "records_screened_title_abstract": screened,
        },
        "title_abstract_screening": {
            "included": ta_included,
            "excluded_total": sum(ta_excluded.values()),
            "excluded_by_reason": ta_excluded,
        },
        "fulltext_screening": {
            "assessed": fulltext_assessed,
            "included": fulltext_included,
            "excluded_total": sum(fulltext_excluded.values()),
            "excluded_by_reason": fulltext_excluded,
        },
        "final_included_studies": final_included,
        "prisma_log_entries": len(prisma_log),
    }


def render_flow_diagram_md(counts: dict) -> str:
    ident = counts["identification"]
    dedup = counts["deduplication"]
    ta = counts["title_abstract_screening"]
    ft = counts["fulltext_screening"]

    lines = [
        "# PRISMA 2020 Flow Diagram (counts)",
        "",
        f"Generated: {counts['generated_at']}",
        "",
        "## Identification",
        f"- Records identified from OpenAlex: {ident['records_from_openalex']}",
        f"- Records identified from Crossref: {ident['records_from_crossref']}",
        f"- Records identified from other manual sources: {ident['records_from_other_manual_sources']}",
        f"- **Total records identified: {ident['total_identified']}**",
        "",
        "## Deduplication",
        f"- Duplicate records removed: {dedup['duplicates_removed']}",
        f"- Flagged needs_manual_review (not auto-merged): {dedup['flagged_needs_manual_review']}",
        f"- **Records screened (title/abstract): {dedup['records_screened_title_abstract']}**",
        "",
        "## Title/Abstract Screening",
        f"- Included: {ta['included']}",
        f"- Excluded (total): {ta['excluded_total']}",
    ]
    for reason, n in sorted(ta["excluded_by_reason"].items()):
        lines.append(f"  - {reason}: {n}")
    lines += [
        "",
        "## Full-Text Screening",
        f"- Assessed for eligibility: {ft['assessed']}",
        f"- Included: {ft['included']}",
        f"- Excluded (total): {ft['excluded_total']}",
    ]
    for reason, n in sorted(ft["excluded_by_reason"].items()):
        lines.append(f"  - {reason}: {n}")
    lines += [
        "",
        "## Final",
        f"- **Studies included in review: {counts['final_included_studies']}**",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=str(MASTER_RECORDS_CSV))
    parser.add_argument("--prisma-log", default=str(PRISMA_LOG_CSV))
    parser.add_argument("--json-output", default=str(OUTPUTS_PRISMA / "prisma_flow_counts.json"))
    parser.add_argument("--md-output", default=str(OUTPUTS_PRISMA / "prisma_flow_diagram.md"))
    args = parser.parse_args()

    records = read_csv_rows(Path(args.records))
    prisma_log = read_csv_rows(Path(args.prisma_log))

    if not records:
        print(f"No records found in {args.records}. Writing zero-count PRISMA outputs.")

    counts = compute_counts(records, prisma_log)

    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(counts, indent=2), encoding="utf-8")

    md_path = Path(args.md_output)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_flow_diagram_md(counts), encoding="utf-8")

    log_run_event({
        "stage": "generate_prisma_counts",
        "total_identified": counts["identification"]["total_identified"],
        "final_included_studies": counts["final_included_studies"],
    })

    print(json.dumps(counts, indent=2))
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
