#!/usr/bin/env python3
"""Fetch Crossref `works` records for the Crossref queries defined in
config/search_queries.yaml (query_id prefix "CR-").

Phase 1 gating: live network calls, requires --live. Without --live this
prints the constructed request(s) and exits without contacting the network.

Usage:
    python scripts/02_fetch_crossref.py
    python scripts/02_fetch_crossref.py --live
    python scripts/02_fetch_crossref.py --live --query-id CR-F1-01
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA_RAW_CROSSREF,
    load_env,
    load_yaml,
    log_run_event,
    log_error,
    normalize_doi,
    doi_url,
)

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
ROWS_PER_PAGE = 100

# Crossref query.bibliographic is relevance-ranked free text, not boolean, so
# total-results is huge and its long tail is off-topic. We retrieve only the
# top-N most-relevant records per family (documented, reproducible) instead of
# paginating the entire tail (which produced ~5,900 noisy hits per family).
DEFAULT_MAX_RESULTS = 500

# Crossref's query.bibliographic is a relevance-ranked free-text search, not
# a boolean engine (no AND/OR/quoted-phrase semantics like OpenAlex or
# Scopus). A handwritten query_text placeholder describing the intended
# boolean (e.g. "Crossref bibliographic query built from F2 concept_a/b/c
# terms; see scripts/02_fetch_crossref.py") was previously sent to the API
# verbatim as the search string, matching on generic words like "terms" and
# "scripts" rather than the topic — this produced ~5,900 near-duplicate,
# largely irrelevant hits per family. Build a concise, representative
# free-text string from each concept family instead, mirroring the
# concept_a/b/c structure without relying on unsupported boolean syntax.
_CONCEPT_KEYS = ("concept_a", "concept_b", "concept_c")
_TERMS_PER_CONCEPT = 3


def build_bibliographic_query(family: dict) -> str:
    words: list[str] = []
    for key in _CONCEPT_KEYS:
        terms = (family.get(key) or [])[:_TERMS_PER_CONCEPT]
        words.extend(terms)
    return " ".join(words)


def build_request_params(query: dict, cfg: dict, mailto: str | None) -> dict:
    filters = query.get("filters", {})
    start = filters.get("from-pub-date", cfg["date_range"]["start"])
    end = filters.get("until-pub-date", cfg["date_range"]["end"])
    # Amendment PA-001: full conference papers are core-eligible alongside
    # journal articles, so both Crossref document types are retrieved.
    # Crossref ORs repeated filter keys and ANDs across distinct keys.
    doc_types = filters.get("type")
    if doc_types is None:
        doc_types = ["journal-article", "proceedings-article"]
    elif isinstance(doc_types, str):
        doc_types = [doc_types]

    family = cfg["concept_families"][query["concept_family"]]
    bib_query = build_bibliographic_query(family)

    filter_clauses = [f"from-pub-date:{start}", f"until-pub-date:{end}"]
    filter_clauses += [f"type:{t}" for t in doc_types]

    params = {
        "query.bibliographic": bib_query,
        "filter": ",".join(filter_clauses),
        "rows": ROWS_PER_PAGE,
        "offset": 0,
    }
    if mailto:
        params["mailto"] = mailto
    return params


def crossref_queries(cfg: dict) -> list[dict]:
    return [q for q in cfg["queries"] if str(q["query_id"]).startswith("CR-")]


def normalize_crossref_item(item: dict, query: dict) -> dict:
    """Map one Crossref `works` API item to a master_records_csv-shaped dict."""
    doi_raw = item.get("DOI")
    doi_norm = normalize_doi(doi_raw)
    title_list = item.get("title") or []
    container = item.get("container-title") or []
    issn_list = item.get("ISSN") or []
    authors = "; ".join(
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in (item.get("author") or [])
        if a.get("family")
    )
    issued = (item.get("issued") or {}).get("date-parts") or [[None]]
    pub_year = issued[0][0] if issued and issued[0] else None
    link = (item.get("link") or [{}])[0]

    return {
        "source_database": "Crossref",
        "source_query_id": query["query_id"],
        "source_query_text": query["query_text"].strip(),
        "crossref_id": doi_norm,
        "title": title_list[0] if title_list else "",
        "authors": authors,
        "publication_year": pub_year,
        "journal_name": container[0] if container else "",
        "issn_print": issn_list[0] if issn_list else None,
        "publisher": item.get("publisher"),
        "document_type": item.get("type", ""),
        "doi_raw": doi_raw,
        "doi_normalized": doi_norm,
        "doi_url": doi_url(doi_norm) if doi_norm else "",
        "landing_page_url": item.get("URL"),
        "open_access_url": link.get("URL"),
    }


def fetch_query(query: dict, cfg: dict, mailto: str | None,
                max_results: int = DEFAULT_MAX_RESULTS) -> int:
    import time

    import requests
    from tenacity import retry, stop_after_attempt, wait_exponential

    out_dir = DATA_RAW_CROSSREF
    out_dir.mkdir(parents=True, exist_ok=True)

    params = build_request_params(query, cfg, mailto)
    total = 0
    page = 0

    @retry(stop=stop_after_attempt(8), wait=wait_exponential(multiplier=2, min=5, max=120))
    def _get(p):
        resp = requests.get(CROSSREF_WORKS_URL, params=p, timeout=60)
        resp.raise_for_status()
        return resp.json()

    while True:
        try:
            data = _get(params)
        except Exception as exc:  # noqa: BLE001
            log_error({
                "stage": "fetch_crossref",
                "query_id": query["query_id"],
                "page": page,
                "error": str(exc),
            })
            break

        page += 1
        out_path = out_dir / f"{query['query_id']}_{page:03d}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        items = data.get("message", {}).get("items", [])
        total_results = data.get("message", {}).get("total-results", 0)
        total += len(items)

        params["offset"] += ROWS_PER_PAGE
        # Bound to the top-N most-relevant records (relevance-ranked search).
        if not items or params["offset"] >= total_results or total >= max_results:
            break
        time.sleep(0.5)  # polite pacing

    log_run_event({
        "stage": "fetch_crossref",
        "query_id": query["query_id"],
        "database": "Crossref",
        "concept_family": query.get("concept_family"),
        "resolved_query_bibliographic": params.get("query.bibliographic"),
        "resolved_filter": params.get("filter"),
        "max_results_cap": max_results,
        "result_count": total,
        "pages_saved": page,
    })
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                         help="Execute real Crossref API calls. Defaults to a dry run.")
    parser.add_argument("--query-id", default=None)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS,
                         help=f"Top-N relevance-ranked records per family (default {DEFAULT_MAX_RESULTS}).")
    args = parser.parse_args()

    load_env()
    cfg = load_yaml("search_queries.yaml")
    queries = crossref_queries(cfg)
    if args.query_id:
        queries = [q for q in queries if q["query_id"] == args.query_id]
        if not queries:
            print(f"No Crossref query with query_id={args.query_id}")
            return 1

    mailto = os.environ.get("CROSSREF_MAILTO") or None

    if not args.live:
        print("Phase 1 not yet approved — dry run only")
        for q in queries:
            params = build_request_params(q, cfg, mailto)
            print(f"[DRY RUN] {q['query_id']} -> GET {CROSSREF_WORKS_URL}")
            for k, v in params.items():
                print(f"    {k} = {v}")
        return 0

    if not mailto:
        sys.exit("ERROR: CROSSREF_MAILTO environment variable is required to use the polite pool.")

    grand_total = 0
    for q in queries:
        print(f"Fetching {q['query_id']} ...")
        count = fetch_query(q, cfg, mailto, max_results=args.max_results)
        print(f"  -> {count} results")
        grand_total += count

    print(f"\nDone. Total records fetched across {len(queries)} queries: {grand_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
