#!/usr/bin/env python3
"""Fast batch evidence extraction — processes all matched PDFs."""
import csv
import hashlib
import re
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, evidence_extraction_fieldnames, log_run_event, read_csv_rows, write_csv_rows

CORPUS = OUTPUTS_DIR / "corpus"
MANIFEST = CORPUS / "corpus_manifest.csv"
WORKLIST = OUTPUTS_DIR / "csv" / "fulltext_eligibility_worklist.csv"
EXTRACTION_OUTPUT = OUTPUTS_DIR / "csv" / "evidence_extraction.csv"


def extract_text(pdf_path):
    try:
        reader = PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
        return "\n".join(pages)
    except:
        return ""


def split_sections(text):
    text = re.sub(r'\t', ' ', text)
    text = re.sub(r' {2,}', ' ', text)
    s = {"full": text, "abstract": "", "methods": "", "results": "", "conclusion": ""}

    m = re.search(r"(?i)\babstract\s*[\n:](.{200,3000}?)\s*\n\s*keywords\b", text, re.IGNORECASE | re.DOTALL)
    if m:
        s["abstract"] = m.group(1).strip()[:3000]
    else:
        m = re.search(r"(?i)\babstract\s*[\n:](.{200,3000}?)\s*\n\s*\n", text, re.IGNORECASE | re.DOTALL)
        if m:
            s["abstract"] = m.group(1).strip()[:3000]

    m = re.search(r"(?i)(?:method|methodology|approach|experimental?\s+(?:design|setup|procedure))\s*[\n:](.{200,5000}?)(?:\n\s*\n|\b4\b|IV\b|results|evaluation|findings)", text, re.DOTALL)
    if m:
        s["methods"] = m.group(1).strip()[:5000]

    m = re.search(r"(?i)(?:results?|findings?|evaluation|experiments?)\s*[\n:](.{200,5000}?)(?:\n\s*\n|discussion|conclusion|5\b|V\b|limitations)", text, re.DOTALL)
    if m:
        s["results"] = m.group(1).strip()[:5000]

    m = re.search(r"(?i)(?:conclusion|concluding|discussion)\s*[\n:](.{200,3000}?)(?:\n\s*\n|references|acknowledgment|appendix|$)", text, re.DOTALL)
    if m:
        s["conclusion"] = m.group(1).strip()[:3000]

    return s


def ext_level(s):
    t = (s.get("abstract","") + " " + s.get("methods","")).lower()
    if re.search(r"\b(k[- ]?12|primary school|secondary school|elementary|high school|middle school|grade[s]?\s+\d)", t):
        return "K-12"
    if re.search(r"\b(university|college|undergraduate|graduate|postgraduate|higher education)", t):
        return "higher-ed"
    if re.search(r"\b(vocational|technical training|professional development)", t):
        return "vocational"
    return "NR"


def ext_subject(s):
    a = (s.get("abstract","") + " " + s.get("full","")[:2000]).lower()
    subj = []
    if re.search(r"\b(math|algebra|geometry|calculus|statistics)\b", a): subj.append("math")
    if re.search(r"\b(science|physics|chemistry|biology)\b", a): subj.append("science")
    if re.search(r"\b(computer science|programming|coding|software|AI|machine learning)\b", a): subj.append("CS/AI")
    if re.search(r"\b(English|writing|reading|language arts|literacy)\b", a): subj.append("language")
    if re.search(r"\b(education|assessment|grading|feedback|pedagog|teaching)\b", a): subj.append("education")
    return "; ".join(subj) if subj else "NR"


def ext_task(s):
    t = (s.get("abstract","") + " " + s.get("methods","")).lower()
    tasks = []
    if re.search(r"\b(essay\s+(?:scoring|grading|assessment|evaluation)|short.answer)\b", t):
        tasks.append("essay")
    if re.search(r"\b(exam|test|quiz|multiple.choice|MCQ|MCQA)\b", t):
        tasks.append("exam")
    if re.search(r"\b(diagram|figure|chart|graph)\s+(?:understanding|interpretation|generation)\b", t):
        tasks.append("diagram")
    if re.search(r"\b(coding|programming|code\s+(?:generation|completion|review))\b", t):
        tasks.append("coding")
    if re.search(r"\b(oral|presentation|speaking|speech)\b", t):
        tasks.append("oral")
    return "; ".join(tasks) if tasks else "NR"


