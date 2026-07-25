#!/usr/bin/env python3
"""Import manual database exports (CSV / RIS / BibTeX) from
data/raw/manual_database_exports/ and normalize them into master_records_csv
schema rows, appended to outputs/csv/master_records.csv.

Local-file-only. Runs for real now — no network calls, no live gate.

Usage:
    python scripts/03_import_manual_exports.py
    python scripts/03_import_manual_exports.py --write
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DATA_RAW_MANUAL_EXPORTS,
    MASTER_RECORDS_CSV,
    empty_master_record,
    master_records_fieldnames,
    normalize_doi,
    doi_url,
    next_record_id,
    read_csv_rows,
    write_csv_rows,
    log_run_event,
    log_error,
    utc_now_iso,
)

RIS_TAG_RE = re.compile(r"^([A-Z][A-Z0-9])\s+-\s?(.*)$")

RIS_TAG_MAP = {
    "TI": "title",
    "T1": "title",
    "AU": "authors",
    "A1": "authors",
    "PY": "publication_year",
    "Y1": "publication_year",
    "JO": "journal_name",
    "JF": "journal_name",
    "T2": "journal_name",
    "SN": "issn_print",
    "DO": "doi_raw",
    "AB": "abstract",
    "N2": "abstract",
    "UR": "landing_page_url",
    "PB": "publisher",
    "TY": "document_type",
    "KW": "keywords",
}


def parse_ris_file(path: Path) -> list[dict]:
    """Simple tag-based RIS parser. Each record starts at a TY tag and ends
    at an ER tag. Repeated AU/KW tags are accumulated (semicolon-joined).
    Unknown tags are ignored.
    """
    records: list[dict] = []
    current: dict = {}
    authors: list[str] = []
    keywords: list[str] = []

    def flush():
        nonlocal current, authors, keywords
        if current:
            if authors:
                current["authors"] = "; ".join(authors)
            if keywords:
                current["keywords"] = "; ".join(keywords)
            records.append(current)
        current = {}
        authors = []
        keywords = []

    text = path.read_text(encoding="utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n\r")
        if not line.strip():
            continue
        m = RIS_TAG_RE.match(line)
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()
        if tag == "TY":
            flush()
            current = {"document_type": value}
            continue
        if tag == "ER":
            flush()
            continue
        field = RIS_TAG_MAP.get(tag)
        if field == "authors":
            authors.append(value)
        elif field == "keywords":
            keywords.append(value)
        elif field:
            current[field] = value
    flush()
    return records


BIBTEX_FIELD_MAP = {
    "title": "title",
    "author": "authors",
    "year": "publication_year",
    "journal": "journal_name",
    "doi": "doi_raw",
    "issn": "issn_print",
    "publisher": "publisher",
    "abstract": "abstract",
    "keywords": "keywords",
    "url": "landing_page_url",
}


def parse_bibtex_file(path: Path) -> list[dict]:
    """Minimal brace-balanced BibTeX entry splitter + field extractor.
    Handles the common single-level-brace case produced by reference
    manager exports; does not attempt full BibTeX grammar.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    records: list[dict] = []
    pos = 0
    while True:
        m = re.search(r"@(\w+)\s*\{", text[pos:])
        if not m:
            break
        start = pos + m.end() - 1
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        entry_type = m.group(1).lower()
        body = text[start + 1:end]
        pos = end + 1

        rec = {"document_type": "journal-article" if entry_type == "article" else entry_type}
        for field_match in re.finditer(r"(\w+)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", body):
            key = field_match.group(1).strip().lower()
            value = field_match.group(2).strip()
            mapped = BIBTEX_FIELD_MAP.get(key)
            if mapped:
                rec[mapped] = value
        records.append(rec)
    return records


CSV_HEADER_ALIAS = {
    "title": "title",
    "article title": "title",
    "authors": "authors",
    "author": "authors",
    "author full names": "authors",
    "year": "publication_year",
    "publication year": "publication_year",
    "pubyear": "publication_year",
    "journal": "journal_name",
    "journal_name": "journal_name",
    "source title": "journal_name",
    "publication title": "journal_name",
    "issn": "issn_print",
    "doi": "doi_raw",
    "digital object identifier": "doi_raw",
    "abstract": "abstract",
    "publisher": "publisher",
    "document_type": "document_type",
    "document type": "document_type",
    "type": "document_type",
    "keywords": "keywords",
    "url": "landing_page_url",
    "link": "landing_page_url",
}


