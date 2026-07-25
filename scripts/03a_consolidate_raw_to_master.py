#!/usr/bin/env python3
"""Consolidate raw OpenAlex/Crossref JSON pages (already saved to
data/raw/openalex/ and data/raw/crossref/ by scripts/01 and scripts/02) into
outputs/csv/master_records.csv.

Phase 1 scope only: this performs NO deduplication, NO venue/Q1-Q2 filtering,
and NO AI screening. Duplicate records across queries/sources are preserved
as separate rows, exactly as retrieved. Deduplication is scripts/04's job
(Phase 2) and must not be run until explicitly approved.

Local-file-only: reads JSON already on disk, makes no network calls.

Usage:
    python scripts/03a_consolidate_raw_to_master.py           # dry run summary
    python scripts/03a_consolidate_raw_to_master.py --write   # writes master_records.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA_RAW_OPENALEX,
    DATA_RAW_CROSSREF,
    MASTER_RECORDS_CSV,
    empty_master_record,
    master_records_fieldnames,
    normalize_doi,
    doi_url,
    next_record_id,
    read_csv_rows,
    write_csv_rows,
    log_run_event,
    utc_now_iso,
)


import re

_JATS_TAG_RE = re.compile(r"<[^>]+>")


def strip_jats_abstract(raw: str | None) -> str:
    """Crossref abstracts are JATS-tagged XML fragments (e.g. <jats:p>...);
    strip tags for a plain-text field usable by relevance screening."""
    if not raw:
        return ""
    return _JATS_TAG_RE.sub(" ", raw).strip()


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return None
    positions = {}
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def openalex_work_to_row(work: dict, query_id: str, query_text: str, retrieval_date: str) -> dict:
    doi_raw = work.get("doi")
    doi_norm = normalize_doi(doi_raw)
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    oa = work.get("open_access") or {}
    authorships = work.get("authorships") or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    )
    return empty_master_record(
        source_database="OpenAlex",
        source_query_id=query_id,
        source_query_text=query_text,
        retrieval_date=retrieval_date,
        openalex_id=work.get("id") or "",
        title=work.get("title") or work.get("display_name") or "",
        authors=authors,
        publication_year=work.get("publication_year") or "",
        publication_date=work.get("publication_date") or "",
        journal_name=source.get("display_name", "") or "",
        issn_print=(source.get("issn") or [None])[0] or "",
        publisher=source.get("host_organization_name") or "",
        document_type=work.get("type", "") or "",
        doi_raw=doi_raw or "",
        doi_normalized=doi_norm or "",
        doi_url=doi_url(doi_norm) if doi_norm else "",
        abstract=reconstruct_abstract(work.get("abstract_inverted_index")) or "",
        open_access_status=oa.get("oa_status") or "",
        open_access_url=oa.get("oa_url") or "",
        landing_page_url=primary_location.get("landing_page_url") or "",
        cited_by_count_openalex=work.get("cited_by_count") or "",
        scopus_verified="False",
        venue_match_status="pending",
        venue_match_confidence="NR",
        deduplication_status="pending",
        title_abstract_ai_decision="pending",
        title_abstract_human_decision="pending",
        fulltext_ai_decision="pending",
        fulltext_human_decision="pending",
    )


def crossref_item_to_row(item: dict, query_id: str, query_text: str, retrieval_date: str) -> dict:
    doi_raw = item.get("DOI")
    doi_norm = normalize_doi(doi_raw)
    title_list = item.get("title") or []
    container = item.get("container-title") or []
    issn_list = item.get("ISSN") or []
    # Serialize as "Given Family" (comma-free) joined by "; ", matching the
    # OpenAlex display_name format. Avoids intra-author commas so the single
    # authors field stays robust for CSV/Excel and naive downstream consumers.
    authors = "; ".join(
        " ".join(part for part in (a.get("given", ""), a.get("family", "")) if part).strip()
        for a in (item.get("author") or [])
        if a.get("family")
    )
    issued = (item.get("issued") or {}).get("date-parts") or [[None]]
    pub_year = issued[0][0] if issued and issued[0] else ""
    link = (item.get("link") or [{}])[0]
    license_urls = "; ".join(
        l.get("URL", "") for l in (item.get("license") or []) if l.get("URL")
    )
    return empty_master_record(
        source_database="Crossref",
        source_query_id=query_id,
        source_query_text=query_text,
        retrieval_date=retrieval_date,
        crossref_id=doi_norm or "",
        title=title_list[0] if title_list else "",
        authors=authors,
        publication_year=pub_year or "",
        journal_name=container[0] if container else "",
        issn_print=issn_list[0] if issn_list else "",
        publisher=item.get("publisher") or "",
        document_type=item.get("type", "") or "",
        doi_raw=doi_raw or "",
        doi_normalized=doi_norm or "",
        doi_url=doi_url(doi_norm) if doi_norm else "",
        abstract=strip_jats_abstract(item.get("abstract")),
        landing_page_url=item.get("URL") or "",
        open_access_url=link.get("URL") or "",
        crossref_license=license_urls,
        scopus_verified="False",
        venue_match_status="pending",
        venue_match_confidence="NR",
        deduplication_status="pending",
        title_abstract_ai_decision="pending",
        title_abstract_human_decision="pending",
        fulltext_ai_decision="pending",
        fulltext_human_decision="pending",
    )


def load_openalex_rows(retrieval_date: str) -> tuple[list[dict], Counter]:
    rows, per_query = [], Counter()
    if not DATA_RAW_OPENALEX.exists():
        return rows, per_query
    for path in sorted(DATA_RAW_OPENALEX.glob("*.json")):
        query_id = path.stem.rsplit("_", 1)[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        for work in data.get("results", []):
            rows.append(openalex_work_to_row(work, query_id, "", retrieval_date))
            per_query[query_id] += 1
    return rows, per_query


def load_crossref_rows(retrieval_date: str) -> tuple[list[dict], Counter]:
    rows, per_query = [], Counter()
    if not DATA_RAW_CROSSREF.exists():
        return rows, per_query
    for path in sorted(DATA_RAW_CROSSREF.glob("*.json")):
        query_id = path.stem.rsplit("_", 1)[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("message", {}).get("items", []):
            rows.append(crossref_item_to_row(item, query_id, "", retrieval_date))
            per_query[query_id] += 1
    return rows, per_query


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                         help="Write outputs/csv/master_records.csv. Without this flag, only a summary is printed.")
    args = parser.parse_args()

    retrieval_date = utc_now_iso()[:10]
    fieldnames = master_records_fieldnames()

    oa_rows, oa_per_query = load_openalex_rows(retrieval_date)
    cr_rows, cr_per_query = load_crossref_rows(retrieval_date)

    existing_rows = read_csv_rows(MASTER_RECORDS_CSV)
    existing_ids = [r.get("record_id", "") for r in existing_rows]

    new_rows = oa_rows + cr_rows
    # next_record_id() rescans the full id list each call; calling it inside
    # the loop over new_rows (O(n) list rebuild + scan per row) is O(n^2) and
    # took minutes on ~25k rows. Seed a counter from the existing max once,
    # then increment locally — matches next_record_id's REC-NNNNNN format.
    next_n = int(next_record_id(existing_ids)[4:]) if existing_ids else 1
    for row in new_rows:
        row["record_id"] = f"REC-{next_n:06d}"
        next_n += 1

    print("Consolidation summary (raw JSON -> master_records.csv rows)")
    print("=" * 70)
    print(f"OpenAlex:  {len(oa_rows)} rows across {len(oa_per_query)} query id(s)")
    for qid, n in sorted(oa_per_query.items()):
        print(f"    {qid}: {n}")
    print(f"Crossref:  {len(cr_rows)} rows across {len(cr_per_query)} query id(s)")
    for qid, n in sorted(cr_per_query.items()):
        print(f"    {qid}: {n}")
    print(f"Total new rows: {len(new_rows)}")
    print("Note: duplicates across queries/sources are NOT removed at this stage "
          "(Phase 2 handles deduplication).")

    if args.write:
        all_rows = existing_rows + new_rows
        write_csv_rows(MASTER_RECORDS_CSV, all_rows, fieldnames)
        print(f"\nWrote {len(all_rows)} total rows to {MASTER_RECORDS_CSV}")
        log_run_event({
            "stage": "consolidate_raw_to_master",
            "openalex_rows": len(oa_rows),
            "crossref_rows": len(cr_rows),
            "total_new_rows": len(new_rows),
            "total_rows_after_write": len(all_rows),
        })
    else:
        print("\nDry run (no --write): master_records.csv was not modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
