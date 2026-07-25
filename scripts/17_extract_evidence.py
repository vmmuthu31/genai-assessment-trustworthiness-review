#!/usr/bin/env python3
"""Evidence extraction from PDFs: rule-based first pass (v2).

Improved: searches only in specific sections, better metric extraction,
more specific patterns.

Usage:
    python scripts/17_extract_evidence.py
    python scripts/17_extract_evidence.py --max 10   # test on 10 PDFs
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf not installed. Run: pip install pypdf")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, evidence_extraction_fieldnames, log_run_event, read_csv_rows, write_csv_rows

CORPUS = OUTPUTS_DIR / "corpus"
MANIFEST = CORPUS / "corpus_manifest.csv"
WORKLIST = OUTPUTS_DIR / "csv" / "fulltext_eligibility_worklist.csv"
EXTRACTION_OUTPUT = OUTPUTS_DIR / "csv" / "evidence_extraction.csv"


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except Exception as e:
        print(f"  WARNING: Failed to extract text: {e}")
        return ""


def split_sections(text: str) -> dict[str, str]:
    """Split paper text into rough sections."""
    # Normalize: replace tabs with spaces, collapse whitespace
    text = re.sub(r'\t', ' ', text)
    text = re.sub(r' {2,}', ' ', text)
    
    sections = {"full": text, "abstract": "", "methods": "", "results": "", "conclusion": ""}
    
    # Find abstract - header may end with \n or :
    # Stop at Keywords (case-insensitive, usually on its own line)
    # NOTE: use re.DOTALL so . matches newlines
    m = re.search(r"(?i)\babstract\s*[\n:](.{200,3000}?)\s*\n\s*keywords\b", text, re.IGNORECASE | re.DOTALL)
    if m:
        sections["abstract"] = m.group(1).strip()[:3000]
    else:
        # Fallback: abstract followed by double newline
        m = re.search(r"(?i)\babstract\s*[\n:](.{200,3000}?)\s*\n\s*\n", text, re.IGNORECASE | re.DOTALL)
        if m:
            sections["abstract"] = m.group(1).strip()[:3000]
    
    # Find methods section
    m = re.search(r"(?i)(?:3|III|method|methodology|approach|experimental?\s+(?:design|setup|procedure))\s*[\n:](.{200,5000}?)(?:\n\s*\n|\b4\b|IV\b|results|evaluation|findings)", text, re.DOTALL)
    if m:
        sections["methods"] = m.group(1).strip()[:5000]
    
    # Find results section
    m = re.search(r"(?i)(?:results|findings|evaluation|experiments?|4|IV)\s*[\n:](.{200,5000}?)(?:\n\s*\n|discussion|conclusion|5\b|V\b|limitations)", text, re.DOTALL)
    if m:
        sections["results"] = m.group(1).strip()[:5000]
    
    # Find conclusion
    m = re.search(r"(?i)(?:conclusion|concluding|discussion|6|VI)\s*[\n:](.{200,3000}?)(?:\n\s*\n|references|acknowledgment|appendix|$)", text, re.DOTALL)
    if m:
        sections["conclusion"] = m.group(1).strip()[:3000]
    
    return sections


def extract_educational_level(sections: dict[str, str]) -> str:
    """Extract educational level from abstract + methods."""
    search_text = (sections.get("abstract", "") + " " + sections.get("methods", "")).lower()
    
    if re.search(r"\b(k[- ]?12|primary school|secondary school|elementary|high school|middle school|grade[s]?\s+\d)", search_text):
        return "K-12"
    if re.search(r"\b(university|college|undergraduate|graduate|postgraduate|higher education|higher-ed)", search_text):
        return "higher-ed"
    if re.search(r"\b(vocational|technical training|professional development)", search_text):
        return "vocational"
    return "NR"


def extract_subject_area(sections: dict[str, str]) -> str:
    """Extract subject area from abstract."""
    abstract = sections.get("abstract", "").lower()
    if not abstract:
        abstract = sections.get("full", "")[:2000].lower()
    
    subjects = []
    if re.search(r"\b(math|algebra|geometry|calculus|statistics|arithmetic)\b", abstract):
        subjects.append("math")
    if re.search(r"\b(science|physics|chemistry|biology|lab\s+work)\b", abstract):
        subjects.append("science")
    if re.search(r"\b(computer science|programming|coding|software|AI|machine learning)\b", abstract):
        subjects.append("CS/AI")
    if re.search(r"\b(English|writing|reading|language arts|literacy|composition)\b", abstract):
        subjects.append("language")
    if re.search(r"\b(education|assessment|grading|feedback|pedagog|teaching|learning)\b", abstract):
        subjects.append("education")
    
    return "; ".join(subjects) if subjects else "NR"


def extract_assessment_task(sections: dict[str, str]) -> str:
    """Extract assessment task type from abstract + methods."""
    search_text = (sections.get("abstract", "") + " " + sections.get("methods", "")).lower()
    
    tasks = []
    # Be more specific: look for actual task descriptions
    if re.search(r"\b(essay\s+(?:scoring|grading|assessment|evaluation)|short.answer\s+(?:question|response))\b", search_text):
        tasks.append("essay")
    if re.search(r"\b(exam|test|quiz|multiple.choice|MCQ|MCQA)\b", search_text):
        tasks.append("exam")
    if re.search(r"\b(diagram|figure|chart|graph|visual)\s+(?:understanding|interpretation|generation)\b", search_text):
        tasks.append("diagram")
    if re.search(r"\b(coding|programming|code\s+(?:generation|completion|review))\b", search_text):
        tasks.append("coding")
    if re.search(r"\b(oral|presentation|speaking|speech)\b", search_text):
        tasks.append("oral")
    
    return "; ".join(tasks) if tasks else "NR"


def extract_input_modalities(sections: dict[str, str]) -> str:
    """Extract input modalities from abstract + methods."""
    search_text = (sections.get("abstract", "") + " " + sections.get("methods", "")).lower()
    
    mods = []
    if re.search(r"\b(handwritten|handwritten|scanned|image|visual|photo|figure|diagram|chart)\b", search_text):
        mods.append("image")
    if re.search(r"\b(audio|speech|voice|spoken|listening)\b", search_text):
        mods.append("audio")
    if re.search(r"\b(video|multimedia|animation)\b", search_text):
        mods.append("video")
    
    # Text is usually present but don't over-report
    if mods:
        mods.insert(0, "text")
    elif re.search(r"\b(text|written|natural language|NLG|text generation)\b", search_text):
        mods.append("text")
    
    if re.search(r"\bmultimodal|multi.modal|visual.language|image.text\b", search_text):
        mods.append("multimodal")
    
    return "; ".join(mods) if mods else "NR"


def extract_generative_model(sections: dict[str, str]) -> str:
    """Extract model names from methods section."""
    search_text = (sections.get("methods", "") + " " + sections.get("abstract", "")).lower()
    
    models = []
    if re.search(r"\bgpt[- ]?[34]\b|\bchatgpt\b", search_text):
        models.append("GPT")
    if re.search(r"\bllama\b", search_text):
        models.append("LLaMA")
    if re.search(r"\bbert\b|\broberta\b", search_text):
        models.append("BERT")
    if re.search(r"\bt5\b|\bflan.t5\b", search_text):
        models.append("T5")
    if re.search(r"\bpalm\b", search_text):
        models.append("PaLM")
    if re.search(r"\bclaude\b", search_text):
        models.append("Claude")
    if re.search(r"\bgemini\b|\bbard\b", search_text):
        models.append("Gemini")
    if re.search(r"\b(deepseek|deep.seek)\b", search_text):
        models.append("DeepSeek")
    
    # Check for MLLM specifically
    if re.search(r"\b(mllm|multimodal llm|vision.language model|multimodal model)\b", search_text):
        models.append("MLLM")
    elif re.search(r"\blarge language model\b|\bllm\b", search_text) and not models:
        models.append("LLM")
    
    return "; ".join(models) if models else "NR"


def extract_metrics(sections: dict[str, str]) -> str:
    """Extract metric results from results section."""
    results_text = sections.get("results", "") + " " + sections.get("full", "")[:5000]
    
    # More precise metric patterns
    metric_patterns = [
        (r"(?:accuracy|acc)\s*[=:]\s*(\d+\.?\d*%?)", "accuracy"),
        (r"(?:F1[\s-]score|F1)\s*[=:]\s*(\d+\.?\d*)", "F1"),
        (r"(?:QWK|quadratic weighted kappa)\s*[=:]\s*(\d+\.?\d*)", "QWK"),
        (r"(?:precision)\s*[=:]\s*(\d+\.?\d*)", "precision"),
        (r"(?:recall)\s*[=:]\s*(\d+\.?\d*)", "recall"),
        (r"(?:BLEU[\s-]?score?)\s*[=:]\s*(\d+\.?\d*)", "BLEU"),
        (r"(?:ROUGE[\s-]?[LM12]?)\s*[=:]\s*(\d+\.?\d*)", "ROUGE"),
        (r"(?:AUC[\s-]?ROC?)\s*[=:]\s*(\d+\.?\d*)", "AUC"),
        (r"(?:kappa)\s*[=:]\s*(\d+\.?\d*)", "kappa"),
    ]
    
    results = []
    for pat, name in metric_patterns:
        matches = re.findall(pat, results_text, re.IGNORECASE)
        for m in matches[:3]:  # max 3 per metric
            results.append(f"{name}={m}")
    
    # Also look for "Table X shows..." patterns
    table_results = re.findall(
        r"(?:Table|Supplementary)\s+\d+[.:]\s*(?:.*?){0,50}(?:accuracy|F1|QWK|precision|recall)\s*[=:]\s*(\d+\.?\d*)",
        results_text, re.IGNORECASE
    )
    for v in table_results[:5]:
        if f"={v}" not in "; ".join(results):
            results.append(f"table_metric={v}")
    
    return "; ".join(results[:10]) if results else "NR"


def extract_dataset_info(sections: dict[str, str]) -> tuple[str, str]:
    """Extract dataset name and size from methods section."""
    methods = sections.get("methods", "")
    full = sections.get("full", "")[:8000]
    search_text = methods + " " + full
    
    name = "NR"
    size = "NR"
    
    # Dataset name - look for specific patterns
    name_patterns = [
        r"(?:dataset|corpus|benchmark)\s+(?:called|named|termed|referred to as)\s+[\"']?([A-Z][\w\s-]{2,40}?)[\"']?[\s.,)]",
        r"(?:the)\s+([A-Z][\w]+(?:\s+[\w]+){0,2}?)\s+(?:dataset|corpus|benchmark)",
        r"(?:we use|using|used|adopt|employ)\s+(?:the\s+)?([A-Z][\w]+(?:\s+[\w]+){0,2}?)\s+(?:dataset|corpus)",
        r"(?:from|in)\s+(?:the\s+)?([A-Z][\w]+(?:\s+[\w]+){0,2}?)\s+(?:dataset|corpus|benchmark)",
    ]
    for pat in name_patterns:
        m = re.search(pat, search_text)
        if m:
            candidate = m.group(1).strip()
            # Filter out common false positives
            if candidate.lower() not in ("the", "our", "this", "a", "an", "our proposed", "the proposed"):
                name = candidate[:60]
                break
    
    # Dataset size
    size_patterns = [
        r"(\d[\d,]*)\s+(?:samples?|instances?|questions?|items?|passages?|documents?|texts?|essays?|responses?|data\s*points?|observations?)",
        r"(?:dataset|corpus)\s+(?:of|with|containing|comprising)\s+(\d[\d,]*)",
        r"(?:total|overall|in\s+total)\s+(\d[\d,]*)\s+(?:samples?|instances?|questions?)",
    ]
    for pat in size_patterns:
        m = re.search(pat, search_text, re.IGNORECASE)
        if m:
            size = m.group(1).strip()
            break
    
    return name, size


def extract_limitations(sections: dict[str, str]) -> str:
    """Extract limitations from conclusion section."""
    conclusion = sections.get("conclusion", "")
    if not conclusion:
        conclusion = sections.get("full", "")[-3000:]
    
    patterns = [
        r"(?:limitations?|limitation of (?:this|the) (?:study|work|paper|research))[:\s]+(.{30,300})",
        r"(?:we acknowledge|one limitation|a limitation|the main limitation|future work)[:\s]+(.{30,300})",
        r"(?:however|although|despite)[:\s]+(.{30,200})",
    ]
    for pat in patterns:
        m = re.search(pat, conclusion, re.IGNORECASE)
        if m:
            text = m.group(0).strip()
            # Clean up
            text = re.sub(r'\s+', ' ', text)
            return text[:300]
    return "NR"


def extract_main_findings(sections: dict[str, str]) -> str:
    """Extract main findings from conclusion."""
    conclusion = sections.get("conclusion", "")
    if not conclusion:
        conclusion = sections.get("full", "")[-3000:]
    
    patterns = [
        r"(?:we (?:conclude|found|demonstrate|show|argue)|our (?:main|key) finding[s]?|in (?:summary|conclusion))[:\s]+(.{30,400})",
        r"(?:results?\s+(?:show|demonstrate|indicate|suggest|reveal|confirm))[:\s]+(.{30,300})",
    ]
    for pat in patterns:
        m = re.search(pat, conclusion, re.IGNORECASE)
        if m:
            text = m.group(0).strip()
            text = re.sub(r'\s+', ' ', text)
            return text[:400]
    return "NR"


def extract_code_data(sections: dict[str, str]) -> tuple[str, str]:
    """Check code/data availability."""
    full = sections.get("full", "").lower()
    code = "NR"
    data = "NR"
    
    if re.search(r"github\.com|gitlab\.com|huggingface\.co|code\s+available|source\s+code", full):
        code = "yes"
    elif re.search(r"code\s+(?:is\s+)?(?:not|un)?available|proprietary|closed.?source", full):
        code = "no"
    
    if re.search(r"data\s+(?:is\s+)?available|dataset.*available|publicly\s+available", full):
        data = "yes"
    elif re.search(r"data\s+(?:is\s+)?(?:not|un)?available|confidential|private|proprietary", full):
        data = "no"
    
    return code, data


def extract_from_text(text: str, record: dict) -> dict:
    """Extract structured data from paper text."""
    row = {f: "NR" for f in evidence_extraction_fieldnames()}
    row["record_id"] = record.get("record_id", "")
    row["doi_normalized"] = record.get("doi_normalized", "")
    row["citation_key"] = record.get("citation_key", "")
    
    if not text or len(text) < 200:
        row["notes"] = "PDF text extraction failed or too short"
        row["extraction_status"] = "needs_review"
        return row
    
    sections = split_sections(text)
    
    row["educational_level"] = extract_educational_level(sections)
    row["subject_area"] = extract_subject_area(sections)
    row["assessment_task"] = extract_assessment_task(sections)
    row["input_modalities"] = extract_input_modalities(sections)
    row["generative_model"] = extract_generative_model(sections)
    row["primary_metrics"] = extract_metrics(sections)
    
    ds_name, ds_size = extract_dataset_info(sections)
    row["dataset_name"] = ds_name
    row["dataset_size"] = ds_size
    
    row["author_reported_limitations"] = extract_limitations(sections)
    row["main_findings"] = extract_main_findings(sections)
    
    code, data = extract_code_data(sections)
    row["code_available"] = code
    row["data_available"] = data
    
    row["evidence_page_section"] = "extracted from abstract/methods/results/conclusion sections"
    row["extraction_status"] = "ai_draft"
    row["human_verified"] = "false"
    
    return row


def _citation_key(record: dict) -> str:
    authors = record.get("authors", "")
    year = record.get("publication_year", "")
    if not authors or not year:
        return ""
    first = authors.split(";")[0].strip()
    parts = first.split()
    surname = parts[-1] if parts else ""
    return f"{surname}{year}" if surname else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=0, help="Max PDFs to process (0=all).")
    parser.add_argument("--force", action="store_true", help="Re-extract all, even already-done.")
    args = parser.parse_args()
    
    manifest = read_csv_rows(MANIFEST)
    worklist = read_csv_rows(WORKLIST)
    worklist_by_doi = {r["doi_normalized"]: r for r in worklist}
    
    existing_extraction = {}
    if EXTRACTION_OUTPUT.exists():
        existing = read_csv_rows(EXTRACTION_OUTPUT)
        existing_extraction = {r["record_id"]: r for r in existing}
    
    tasks = []
    for entry in manifest:
        doi = entry.get("doi_normalized", "")
        record = worklist_by_doi.get(doi, {})
        if record:
            pdf_path = CORPUS / entry["filename"]
            if pdf_path.exists():
                record["citation_key"] = _citation_key(record)
                tasks.append((record, pdf_path))
    
    if args.max > 0:
        tasks = tasks[:args.max]
    
    print(f"Extracting from {len(tasks)} PDFs (v2 - section-aware)...")
    
    results = list(existing_extraction.values()) if existing_extraction else []
    extracted = 0
    skipped = 0
    
    for i, (record, pdf_path) in enumerate(tasks):
        rid = record.get("record_id", "")
        if not args.force and rid in existing_extraction and existing_extraction[rid].get("extraction_status") == "human_verified":
            skipped += 1
            continue
        
        print(f"  [{i+1}/{len(tasks)}] {rid}...", end=" ")
        
        text = extract_text_from_pdf(pdf_path)
        row = extract_from_text(text, record)
        
        results = [r for r in results if r.get("record_id") != rid]
        results.append(row)
        extracted += 1
        
        # Show what we got
        non_nr = sum(1 for k, v in row.items() if v != "NR" and k not in ("record_id","doi_normalized","citation_key","extraction_status","human_verified","evidence_page_section"))
        print(f"OK ({len(text)} chars, {non_nr} fields populated)")
    
    fieldnames = evidence_extraction_fieldnames()
    write_csv_rows(EXTRACTION_OUTPUT, results, fieldnames)
    
    print(f"\nDone: extracted={extracted}, skipped={skipped}, total={len(results)}")
    
    log_run_event({
        "stage": "extract_evidence_v2",
        "pdfs_processed": extracted,
        "skipped": skipped,
        "total_rows": len(results),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