def ext_model(s):
    t = (s.get("methods","") + " " + s.get("abstract","")).lower()
    models = []
    if re.search(r"\bgpt[- ]?[34]\b|\bchatgpt\b", t): models.append("GPT")
    if re.search(r"\bllama\b", t): models.append("LLaMA")
    if re.search(r"\bbert\b|\broberta\b", t): models.append("BERT")
    if re.search(r"\bt5\b|\bflan.t5\b", t): models.append("T5")
    if re.search(r"\bclaude\b", t): models.append("Claude")
    if re.search(r"\bgemini\b|\bbard\b", t): models.append("Gemini")
    if re.search(r"\bdeepseek\b", t): models.append("DeepSeek")
    if re.search(r"\b(mllm|multimodal llm|vision.language model|multimodal model)\b", t):
        models.append("MLLM")
    elif re.search(r"\blarge language model\b|\bllm\b", t) and not models:
        models.append("LLM")
    return "; ".join(models) if models else "NR"


def ext_metrics(s):
    txt = s.get("results","") + " " + s.get("full","")[:5000]
    pats = [
        (r"(?:accuracy|acc)\s*[=:]\s*(\d+\.?\d*%?)", "accuracy"),
        (r"(?:F1[\s-]score|F1)\s*[=:]\s*(\d+\.?\d*)", "F1"),
        (r"(?:QWK|quadratic weighted kappa)\s*[=:]\s*(\d+\.?\d*)", "QWK"),
        (r"(?:precision)\s*[=:]\s*(\d+\.?\d*)", "precision"),
        (r"(?:recall)\s*[=:]\s*(\d+\.?\d*)", "recall"),
        (r"(?:BLEU)\s*[=:]\s*(\d+\.?\d*)", "BLEU"),
        (r"(?:ROUGE)\s*[=:]\s*(\d+\.?\d*)", "ROUGE"),
    ]
    res = []
    for pat, name in pats:
        for m in re.findall(pat, txt, re.IGNORECASE)[:3]:
            res.append(f"{name}={m}")
    return "; ".join(res[:10]) if res else "NR"


def ext_dataset(s):
    txt = s.get("methods","") + " " + s.get("full","")[:8000]
    name, size = "NR", "NR"
    for pat in [
        r"(?:dataset|corpus|benchmark)\s+(?:called|named|termed)\s+[\"']?([A-Z][\w\s-]{2,40}?)[\"']?[\s.,)]",
        r"(?:the)\s+([A-Z][\w]+(?:\s+[\w]+){0,2}?)\s+(?:dataset|corpus|benchmark)",
        r"(?:we use|using|used)\s+(?:the\s+)?([A-Z][\w]+(?:\s+[\w]+){0,2}?)\s+(?:dataset|corpus)",
    ]:
        m = re.search(pat, txt)
        if m and m.group(1).lower() not in ("the","our","this","a","an"):
            name = m.group(1).strip()[:60]
            break
    for pat in [
        r"(\d[\d,]*)\s+(?:samples?|instances?|questions?|items?|essays?|responses?|data\s*points?)",
        r"(?:dataset|corpus)\s+(?:of|with|containing)\s+(\d[\d,]*)",
    ]:
        m = re.search(pat, txt, re.IGNORECASE)
        if m:
            size = m.group(1).strip()
            break
    return name, size


def ext_limitations(s):
    c = s.get("conclusion", "")
    if not c:
        c = s.get("full","")[-3000:]
    for pat in [
        r"(?:limitations?|limitation of (?:this|the) (?:study|work|paper))[:\s]+(.{30,300})",
        r"(?:we acknowledge|one limitation|a limitation|the main limitation|future work)[:\s]+(.{30,300})",
    ]:
        m = re.search(pat, c, re.IGNORECASE)
        if m:
            return re.sub(r'\s+', ' ', m.group(0).strip())[:300]
    return "NR"


