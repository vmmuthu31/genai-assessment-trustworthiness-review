#!/usr/bin/env python3
"""Retry PDF downloads for missing records using curl with aggressive timeouts.
Focuses on publishers known to serve PDFs directly."""
import csv
import hashlib
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_env, PROJECT_ROOT

load_env()

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CORPUS = PROJECT_ROOT / "outputs" / "corpus"
WORKLIST = PROJECT_ROOT / "outputs" / "csv" / "fulltext_eligibility_worklist.csv"
MANIFEST = CORPUS / "corpus_manifest.csv"
TIMEOUT = 10


def curl_pdf(url: str) -> Optional[bytes]:
    tmp = tempfile.mktemp(suffix=".pdf")
    try:
        r = subprocess.run(
            [
                "curl", "-sL", "-o", tmp, "--max-time", str(TIMEOUT),
                "-H", f"User-Agent: {UA}",
                "-H", "Accept: application/pdf,*/*",
                url,
            ],
            capture_output=True,
            timeout=TIMEOUT + 5,
        )
        p = Path(tmp)
        if p.exists() and p.stat().st_size > 1024:
            with open(tmp, "rb") as f:
                head = f.read(5)
            if head == b"%PDF-":
                return p.read_bytes()
        if p.exists():
            p.unlink()
    except Exception:
        pass
    return None


def build_urls(r: dict) -> list[str]:
    doi = r["doi_normalized"]
    url = r["open_access_url"]
    host = urlparse(url).hostname or ""
    urls = []

    if any(x in host for x in ("springer", "biomedcentral", "nature")):
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    elif "doi.org" in host:
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
        urls.append(url)
    elif "techrxiv" in host:
        urls.append(url.rstrip("/") + ".pdf")
    elif "mdpi" in host:
        urls.append(url)
        urls.append(url.split("?")[0])
    elif "frontiersin" in host:
        urls.append(url)
    elif "aclanthology" in host:
        urls.append(url)
    elif "github" in host or "figshare" in host or "osf.io" in host or "authorea" in host:
        urls.append(url)
    else:
        urls.append(url)
    return urls


def make_name(r: dict) -> str:
    y = r.get("publication_year", "NA")
    a = r.get("authors", "")
    first = re.sub(r"[^a-zA-Z0-9\s-]", "", a.split(";")[0].split(",")[0].lower()) if a else "unknown"
    first = re.sub(r"[\s_-]+", "-", first).strip("-")[:30]
    t = re.sub(r"[^a-zA-Z0-9\s-]", "", r.get("title", "untitled").lower())
    t = re.sub(r"[\s_-]+", "-", t).strip("-")[:30]
    d = re.sub(r"[^a-zA-Z0-9._-]", "_", r.get("doi_normalized", "x"))
    return f"{y}_{first}_{t}_{d}.pdf"


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)

    wl = list(csv.DictReader(open(WORKLIST)))
    m = list(csv.DictReader(open(MANIFEST)))
    existing = {r["doi_normalized"] for r in m if r.get("doi_normalized")}
    missing = [
        r for r in wl
        if r.get("open_access_status") in ("gold", "hybrid", "green")
        and r.get("open_access_url")
        and r["doi_normalized"] not in existing
    ]

    print(f"Missing {len(missing)} PDFs. Downloading with {TIMEOUT}s timeout...")
    downloaded = 0
    failed = 0

    for i, r in enumerate(missing):
        doi = r["doi_normalized"]
        urls = build_urls(r)
        content = None

        for url in urls[:2]:
            content = curl_pdf(url)
            if content:
                break
            time.sleep(0.3)

        if content:
            fname = make_name(r)
            (CORPUS / fname).write_bytes(content)
            m.append({
                "record_id": r["record_id"],
                "doi_normalized": doi,
                "filename": fname,
                "source_url": r["open_access_url"],
                "license": "NR",
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "checksum_sha256": hashlib.sha256(content).hexdigest(),
                "file_size_bytes": len(content),
            })
            downloaded += 1
        else:
            failed += 1

        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(missing)}] +{downloaded} downloaded, {failed} failed")
            flush_manifest(m)

        time.sleep(0.3)

    flush_manifest(m)
    print(f"\nDone: +{downloaded} new, {failed} failed. Total manifest: {len(m)} entries")


def flush_manifest(m: list):
    fields = [
        "record_id", "doi_normalized", "filename", "source_url",
        "license", "retrieval_timestamp", "checksum_sha256", "file_size_bytes",
    ]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(m)


if __name__ == "__main__":
    main()
