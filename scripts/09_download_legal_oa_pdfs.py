#!/usr/bin/env python3
"""Download legally open-access PDFs for records approved through full-text
eligibility preparation (outputs/csv/fulltext_eligibility_worklist.csv).

This script must NEVER bypass a paywall. Legality rules enforced in code:
  - Only downloads from a record's `open_access_url` field.
  - Only proceeds if `open_access_status` is one of gold/green/hybrid.
  - No scraping, no third-party mirrors, no Sci-Hub/ResearchGate-style
    fallback of any kind. If a legal OA URL is not present, the record is
    simply skipped — it is never a candidate for download.

Every downloaded file is validated (PDF header %PDF-, non-trivial size),
checksummed (SHA-256), and named:
    year_firstauthor_shorttitle_DOI-safe.pdf
and logged to outputs/corpus/corpus_manifest.csv.

Phase gating: this script performs live network calls. It refuses to
download anything unless invoked with --live.

Usage:
    python scripts/09_download_legal_oa_pdfs.py
    python scripts/09_download_legal_oa_pdfs.py --live
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, log_run_event, log_error, read_csv_rows, write_csv_rows  # noqa: E402

LEGAL_OA_STATUSES = {"gold", "green", "hybrid"}

MANIFEST_FIELDS = [
    "record_id", "doi_normalized", "filename", "source_url", "license",
    "retrieval_timestamp", "checksum_sha256", "file_size_bytes",
]


def slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len] or "untitled"


def doi_safe(doi_normalized: str) -> str:
    return re.sub(r"[^\w.-]", "_", doi_normalized or "no-doi")


def target_filename(record: dict) -> str:
    year = record.get("publication_year") or "NA"
    first_author = ""
    authors = record.get("authors", "")
    if authors:
        first_author = slugify(authors.split(";")[0].split(",")[0])
    title_slug = slugify(record.get("title", "untitled"))
    doi_part = doi_safe(record.get("doi_normalized", ""))
    return f"{year}_{first_author}_{title_slug}_{doi_part}.pdf"


def candidates(worklist: list[dict]) -> list[dict]:
    """Only records with a confirmed legal OA status AND a URL are eligible.
    This is the sole gate that determines what download_one() may ever touch.
    """
    out = []
    for r in worklist:
        if r.get("open_access_status") in LEGAL_OA_STATUSES and r.get("open_access_url"):
            out.append(r)
    return out


def validate_pdf_bytes(content: bytes, min_size_bytes: int = 1024) -> bool:
    return content.startswith(b"%PDF-") and len(content) >= min_size_bytes


def download_one(record: dict, out_dir: Path) -> dict | None:
    import requests
    from datetime import datetime, timezone
    import time

    url = record["open_access_url"]
    headers = {
        "User-Agent": "EvalBot-PRISMA/1.0 (academic research; mailto:sudhanm@srmist.edu.in)",
        "Accept": "application/pdf,*/*",
    }
    try:
        resp = requests.get(url, timeout=90, headers=headers, allow_redirects=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as exc:
        log_error({"stage": "download_legal_oa_pdf", "record_id": record.get("record_id"), "url": url, "error": str(exc)})
        return None

    if not validate_pdf_bytes(content):
        # If URL returned HTML, try appending /pdf or checking Content-Type
        ct = resp.headers.get("Content-Type", "")
        log_error({
            "stage": "download_legal_oa_pdf",
            "record_id": record.get("record_id"),
            "url": url,
            "error": f"Not a PDF (Content-Type: {ct}, starts with: {content[:20]})",
        })
        return None

    filename = target_filename(record)
    out_path = out_dir / filename
    out_path.write_bytes(content)

    checksum = hashlib.sha256(content).hexdigest()
    return {
        "record_id": record.get("record_id"),
        "doi_normalized": record.get("doi_normalized"),
        "filename": filename,
        "source_url": url,
        "license": record.get("license", "NR"),
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
        "checksum_sha256": checksum,
        "file_size_bytes": len(content),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", default=str(OUTPUTS_DIR / "csv" / "fulltext_eligibility_worklist.csv"))
    parser.add_argument("--corpus-dir", default=str(OUTPUTS_DIR / "corpus"))
    parser.add_argument("--live", action="store_true",
                         help="Execute real downloads of confirmed legal OA PDFs. Defaults to a dry run.")
    args = parser.parse_args()

    worklist = read_csv_rows(Path(args.worklist))
    if not worklist:
        print(f"No worklist found at {args.worklist}. Run 08_prepare_fulltext_worklist.py first.")
        return 0

    cands = candidates(worklist)
    print(f"{len(cands)} of {len(worklist)} worklist records have a legal OA URL "
          f"(status in {sorted(LEGAL_OA_STATUSES)}).")

    if not args.live:
        print("Phase 1 not yet approved — dry run only")
        for r in cands:
            print(f"[DRY RUN] {r['record_id']} -> {target_filename(r)}  (source: {r['open_access_url']})")
        return 0

    out_dir = Path(args.corpus_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "corpus_manifest.csv"
    manifest_rows = read_csv_rows(manifest_path)
    existing_dois = {r.get("doi_normalized") for r in manifest_rows}

    downloaded = 0
    failed = 0
    for i, r in enumerate(cands):
        if r.get("doi_normalized") in existing_dois:
            continue
        result = download_one(r, out_dir)
        if result:
            manifest_rows.append(result)
            downloaded += 1
            print(f"[{downloaded}/{len(cands)}] Downloaded {result['filename']}")
        else:
            failed += 1
        # Rate limit: 1 second between requests
        if i < len(cands) - 1:
            import time
            time.sleep(1)

    write_csv_rows(manifest_path, manifest_rows, MANIFEST_FIELDS)
    log_run_event({
        "stage": "download_legal_oa_pdfs",
        "candidates": len(cands),
        "downloaded_this_run": downloaded,
        "manifest_total": len(manifest_rows),
    })
    print(f"\nDownloaded {downloaded} new PDFs ({failed} failed). Manifest now has {len(manifest_rows)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