def ext_findings(s):
    c = s.get("conclusion", "")
    if not c:
        c = s.get("full","")[-3000:]
    for pat in [
        r"(?:we (?:conclude|found|demonstrate|show|argue)|our (?:main|key) finding[s]?)[:\s]+(.{30,400})",
        r"(?:results?\s+(?:show|demonstrate|indicate|suggest|reveal|confirm))[:\s]+(.{30,300})",
    ]:
        m = re.search(pat, c, re.IGNORECASE)
        if m:
            return re.sub(r'\s+', ' ', m.group(0).strip())[:400]
    return "NR"


def ext_code_data(s):
    t = s.get("full","").lower()
    code = "NR"
    data = "NR"
    if re.search(r"github\.com|gitlab\.com|huggingface\.co|code\s+available|source\s+code", t):
        code = "yes"
    elif re.search(r"code\s+(?:is\s+)?(?:not|un)?available|proprietary|closed.?source", t):
        code = "no"
    if re.search(r"data\s+(?:is\s+)?available|dataset.*available|publicly\s+available", t):
        data = "yes"
    elif re.search(r"data\s+(?:is\s+)?(?:not|un)?available|confidential|private", t):
        data = "no"
    return code, data


def citation_key(record):
    authors = record.get("authors", "")
    year = record.get("publication_year", "")
    if not authors or not year:
        return ""
    first = authors.split(";")[0].strip()
    parts = first.split()
    surname = parts[-1] if parts else ""
    return f"{surname}{year}" if surname else ""


def extract_record(text, record):
    row = {f: "NR" for f in evidence_extraction_fieldnames()}
    row["record_id"] = record.get("record_id", "")
    row["doi_normalized"] = record.get("doi_normalized", "")
    row["citation_key"] = citation_key(record)

    if not text or len(text) < 200:
        row["notes"] = "PDF text extraction failed"
        row["extraction_status"] = "needs_review"
        return row

    s = split_sections(text)
    row["educational_level"] = ext_level(s)
    row["subject_area"] = ext_subject(s)
    row["assessment_task"] = ext_task(s)
    row["generative_model"] = ext_model(s)
    row["primary_metrics"] = ext_metrics(s)
    name, size = ext_dataset(s)
    row["dataset_name"] = name
    row["dataset_size"] = size
    row["author_reported_limitations"] = ext_limitations(s)
    row["main_findings"] = ext_findings(s)
    code, data = ext_code_data(s)
    row["code_available"] = code
    row["data_available"] = data
    row["evidence_page_section"] = "extracted from abstract/methods/results/conclusion"
    row["extraction_status"] = "ai_draft"
    row["human_verified"] = "false"
    return row


def main():
    manifest = read_csv_rows(MANIFEST)
    worklist = read_csv_rows(WORKLIST)
    wb = {r["doi_normalized"]: r for r in worklist}

    matched = [e for e in manifest if e.get("doi_normalized")]
    print(f"Extracting from {len(matched)} matched PDFs...")

    results = []
    extracted = 0

    for i, entry in enumerate(matched):
        doi = entry["doi_normalized"]
        record = wb.get(doi, {})
        pdf_path = CORPUS / entry["filename"]
        if not pdf_path.exists():
            continue

        text = extract_text(pdf_path)
        row = extract_record(text, record)
        results.append(row)
        extracted += 1

        if (i+1) % 20 == 0:
            print(f"  [{i+1}/{len(matched)}] extracted so far...")

    # Add rows for records without PDFs
    all_dois = {r["doi_normalized"] for r in results}
    for r in worklist:
        if r["doi_normalized"] not in all_dois:
            row = {f: "NR" for f in evidence_extraction_fieldnames()}
            row["record_id"] = r.get("record_id", "")
            row["doi_normalized"] = r.get("doi_normalized", "")
            row["citation_key"] = citation_key(r)
            row["extraction_status"] = "pending"
            results.append(row)

    fieldnames = evidence_extraction_fieldnames()
    write_csv_rows(EXTRACTION_OUTPUT, results, fieldnames)

    from collections import Counter
    status = Counter(r["extraction_status"] for r in results)
    print(f"\nDone: {extracted} extracted")
    print(f"Status: {dict(status)}")
    print(f"Total rows: {len(results)}")

    log_run_event({"stage": "extract_evidence_batch", "extracted": extracted, "total": len(results)})


if __name__ == "__main__":
    raise SystemExit(main())
