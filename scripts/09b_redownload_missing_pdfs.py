#!/usr/bin/env python3
"""Re-download missing PDFs using Unpaywall for alternative PDF URLs.

Queries Unpaywall for each missing record to find the best_oa_location
url_for_pdf (which may differ from the original open_access_url). Falls
back to the original URL if Unpaywall has no better link.

Usage:
    python scripts/09b_redownload_missing_pdfs.py --live
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, log_run_event, log_error, read_csv_rows, write_csv_rows

MANIFEST_FIELDS = [
    "record_id", "doi_normalized", "filename", "source_url", "license",
    "retrieval_timestamp", "checksum_sha256", "file_size_bytes",
]

# Known working PDF domains (serve PDFs directly without bot protection)
WORKING_DOMAINS = {
    "aclanthology.org", "arxiv.org", "frontiersin.org", "www.nature.com",
    "link.springer.com", "bmcmededuc.biomedcentral.com",
    "languagetestingasia.springeropen.com", "mededu.jmir.org",
    "openaccess.thecvf.com", "www.techrxiv.org",
}


def slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len] or "untitled"


def doi_safe(doi_normalized: str) -> str:
    return re.sub(r"[^\w.-]", "_", doi_normalized or "no-doi")


def target_filename(record: dict) -> str:
    year = record.get("publication_year") or "NA"
    authors = record.get("authors", "")
    first_author = ""
    if authors:
        first_author = slugify(authors.split(";")[0].split(",")[0])
    title_slug = slugify(record.get("title", "untitled"))
    doi_part = doi_safe(record.get("doi_normalized", ""))
    return f"{year}_{first_author}_{title_slug}_{doi_part}.pdf"


def validate_pdf_bytes(content: bytes, min_size_bytes: int = 1024) -> bool:
    return content.startswith(b"%PDF-") and len(content) >= min_size_bytes


def get_unpaywall_urls(doi: str) -> list[str]:
    """Query Unpaywall for PDF URLs, ordered by preference."""
    import requests
    urls = []
    try:
        resp = requests.get(
            f"https://api.unpaywall.org/v2/{doi}?email=sudhanm@srmist.edu.in",
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Best location first
            best = data.get("best_oa_location") or {}
            for key in ("url_for_pdf", "url"):
                u = best.get(key)
                if u:
                    urls.append(u)
            # Other locations
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf") and loc["url_for_pdf"] not in urls:
                    urls.append(loc["url_for_pdf"])
                elif loc.get("url") and loc["url"] not in urls:
                    urls.append(loc["url"])
    except Exception:
        pass
    return urls


def download_pdf(url: str, record: dict, out_dir: Path) -> dict | None:
    import requests as req
    from datetime import datetime, timezone

    headers = {
        "User-Agent": "EvalBot-PRISMA/1.0 (academic research; mailto:sudhanm@srmist.edu.in)",
        "Accept": "application/pdf,*/*",
    }
    try:
        resp = req.get(url, timeout=90, headers=headers, allow_redirects=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as exc:
        return None

    if not validate_pdf_bytes(content):
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
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    wl = list(csv.DictReader(open(OUTPUTS_DIR / "csv" / "fulltext_eligibility_worklist.csv")))
    manifest = list(csv.DictReader(open(OUTPUTS_DIR / "corpus" / "corpus_manifest.csv")))
    existing = {r["doi_normalized"] for r in manifest}

    cands = [r for r in wl
             if r.get("open_access_status") in ("gold", "hybrid", "green")
             and r.get("open_access_url")
             and r["doi_normalized"] not in existing]

    print(f"Already downloaded: {len(existing)}")
    print(f"Missing candidates: {len(cands)}")

    if not args.live:
        print("Dry run only. Use --live to download.")
        return 0

    out_dir = OUTPUTS_DIR / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    failed = 0
    no_pdf_url = 0

    for i, r in enumerate(cands):
        doi = r["doi_normalized"]
        # Try Unpaywall URLs first, then original
        urls_to_try = get_unpaywall_urls(doi)
        original = r.get("open_access_url", "")
        if original and original not in urls_to_try:
            urls_to_try.append(original)

        result = None
        for url in urls_to_try:
            result = download_pdf(url, r, out_dir)
            if result:
                break
            time.sleep(0.5)

        if result:
            manifest.append(result)
            downloaded += 1
            print(f"[{i+1}/{len(cands)}] OK {r['record_id']} ({doi[:30]})")
        else:
            failed += 1
            print(f"[{i+1}/{len(cands)}] FAIL {r['record_id']} ({doi[:30]})")

        # Rate limit
        time.sleep(1)

    # Write manifest
    manifest_path = out_dir / "corpus_manifest.csv"
    write_csv_rows(manifest_path, manifest, MANIFEST_FIELDS)
    print(f"\nDone: {downloaded} downloaded, {failed} failed, manifest now {len(manifest)} entries")
    log_run_event({
        "stage": "redownload_missing_pdfs",
        "candidates": len(cands),
        "downloaded": downloaded,
        "failed": failed,
        "manifest_total": len(manifest),
    })
    return 0


if __name__ == "__main__":
    import csv
    raise SystemExit(main())
