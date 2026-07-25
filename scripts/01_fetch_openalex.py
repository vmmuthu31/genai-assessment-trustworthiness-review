#!/usr/bin/env python3
"""Fetch OpenAlex `works` records for the OpenAlex queries defined in
config/search_queries.yaml (query_id prefix "OA-").

Phase 1 gating: this script performs live network calls. It refuses to make
any request unless invoked with --live. Without --live it prints the
constructed request(s) and exits.

Usage:
    python scripts/01_fetch_openalex.py
    python scripts/01_fetch_openalex.py --live
    python scripts/01_fetch_openalex.py --live --query-id OA-F1-01
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA_RAW_OPENALEX,
    load_env,
    load_yaml,
    log_run_event,
    log_error,
    normalize_doi,
    doi_url,
)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
PER_PAGE = 200

# OpenAlex .search filter values may not contain commas (comma separates
# filters). Concept terms contain none; this is asserted at build time.
_CONCEPT_KEYS = ("concept_a", "concept_b", "concept_c")


def _format_term(term: str) -> str:
    """Wrap multi-word phrases in double quotes for exact-phrase matching in
    an OpenAlex title_and_abstract.search boolean; leave single tokens bare.
    """
    term = term.strip()
    return f'"{term}"' if " " in term else term


def build_boolean(family: dict) -> str:
    """Build an OpenAlex boolean search string from a concept family:
    (a1 OR a2 ...) AND (b1 OR b2 ...) [AND (c1 OR c2 ...)].
    """
    blocks = []
    for key in _CONCEPT_KEYS:
        terms = family.get(key) or []
        if not terms:
            continue
        ored = " OR ".join(_format_term(t) for t in terms)
        blocks.append(f"({ored})")
    boolean = " AND ".join(blocks)
    if "," in boolean:
        raise ValueError(
            "Concept term contains a comma, which breaks OpenAlex filter syntax"
        )
    return boolean


def build_request_params(query: dict, cfg: dict, mailto: str | None) -> dict:
    """Construct the OpenAlex API request params for one query entry.

    Uses the `title_and_abstract.search` filter with an OR/AND boolean built
    from the query's concept family, rather than the top-level fulltext
    `search` param (which requires all words to co-occur in fulltext and
    returned zero results). Dates use YYYY-MM-DD, fully supported by OpenAlex.
    """
    filters = query.get("filters", {})
    # OpenAlex renamed the work type "journal-article" -> "article"; the old
    # value silently matches zero records, so map it here.
    raw_type = filters.get("type", "journal-article")
    oa_type = "article" if raw_type == "journal-article" else raw_type
    filter_parts = [f"type:{oa_type}"]
    start = filters.get("from_publication_date", cfg["date_range"]["start"])
    end = filters.get("to_publication_date", cfg["date_range"]["end"])
    filter_parts.append(f"from_publication_date:{start}")
    filter_parts.append(f"to_publication_date:{end}")

    family = cfg["concept_families"][query["concept_family"]]
    boolean = build_boolean(family)
    filter_parts.append(f"title_and_abstract.search:{boolean}")

    params = {
        "filter": ",".join(filter_parts),
        "per_page": PER_PAGE,
        "cursor": "*",
    }
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return params


def openalex_queries(cfg: dict) -> list[dict]:
    return [q for q in cfg["queries"] if str(q["query_id"]).startswith("OA-")]


def reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Rebuild plain-text abstract from OpenAlex's inverted index format:
    {word: [position, ...], ...} -> a single space-joined string ordered by
    position. Returns None if inverted_index is falsy or malformed.
    """
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return None
    ordered = [positions[i] for i in sorted(positions)]
    return " ".join(ordered)


