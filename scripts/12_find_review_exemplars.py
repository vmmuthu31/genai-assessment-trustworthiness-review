#!/usr/bin/env python3
"""Find genuine systematic/scoping review exemplars relevant to this review's
topic, by querying OpenAlex and Crossref for review-type works. Used to
calibrate synthesis structure and to cite closely related prior reviews in
the JAIR positioning materials.

Phase 1 gating: this script performs live network calls. It refuses to
query anything unless invoked with --live.

Writes outputs/csv/systematic_review_exemplars.csv with schema:
    doi, title, authors, journal, year, relevance_note, verified

`verified` is always "no" for AI-discovered rows — a human must confirm each
exemplar is genuinely on-topic before verified is flipped to "yes".

Usage:
    python scripts/12_find_review_exemplars.py
    python scripts/12_find_review_exemplars.py --live
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_CSV,
    normalize_doi,
    read_csv_rows,
    write_csv_rows,
    log_run_event,
)

EXEMPLAR_FIELDS = ["doi", "title", "authors", "journal", "year", "relevance_note", "verified"]

REVIEW_SEARCH_TERMS = [
    "systematic review automated essay scoring",
    "systematic review automated short answer scoring",
    "scoping review large language models educational assessment",
    "systematic review multimodal large language models",
    "survey generative AI grading feedback",
    "systematic review hallucination detection large language models",
]

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"


def build_openalex_params(term: str, mailto: str | None) -> dict:
    params = {
        "search": term,
        "filter": "type:journal-article",
        "per_page": 25,
    }
    if mailto:
        params["mailto"] = mailto
    return params


def build_crossref_params(term: str, mailto: str | None) -> dict:
    params = {
        "query.bibliographic": term,
        "filter": "type:journal-article",
        "rows": 25,
    }
    if mailto:
        params["mailto"] = mailto
    return params


def is_review_like(title: str) -> bool:
    lowered = (title or "").lower()
    return any(k in lowered for k in ("systematic review", "scoping review", "survey", "literature review"))


def normalize_openalex_hit(work: dict, term: str) -> dict | None:
    title = work.get("title") or work.get("display_name") or ""
    if not is_review_like(title):
        return None
    doi = normalize_doi(work.get("doi"))
    source = (work.get("primary_location") or {}).get("source") or {}
    authorships = work.get("authorships") or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "") for a in authorships if a.get("author")
    )
    return {
        "doi": doi or "",
        "title": title,
        "authors": authors,
        "journal": source.get("display_name", ""),
        "year": work.get("publication_year", ""),
        "relevance_note": f"Matched search term: {term}",
        "verified": "no",
    }


def normalize_crossref_hit(item: dict, term: str) -> dict | None:
    title_list = item.get("title") or []
    title = title_list[0] if title_list else ""
    if not is_review_like(title):
        return None
    doi = normalize_doi(item.get("DOI"))
    container = item.get("container-title") or []
    authors = "; ".join(
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in (item.get("author") or []) if a.get("family")
    )
    issued = (item.get("issued") or {}).get("date-parts") or [[None]]
    year = issued[0][0] if issued and issued[0] else ""
    return {
        "doi": doi or "",
        "title": title,
        "authors": authors,
        "journal": container[0] if container else "",
        "year": year,
        "relevance_note": f"Matched search term: {term}",
        "verified": "no",
    }


def fetch_live(mailto_openalex: str | None, mailto_crossref: str | None) -> list[dict]:
    import requests

    exemplars = []
    for term in REVIEW_SEARCH_TERMS:
        try:
            resp = requests.get(OPENALEX_WORKS_URL, params=build_openalex_params(term, mailto_openalex), timeout=30)
            resp.raise_for_status()
            for work in resp.json().get("results", []):
                row = normalize_openalex_hit(work, term)
                if row:
                    exemplars.append(row)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: OpenAlex query failed for '{term}': {exc}")

        try:
            resp = requests.get(CROSSREF_WORKS_URL, params=build_crossref_params(term, mailto_crossref), timeout=30)
            resp.raise_for_status()
            for item in resp.json().get("message", {}).get("items", []):
                row = normalize_crossref_hit(item, term)
                if row:
                    exemplars.append(row)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: Crossref query failed for '{term}': {exc}")
    return exemplars


def dedup_exemplars(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = r["doi"] or r["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                         help="Execute real OpenAlex/Crossref queries. Defaults to a dry run.")
    parser.add_argument("--output", default=str(OUTPUTS_CSV / "systematic_review_exemplars.csv"))
    args = parser.parse_args()

    if not args.live:
        print("Phase 1 not yet approved — dry run only")
        print(f"Would search {len(REVIEW_SEARCH_TERMS)} terms across OpenAlex and Crossref:")
        for term in REVIEW_SEARCH_TERMS:
            print(f"  - {term}")
        out_path = Path(args.output)
        if not out_path.exists():
            write_csv_rows(out_path, [], EXEMPLAR_FIELDS)
            print(f"Wrote empty schema-only file -> {out_path}")
        return 0

    mailto_openalex = os.environ.get("OPENALEX_MAILTO") or None
    mailto_crossref = os.environ.get("CROSSREF_MAILTO") or None

    raw_exemplars = fetch_live(mailto_openalex, mailto_crossref)
    exemplars = dedup_exemplars(raw_exemplars)

    existing = read_csv_rows(Path(args.output))
    existing_keys = {r.get("doi") or r.get("title", "").strip().lower() for r in existing}
    new_rows = [r for r in exemplars if (r["doi"] or r["title"].strip().lower()) not in existing_keys]

    all_rows = existing + new_rows
    write_csv_rows(Path(args.output), all_rows, EXEMPLAR_FIELDS)

    log_run_event({
        "stage": "find_review_exemplars",
        "terms_searched": len(REVIEW_SEARCH_TERMS),
        "new_exemplars": len(new_rows),
        "total_exemplars": len(all_rows),
    })

    print(f"Found {len(new_rows)} new review exemplar(s) (all verified=no pending human check).")
    print(f"Total exemplars on file: {len(all_rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