def parse_csv_file(path: Path) -> list[dict]:
    """Pass-through mapping for CSV exports: columns whose lowercased,
    whitespace-stripped name matches a known alias are copied verbatim;
    unmatched columns are ignored.
    """
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for raw_row in reader:
            rec = {}
            for key, value in raw_row.items():
                if key is None or value is None:
                    continue
                mapped = CSV_HEADER_ALIAS.get(key.strip().lower())
                if mapped and str(value).strip():
                    rec[mapped] = str(value).strip()
            if rec:
                rows.append(rec)
    return rows


def infer_source_database(path: Path) -> str:
    stem = path.stem.lower()
    for token, name in (
        ("scopus", "Scopus"),
        ("wos", "Web of Science"),
        ("web_of_science", "Web of Science"),
        ("eric", "ERIC"),
        ("ieee", "IEEE Xplore"),
        ("acm", "ACM Digital Library"),
        ("pubmed", "PubMed"),
    ):
        if token in stem:
            return name
    return "manual_export"


def normalize_manual_record(raw: dict, source_file: Path, retrieval_date: str) -> dict:
    doi_norm = normalize_doi(raw.get("doi_raw"))
    row = empty_master_record(
        source_database=infer_source_database(source_file),
        source_query_id=f"MANUAL:{source_file.name}",
        source_query_text="",
        retrieval_date=retrieval_date,
        title=raw.get("title", ""),
        authors=raw.get("authors", ""),
        publication_year=raw.get("publication_year", ""),
        journal_name=raw.get("journal_name", ""),
        issn_print=raw.get("issn_print", ""),
        publisher=raw.get("publisher", ""),
        document_type=raw.get("document_type") or "journal-article",
        doi_raw=raw.get("doi_raw", ""),
        doi_normalized=doi_norm or "",
        doi_url=doi_url(doi_norm) if doi_norm else "",
        abstract=raw.get("abstract", ""),
        keywords=raw.get("keywords", ""),
        landing_page_url=raw.get("landing_page_url", ""),
        scopus_verified="False",
        venue_match_status="pending",
        venue_match_confidence="NR",
        deduplication_status="unique",
        title_abstract_ai_decision="pending",
        title_abstract_human_decision="pending",
        fulltext_ai_decision="pending",
        fulltext_human_decision="pending",
    )
    return row


def discover_export_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    exts = {".csv", ".ris", ".bib", ".bibtex"}
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in exts)


def parse_file(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv_file(path)
    if suffix == ".ris":
        return parse_ris_file(path)
    if suffix in (".bib", ".bibtex"):
        return parse_bibtex_file(path)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                         help="Append normalized rows to outputs/csv/master_records.csv. "
                              "Without this flag, only a summary is printed.")
    args = parser.parse_args()

    files = discover_export_files(DATA_RAW_MANUAL_EXPORTS)
    if not files:
        print(f"No manual export files found in {DATA_RAW_MANUAL_EXPORTS}. Nothing to do.")
        return 0

    fieldnames = master_records_fieldnames()
    existing_rows = read_csv_rows(MASTER_RECORDS_CSV)
    existing_ids = [r.get("record_id", "") for r in existing_rows]
    retrieval_date = utc_now_iso()[:10]

    new_rows = []
    for path in files:
        try:
            raw_records = parse_file(path)
        except Exception as exc:  # noqa: BLE001
            log_error({"stage": "import_manual_exports", "file": str(path), "error": str(exc)})
            print(f"  ERROR parsing {path.name}: {exc}")
            continue

        print(f"{path.name}: {len(raw_records)} record(s) parsed")
        for raw in raw_records:
            row = normalize_manual_record(raw, path, retrieval_date)
            row["record_id"] = next_record_id(existing_ids + [r["record_id"] for r in new_rows])
            new_rows.append(row)

    if not new_rows:
        print("No records were successfully parsed from any file.")
        return 0

    print(f"\nTotal new records normalized: {len(new_rows)}")

    if args.write:
        all_rows = existing_rows + new_rows
        write_csv_rows(MASTER_RECORDS_CSV, all_rows, fieldnames)
        print(f"Wrote {len(all_rows)} total rows to {MASTER_RECORDS_CSV}")
        log_run_event({
            "stage": "import_manual_exports",
            "files_processed": len(files),
            "new_records": len(new_rows),
        })
    else:
        print("Dry run (no --write): master_records.csv was not modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
