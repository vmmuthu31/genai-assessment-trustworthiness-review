"""Re-extract the 7 previously-failed needs_review PDFs using pypdf + fitz fallback."""
import csv, re, sys
from pathlib import Path

try:
    from pypdf import PdfReader
    import fitz
except ImportError:
    sys.exit("Missing pypdf or pymupdf")

PROJECT = Path(__file__).parent.parent
CORPUS  = PROJECT / "outputs" / "corpus"
CSV_IN  = PROJECT / "outputs" / "csv" / "evidence_extraction.csv"

# ── import extractor from 17d ────────────────────────────────────────────────
sys.path.insert(0, str(PROJECT / "scripts"))
from importlib import util as ilu
spec = ilu.spec_from_file_location("ext17d", PROJECT/"scripts"/"17d_comprehensive_extract.py")
mod  = ilu.module_from_spec(spec)
spec.loader.exec_module(mod)

FAILED_RIDS = {
    "REC-005256","REC-005628","REC-005129",
    "REC-000013","REC-001406","REC-008413","REC-005482",
}

def extract_text(pdf_path: Path) -> str:
    """Try pypdf first, fall back to fitz."""
    text = ""
    try:
        reader = PdfReader(str(pdf_path), strict=False)
        for page in reader.pages:
            try: text += page.extract_text() or ""
            except: pass
        text = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
        if len(text.strip()) > 200:
            return text
    except Exception:
        pass
    # fitz fallback
    try:
        doc = fitz.open(str(pdf_path))
        text = "".join(p.get_text() for p in doc)
        doc.close()
        text = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
    except Exception as e:
        print(f"  fitz also failed: {e}")
    return text

# ── load CSV ─────────────────────────────────────────────────────────────────
rows = list(csv.DictReader(open(CSV_IN, newline="")))
fieldnames = list(rows[0].keys())

# ── build filename map from downloaded_papers.csv ────────────────────────────
dl_csv = PROJECT / "outputs" / "csv" / "downloaded_papers.csv"
fn_map = {}  # doi_normalized -> filename
for r in csv.DictReader(open(dl_csv)):
    fn_map[r["doi_normalized"]] = r["filename"]

updated = 0
for row in rows:
    if row["record_id"] not in FAILED_RIDS:
        continue
    fn = fn_map.get(row["doi_normalized"], "")
    if not fn:
        print(f"  No filename for {row['record_id']}")
        continue
    pdf_path = CORPUS / fn
    if not pdf_path.exists():
        print(f"  PDF missing: {fn}")
        continue

    print(f"Extracting {row['record_id']} ({fn[:50]})...", end=" ")
    text = extract_text(pdf_path)
    if len(text.strip()) < 100:
        print(f"EMPTY ({len(text)} chars) — keeping needs_review")
        continue

    print(f"{len(text)} chars")
    extracted = mod.extract_from_text(text, dict(row))
    row.update(extracted)
    row["extraction_status"] = "ai_draft"
    # no extraction_date column
    updated += 1

# ── write back ───────────────────────────────────────────────────────────────
with open(CSV_IN, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(rows)

print(f"\nDone. Updated {updated}/7 records → ai_draft")