def normalize_openalex_work(work: dict, query: dict) -> dict:
    """Map one OpenAlex `works` API item to a master_records_csv-shaped dict
    (subset of fields; downstream dedup/venue scripts fill the rest).
    """
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

    return {
        "source_database": "OpenAlex",
        "source_query_id": query["query_id"],
        "source_query_text": query["query_text"].strip(),
        "openalex_id": work.get("id"),
        "title": work.get("title") or work.get("display_name") or "",
        "authors": authors,
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "journal_name": source.get("display_name", ""),
        "issn_print": (source.get("issn") or [None])[0],
        "publisher": source.get("host_organization_name"),
        "document_type": work.get("type", ""),
        "doi_raw": doi_raw,
        "doi_normalized": doi_norm,
        "doi_url": doi_url(doi_norm) if doi_norm else "",
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "open_access_status": oa.get("oa_status"),
        "open_access_url": oa.get("oa_url"),
        "landing_page_url": primary_location.get("landing_page_url"),
        "cited_by_count_openalex": work.get("cited_by_count"),
    }


def fetch_query(query: dict, cfg: dict, mailto: str | None) -> int:
    """Fetch all pages for one query, saving raw JSON per page. Returns the
    total result count. Only called when --live is set.
    """
    import time

    import requests
    from tenacity import retry, stop_after_attempt, wait_exponential

    out_dir = DATA_RAW_OPENALEX
    out_dir.mkdir(parents=True, exist_ok=True)

    params = build_request_params(query, cfg, mailto)
    page = 0
    total = 0

    @retry(stop=stop_after_attempt(8), wait=wait_exponential(multiplier=2, min=5, max=120))
    def _get(p):
        resp = requests.get(OPENALEX_WORKS_URL, params=p, timeout=60)
        resp.raise_for_status()
        return resp.json()

    cursor = "*"
    while cursor:
        params["cursor"] = cursor
        try:
            data = _get(params)
        except Exception as exc:  # noqa: BLE001
            log_error({
                "stage": "fetch_openalex",
                "query_id": query["query_id"],
                "page": page,
                "error": str(exc),
            })
            break

        page += 1
        out_path = out_dir / f"{query['query_id']}_{page:03d}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        results = data.get("results", [])
        total += len(results)
        meta = data.get("meta", {})
        cursor = meta.get("next_cursor")
        if not results or not cursor:
            break
        time.sleep(1.0)  # be polite; avoid sustained-rate 429/403 throttling

    log_run_event({
        "stage": "fetch_openalex",
        "query_id": query["query_id"],
        "database": "OpenAlex",
        "search_params": query["concept_family"],
        "filter_params": params.get("filter", ""),
        "result_count": total,
        "pages_saved": page,
    })
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                         help="Execute real OpenAlex API calls. Defaults to a dry run.")
    parser.add_argument("--query-id", default=None,
                         help="Restrict to a single OA-* query_id (default: all OA-* queries).")
    args = parser.parse_args()

    load_env()
    cfg = load_yaml("search_queries.yaml")
    queries = openalex_queries(cfg)
    if args.query_id:
        queries = [q for q in queries if q["query_id"] == args.query_id]
        if not queries:
            print(f"No OpenAlex query with query_id={args.query_id}")
            return 1

    mailto = os.environ.get("OPENALEX_MAILTO") or None

    if not args.live:
        print("Phase 1 not yet approved — dry run only")
        for q in queries:
            params = build_request_params(q, cfg, mailto)
            print(f"[DRY RUN] {q['query_id']} -> GET {OPENALEX_WORKS_URL}")
            for k, v in params.items():
                print(f"    {k} = {v}")
        return 0

    if not mailto:
        print("WARNING: OPENALEX_MAILTO not set in .env — requests will not use "
              "the polite pool and may be rate-limited more aggressively.")

    grand_total = 0
    for q in queries:
        print(f"Fetching {q['query_id']} ...")
        count = fetch_query(q, cfg, mailto)
        print(f"  -> {count} results")
        grand_total += count

    print(f"\nDone. Total records fetched across {len(queries)} queries: {grand_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
