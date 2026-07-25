#!/usr/bin/env python3
"""Comprehensive evidence extraction from PDFs — v4 (all-field coverage).

Dramatically improves on the rule-based v2 by:
  - Dedicated extractors for ALL 40 evidence_extraction_csv fields
  - Multi-pass text search (full doc + section-specific)
  - Smarter metric extraction with actual numeric values
  - Proper answer_format, baselines, key_results, educational_context extraction
  - Better main_findings using multiple conclusion sentence patterns
  - Preserves human_verified rows (never overwrites them)

Usage:
    cd evalbot_jair_prisma_review
    python scripts/17d_comprehensive_extract.py            # all PDFs
    python scripts/17d_comprehensive_extract.py --max 20  # test on 20
    python scripts/17d_comprehensive_extract.py --force   # re-extract all
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

try:
    import fitz  # PyMuPDF fallback for PDFs pypdf can't parse cleanly
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, evidence_extraction_fieldnames, log_run_event, read_csv_rows, write_csv_rows

CORPUS     = OUTPUTS_DIR / "corpus"
MANIFEST   = CORPUS / "corpus_manifest.csv"
WORKLIST   = OUTPUTS_DIR / "csv" / "fulltext_eligibility_worklist.csv"
MASTER     = OUTPUTS_DIR / "csv" / "master_records.csv"
EXTRACTION = OUTPUTS_DIR / "csv" / "evidence_extraction.csv"

NR = "NR"

# ─────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────

def _extract_text_pypdf(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path), strict=False)
        pages = []
        for page in reader.pages:
            try:
                t = page.extract_text()
            except Exception:
                t = None
            if t:
                pages.append(t)
        return "\n\n".join(pages)
    except Exception as e:
        print(f"    WARN (pypdf): {e}")
        return ""


def _extract_text_fitz(pdf_path: Path) -> str:
    if not _HAS_FITZ:
        return ""
    try:
        doc = fitz.open(str(pdf_path))
        text = "\n\n".join(p.get_text() for p in doc)
        doc.close()
        return text
    except Exception as e:
        print(f"    WARN (fitz): {e}")
        return ""


def extract_text(pdf_path: Path) -> str:
    """Try pypdf first; fall back to PyMuPDF (fitz) if pypdf yields too little text.

    Some PDFs (malformed xref tables, non-stream objects, etc.) parse fine in one
    library and fail silently in the other, so we take whichever returns more text.
    """
    raw = _extract_text_pypdf(pdf_path)
    if len(raw.strip()) < 300:
        fitz_text = _extract_text_fitz(pdf_path)
        if len(fitz_text.strip()) > len(raw.strip()):
            raw = fitz_text
    # Strip control characters that break CSV (keep \n \r \t only)
    return "".join(c for c in raw if ord(c) >= 32 or c in "\n\r\t")


def split_sections(raw: str) -> dict[str, str]:
    """Segment paper text into named zones for targeted extraction."""
    text = re.sub(r"\t", " ", raw)
    text = re.sub(r" {2,}", " ", text)
    s = {"full": text, "abstract": "", "intro": "",
         "methods": "", "results": "", "conclusion": "", "limitations": ""}

    # --- Abstract ---
    m = re.search(
        r"(?i)\babstract\s*[\n:]\s*(.{150,4000}?)\s*\n\s*(?:keywords?|1[.\s]?\s*introduction)",
        text, re.DOTALL)
    if m:
        s["abstract"] = m.group(1).strip()[:4000]
    else:
        m = re.search(r"(?i)\babstract\s*[\n:]\s*(.{150,4000}?)\n\s*\n", text, re.DOTALL)
        if m:
            s["abstract"] = m.group(1).strip()[:4000]

    # --- Introduction ---
    m = re.search(
        r"(?i)\b(?:1\.?\s*)?introduction\s*[\n:]\s*(.{200,5000}?)\n\s*(?:2\.?\s*|related work|background|literature|method)",
        text, re.DOTALL)
    if m:
        s["intro"] = m.group(1).strip()[:5000]

    # --- Methods ---
    m = re.search(
        r"(?i)(?:2|3|II|III|method(?:ology|s)?|approach|experimental\s+(?:design|setup))\s*[\n:]\s*(.{300,8000}?)"
        r"(?:\n\s*(?:3|4|IV|results?|evaluation|findings|experiment))",
        text, re.DOTALL)
    if m:
        s["methods"] = m.group(1).strip()[:8000]

    # --- Results / Evaluation ---
    m = re.search(
        r"(?i)(?:results?|findings?|evaluation|experiments?\s+and\s+results?|4|IV)\s*[\n:]\s*(.{300,10000}?)"
        r"(?:\n\s*(?:discussion|conclusion|5|V\b|limitations?|future))",
        text, re.DOTALL)
    if m:
        s["results"] = m.group(1).strip()[:10000]

    # --- Conclusion / Discussion ---
    m = re.search(
        r"(?i)(?:conclusion|concluding\s+remarks?|discussion|summary)\s*[\n:]\s*(.{200,5000}?)"
        r"(?:\n\s*(?:references?|acknowledgement|appendix|$))",
        text, re.DOTALL)
    if m:
        s["conclusion"] = m.group(1).strip()[:5000]

    # --- Limitations (sometimes a sub-section) ---
    m = re.search(
        r"(?i)(?:limitations?(?:\s+and\s+future\s+work)?)\s*[\n:]\s*(.{100,3000}?)"
        r"(?:\n\s*(?:\d|future|conclusion|references?|$))",
        text, re.DOTALL)
    if m:
        s["limitations"] = m.group(1).strip()[:3000]

    return s


# ─────────────────────────────────────────────
# Field-specific extractors
# ─────────────────────────────────────────────

def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def _first_match(patterns: list[str], text: str, flags=re.IGNORECASE) -> str:
    for p in patterns:
        m = re.search(p, text, flags | re.DOTALL)
        if m:
            return _clean(m.group(1))[:400]
    return NR


def extr_educational_context(s: dict) -> str:
    """Free-text description of the educational setting."""
    src = s["abstract"] + " " + s["intro"]
    patterns = [
        r"(?:conducted?|carried out|deployed|implemented|evaluated?)\s+in\s+([^.]{10,120}(?:class(?:room)?|course|school|university|college|institution)[^.]{0,80})",
        r"(?:students?\s+(?:from|at|in)\s+([^.]{10,80}(?:university|college|school|course)[^.]{0,60}))",
        r"(?:in\s+a\s+([^.]{5,80}(?:classroom|educational|academic|school|university|college)[^.]{0,60})\s+(?:setting|environment|context))",
        r"([^.]{5,80}(?:K-12|higher education|undergraduate|postgraduate|vocational|primary|secondary|high school)[^.]{0,80})",
    ]
    result = _first_match(patterns, src)
    if result == NR:
        # Fallback: grab sentence that mentions students/learners
        m = re.search(r"([^.]*(?:students?|learners?|pupils?)[^.]{10,150}\.)", src, re.IGNORECASE)
        if m:
            return _clean(m.group(1))[:300]
    return result


def extr_educational_level(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    if re.search(r"\b(k[- ]?12|primary school|secondary school|elementary|high school|middle school|grade[s]?\s*\d)", src):
        return "K-12"
    if re.search(r"\b(university|college|undergraduate|graduate|postgraduate|higher.?ed|bachelor|master(?!'s exam)|phd|doctoral)", src):
        return "higher-ed"
    if re.search(r"\b(vocational|technical training|professional development|workforce)", src):
        return "vocational"
    if re.search(r"\b(mixed|multiple levels?|across grades?|various levels?)", src):
        return "mixed"
    return NR


def extr_subject_area(s: dict) -> str:
    src = (s["abstract"] + " " + s["intro"])
    subs = []
    checks = [
        (r"\b(math|algebra|geometry|calculus|statistics|arithmetic|numeracy)\b", "math"),
        (r"\b(physics|chemistry|biology|science|stem\b|laboratory|lab\s+work)\b", "science"),
        (r"\b(computer science|programming|coding|software|CS\b)\b", "CS/AI"),
        (r"\b(English|writing|reading|language arts|literacy|composition|essay writing|EFL|ESL|L2)\b", "language"),
        (r"\b(history|social studies|geography|civics)\b", "social sciences"),
        (r"\b(medicine|medical|clinical|nursing|health)\b", "medicine/health"),
        (r"\b(accounting|business|economics|finance|management)\b", "business"),
        (r"\b(education|pedagog|teaching|learning|assessment|grading)\b", "education"),
        (r"\b(music|art|creative)\b", "arts"),
        (r"\b(law|legal)\b", "law"),
    ]
    for pat, label in checks:
        if re.search(pat, src, re.IGNORECASE):
            subs.append(label)
    return "; ".join(subs) if subs else NR


def extr_assessment_task(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    tasks = []
    checks = [
        (r"\b(open.?ended\s+(?:question|answer|response)|short.?answer\s+(?:question|scoring|grading))", "short-answer"),
        (r"\b(essay\s+(?:scoring|grading|writing|assessment|evaluation)|essay\b)", "essay"),
        (r"\b(multiple.choice|mcq|mcqa|mc\s+question)", "MCQ"),
        (r"\b(programming\s+(?:assignment|exercise|problem)|code\s+(?:grading|evaluation|assessment)|coding\s+(?:task|exercise))", "coding"),
        (r"\b(oral\s+(?:exam|assessment|presentation)|speaking|speech\s+(?:evaluation|scoring))", "oral"),
        (r"\b(diagram|figure|sketch|drawing)\s+(?:interpretation|evaluation|grading)", "diagram"),
        (r"\b(handwritten|handwriting\s+(?:recognition|grading))", "handwritten"),
        (r"\b(exam|test|quiz)\b", "exam"),
        (r"\b(project|portfolio)\s+(?:grading|assessment|evaluation)", "project"),
        (r"\b(feedback\s+(?:generation|grading)|formative\s+(?:assessment|feedback))", "formative-feedback"),
        (r"\b(translation|interpreting)\b", "translation"),
        (r"\b(question\s+(?:generation|answering)|QA\b)", "QA"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in tasks:
            tasks.append(label)
    return "; ".join(tasks) if tasks else NR


def extr_answer_format(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    fmts = []
    checks = [
        (r"\b(short.?answer|brief\s+answer|one.?sentence|2-3\s+sentence)", "short-answer"),
        (r"\b(essay|long.?form|extended\s+(?:response|writing))", "essay"),
        (r"\b(multiple.choice|mcq|option\s+[abcd]\b)", "MCQ"),
        (r"\b(diagram|image|figure|sketch|graph|chart)\s+(?:answer|response|submission)", "diagram"),
        (r"\b(code|program|script)\s+(?:answer|response|submission)", "code"),
        (r"\b(mixed|various\s+(?:format|type)|combination)", "mixed"),
        (r"\b(handwritten\s+(?:answer|response|text))", "handwritten"),
        (r"\b(structured\s+(?:report|document)|lab\s+report)", "structured-report"),
        (r"\b(open.?ended)", "open-ended"),
        (r"\b(numeric|numerical\s+answer|number)", "numeric"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in fmts:
            fmts.append(label)
    return "; ".join(fmts) if fmts else NR


def extr_input_modalities(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    mods = []
    checks = [
        (r"\b(image|visual|photo|scan|figure|chart|diagram|table\s+image)\b", "image"),
        (r"\b(handwrit|scanned\s+(?:answer|document|sheet))", "image"),
        (r"\b(audio|speech|voice|spoken|listening|recording)\b", "audio"),
        (r"\b(video|screencast|lecture\s+video)\b", "video"),
        (r"\b(multimodal|multi.modal|vision.language|image.text|visual.text)\b", "multimodal"),
        (r"\b(ocr|optical\s+character)\b", "image"),
    ]
    has_text = bool(re.search(r"\b(text|written|natural\s+language|nlp|sentence|paragraph)\b", src))
    for pat, label in checks:
        if re.search(pat, src) and label not in mods:
            mods.append(label)
    if mods or has_text:
        if "text" not in mods:
            mods.insert(0, "text")
    return "; ".join(mods) if mods else NR


def extr_document_image_type(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    types = []
    checks = [
        (r"\b(exam\s+(?:paper|sheet)|answer\s+sheet|scantron)\b", "exam-sheet"),
        (r"\b(essay\s+(?:document|text|paper))\b", "essay-doc"),
        (r"\b(handwritten\s+(?:answer|note|text|document|response))\b", "handwritten-doc"),
        (r"\b(medical\s+(?:image|scan|report|record)|radiograph|x.ray|mri|ct\s+scan)\b", "medical-image"),
        (r"\b(diagram|figure|chart|graph|table|visual)\b", "figure/diagram"),
        (r"\b(pdf|document|form|report)\b", "pdf-doc"),
        (r"\b(screenshot|screen\s+capture)\b", "screenshot"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in types:
            types.append(label)
    return "; ".join(types) if types else NR


def extr_ocr_model(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    models = []
    checks = [
        (r"\btesseract\b", "Tesseract"),
        (r"\bocr\s*(?:api|model|engine|system|pipeline)?\b", "OCR"),
        (r"\bpaddleocr\b", "PaddleOCR"),
        (r"\bamazon\s+textract\b|\btextract\b", "AWS Textract"),
        (r"\bgoogle\s+(?:cloud\s+)?vision\b|\bcloud\s+vision\s+api\b", "Google Vision"),
        (r"\bdocument\s+ai\b", "Google Doc AI"),
        (r"\bvision\s+transformer\b|\bvit\b", "ViT"),
        (r"\bclip\b", "CLIP"),
        (r"\bllava\b|\bllave\b", "LLaVA"),
        (r"\bgpt.4v(?:ision)?\b|\bgpt.4o\b", "GPT-4V/4o"),
        (r"\bgemini\s+(?:pro\s+)?vision\b", "Gemini Vision"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in models:
            models.append(label)
    return "; ".join(models) if models else NR


def extr_generative_model(s: dict) -> str:
    src = s["methods"] + " " + s["abstract"] + " " + s["results"]
    models = []
    checks = [
        (r"\bgpt.?4o\b|\bgpt.4o\b", "GPT-4o"),
        (r"\bgpt.?4(?!o)\b|\bgpt\s*4\b", "GPT-4"),
        (r"\bgpt.?3\.?5\b|\bchatgpt\b", "GPT-3.5/ChatGPT"),
        (r"\bgpt.?4(?:v|vision)\b|\bgpt.4\s*vision\b", "GPT-4V"),
        (r"\bo1\b|\bo3\b|\bo4.mini\b", "OpenAI-o-series"),
        (r"\bllama.?3(?:\.\d)?\b", "LLaMA-3"),
        (r"\bllama.?2\b", "LLaMA-2"),
        (r"\bllama\b(?!\.?2|\.?3)", "LLaMA"),
        (r"\bmistral\b", "Mistral"),
        (r"\bbert\b(?!\s+score)", "BERT"),
        (r"\broberta\b", "RoBERTa"),
        (r"\bdeberta\b", "DeBERTa"),
        (r"\bt5\b|\bflan.?t5\b", "T5/FlanT5"),
        (r"\bpalm.?2?\b", "PaLM"),
        (r"\bclaude\b", "Claude"),
        (r"\bgemini\b(?!\s+vision)", "Gemini"),
        (r"\bbard\b", "Bard"),
        (r"\bdeepseek\b", "DeepSeek"),
        (r"\bqwen\b", "Qwen"),
        (r"\bvicuna\b", "Vicuna"),
        (r"\balpaca\b", "Alpaca"),
        (r"\bllave\b|\bllava\b", "LLaVA"),
        (r"\binternvl\b", "InternVL"),
        (r"\bblip.?2\b", "BLIP-2"),
        (r"\bstable\s+diffusion\b|\bsdxl\b", "Stable Diffusion"),
        (r"\bdall.?e\b", "DALL-E"),
        (r"\bbart\b", "BART"),
    ]
    for pat, label in checks:
        if re.search(pat, src, re.IGNORECASE) and label not in models:
            models.append(label)
    if not models and re.search(r"\b(large\s+language\s+model|LLM)\b", src, re.IGNORECASE):
        models.append("LLM (unspecified)")
    return "; ".join(models) if models else NR


def extr_rag_component(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    comps = []
    checks = [
        (r"\b(retrieval.augmented\s+generation|rag\b)", "RAG"),
        (r"\b(vector\s+(?:database|store|index|search)|chromadb|faiss|pinecone|weaviate|qdrant)\b", "vector-DB"),
        (r"\b(embedding\s+(?:model|search|retrieval)|semantic\s+search)\b", "semantic-retrieval"),
        (r"\b(knowledge\s+(?:base|graph|retrieval)|knowledge.grounded)\b", "knowledge-base"),
        (r"\b(bm25|tf.idf|sparse\s+retrieval)\b", "sparse-retrieval"),
        (r"\b(dense\s+retrieval|dpr\b)\b", "dense-retrieval"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in comps:
            comps.append(label)
    return "; ".join(comps) if comps else NR


def extr_rubric(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(analytic\s+rubric|analytic\s+grading\s+rubric)\b", "analytic rubric"),
        (r"\b(holistic\s+rubric|holistic\s+scoring)\b", "holistic rubric"),
        (r"\b(scoring\s+rubric|grading\s+rubric|assessment\s+rubric|rubric.based)\b", "rubric"),
        (r"\b(model\s+answer|answer\s+key|reference\s+(?:answer|solution)|gold\s+(?:label|answer))\b", "reference answer"),
        (r"\b(mark(?:ing)?\s+(?:scheme|guide|criteria)|grade\s+scheme)\b", "marking scheme"),
        (r"\b(learning\s+objectives?|competency\s+(?:framework|criteria))\b", "learning objectives"),
        (r"\b(standardized\s+(?:scoring|rubric|criteria))\b", "standardized rubric"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_evidence_grounding(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(chain.of.thought|cot\b|step.by.step\s+reasoning)\b", "chain-of-thought"),
        (r"\b(citation|source\s+attribution|evidence\s+grounding|source.grounded)\b", "citation-grounding"),
        (r"\b(faithfulness|faithful\s+(?:generation|response))\b", "faithfulness"),
        (r"\b(fact.check|factuality\s+(?:check|evaluation))\b", "fact-checking"),
        (r"\b(retrieval.grounded|grounded\s+(?:response|generation))\b", "retrieval-grounding"),
        (r"\b(reasoning\s+trace|rationale\s+generation)\b", "rationale-generation"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_hallucination(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"] + " " + s["results"]).lower()
    items = []
    checks = [
        (r"\b(hallucination\s+(?:detection|rate|test|evaluation|metric))\b", "hallucination-detection"),
        (r"\b(factual\s+(?:accuracy|error|inconsistency)|factual\s+hallucination)\b", "factual-accuracy"),
        (r"\b(faithfulness\s+(?:score|metric|evaluation)|nli\s+(?:score|check))\b", "faithfulness-score"),
        (r"\b(confabulation)\b", "confabulation"),
        (r"\b(bertscore\b|semantic\s+similarity\s+to\s+(?:gold|reference))", "semantic-similarity"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_calibration(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(calibrat(?:ion|ed|ing)|temperature\s+scaling)\b", "calibration"),
        (r"\b(confidence\s+(?:interval|score|calibration)|reliability\s+diagram)\b", "confidence-calibration"),
        (r"\b(ece\b|expected\s+calibration\s+error)\b", "ECE"),
        (r"\b(platt\s+scaling)\b", "Platt scaling"),
        (r"\b(isotonic\s+regression)\b", "isotonic regression"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_calibration_metric(s: dict) -> str:
    src = s["results"] + " " + s["full"][:5000]
    patterns = [
        r"(?:ECE|expected\s+calibration\s+error)\s*[=:≈]\s*([0-9.]+)",
        r"(?:calibration\s+error)\s*[=:≈]\s*([0-9.]+)",
        r"(?:reliability|calibration)\s+(?:score|metric)\s*[=:≈]\s*([0-9.]+)",
    ]
    for p in patterns:
        m = re.search(p, src, re.IGNORECASE)
        if m:
            return m.group(0).strip()[:200]
    return NR


def extr_uncertainty(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(uncertainty\s+(?:quantification|estimation|aware)|abstention)\b", "uncertainty-quantification"),
        (r"\b(confidence\s+threshold|confidence.based\s+(?:routing|abstention))\b", "confidence-threshold"),
        (r"\b(selective\s+(?:prediction|classification)|defer(?:ral|ring)\s+to\s+human)\b", "selective-prediction"),
        (r"\b(dropout\s+(?:uncertainty|sampling)|monte\s+carlo\s+dropout)\b", "MC-dropout"),
        (r"\b(entropy.based|predictive\s+entropy)\b", "entropy-based"),
        (r"\b(human.in.the.loop|teacher\s+review|expert\s+review)\b", "human-in-the-loop"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_explainability(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(shap\b|shapley|feature\s+importance|saliency\s+map)\b", "SHAP/saliency"),
        (r"\b(lime\b)\b", "LIME"),
        (r"\b(attention\s+(?:map|weight|visualization))\b", "attention-vis"),
        (r"\b(rationale\s+(?:generation|extraction)|explanation\s+generation)\b", "rationale-generation"),
        (r"\b(grad.?cam\b|gradient.based\s+(?:attribution|explanation))\b", "GradCAM"),
        (r"\b(interpretab(?:le|ility)|explainable\s+ai|xai)\b", "XAI"),
        (r"\b(feedback\s+(?:generation|explanation)|scoring\s+justification)\b", "feedback-generation"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_fairness(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(bias(?:es)?\s+(?:detection|mitigation|analysis|evaluation)|demographic\s+(?:bias|parity))\b", "bias-detection"),
        (r"\b(fairness\s+(?:metric|constraint|evaluation|aware))\b", "fairness-metric"),
        (r"\b(gender\s+(?:bias|fairness)|racial\s+bias|ethnic\s+bias)\b", "demographic-bias"),
        (r"\b(equal\s+opportunity|equalized\s+odds)\b", "equalized-odds"),
        (r"\b(adverse\s+impact|disparate\s+(?:impact|treatment))\b", "disparate-impact"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_hitl(s: dict) -> str:
    src = (s["abstract"] + " " + s["methods"]).lower()
    items = []
    checks = [
        (r"\b(human.in.the.loop|human\s+(?:review|verification|check|oversight))\b", "human-review"),
        (r"\b(teacher\s+(?:review|verification|approval|oversight))\b", "teacher-review"),
        (r"\b(active\s+learning|human\s+annotation|crowdsourc)\b", "active-learning"),
        (r"\b(hybrid\s+(?:scoring|grading|assessment)|human.ai\s+(?:collaboration|grading))\b", "hybrid-grading"),
        (r"\b(deferral\s+(?:policy|mechanism)|defer\s+to\s+human)\b", "deferral"),
        (r"\b(human\s+(?:expert|rater|annotator|evaluator)\s+(?:in\s+the\s+loop|involved|checked))\b", "expert-in-loop"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_dataset_info(s: dict) -> tuple[str, str]:
    src = s["methods"] + " " + s["results"] + " " + s["abstract"]

    # --- Dataset name ---
    name_patterns = [
        r"(?:dataset|corpus|benchmark|collection)\s+(?:called|named|termed|entitled|known\s+as)\s+['\"]?([A-Z][\w\s\-]{2,50}?)['\"]?[\s,.]",
        r"['\"]([A-Z][A-Z\d\-_]{2,30})['\"]?\s+(?:dataset|corpus|benchmark|collection)",
        r"(?:the\s+)([A-Z][\w\-]+(?:\s+[\w]+){0,3})\s+(?:dataset|corpus|benchmark|collection)\b",
        r"(?:we\s+(?:use|adopt|employ|evaluate\s+on)|using|evaluated?\s+on)\s+(?:the\s+)?([A-Z][\w\-]+(?:\s+[\w]+){0,2})\s+(?:dataset|corpus|benchmark)",
        r"([A-Z][A-Z\d]{2,15})\s+(?:dataset|benchmark|corpus)\b",
        # We introduce/present/construct a (new) dataset named X
        r"we\s+(?:introduce|present|construct|curate|collect(?:ed)?|build|created?|release)\s+a\s+(?:new\s+)?(?:dataset|corpus|benchmark)\s+(?:called|named|termed)?\s*['\"]?([A-Z][\w\-]{2,40})['\"]?",
        # X, a dataset/benchmark of ...
        r"([A-Z][\w\-]{2,30}),?\s+a\s+(?:new\s+)?(?:dataset|corpus|benchmark)\s+(?:of|for|comprising|containing)",
        # own/proprietary/in-house dataset (no proper name — still informative)
        r"\b(our\s+own\s+dataset|in-house\s+dataset|proprietary\s+dataset|custom\s+dataset)\b",
    ]
    name = NR
    stopwords = {"the", "our", "this", "a", "an", "new", "proposed", "paper", "study",
                 "all", "each", "standard", "public", "open", "real", "full", "main",
                 "same", "training", "test", "eval", "benchmark"}
    for pat in name_patterns:
        for m in re.finditer(pat, src):
            candidate = m.group(1).strip()
            if candidate.lower() not in stopwords and len(candidate) > 2:
                name = candidate[:80]
                break
        if name != NR:
            break

    # Fallback: bare mention of a well-known benchmark/dataset name, even
    # without an adjacent "dataset/corpus/benchmark" keyword (common in
    # results tables and abstracts, e.g. "evaluated on ASAP and MATH").
    if name == NR:
        KNOWN_BENCHMARKS = [
            "ASAP", "ASAP-AES", "ASAP++", "AR-ASAG", "MATH", "GSM8K", "MMLU",
            "SQuAD", "SQuAD2.0", "GLUE", "SuperGLUE", "HellaSwag", "TruthfulQA",
            "HumanEval", "MBPP", "ARC", "PIQA", "WinoGrande", "BoolQ",
            "CommonsenseQA", "TriviaQA", "NaturalQuestions", "MS MARCO",
            "CoQA", "RACE", "DROP", "BIG-Bench", "MT-Bench", "AlpacaEval",
            "COCO", "MS-COCO", "ImageNet", "CIFAR-10", "CIFAR-100", "MNIST",
            "VQA", "TextVQA", "DocVQA", "ChartQA", "ScienceQA", "OK-VQA",
            "NCTE", "FeedbackPrize", "Feedback Prize", "CLC-FCE", "FCE",
            "TOEFL11", "ICLE", "CEDEL2", "Speechocean762", "IELTS",
        ]
        low = src.lower()
        for bench in KNOWN_BENCHMARKS:
            if re.search(r"\b" + re.escape(bench.lower()) + r"\b", low):
                name = bench
                break

    # --- Dataset size ---
    size_patterns = [
        r"(\d[\d,]+)\s+(?:unique\s+)?(?:samples?|instances?|items?|passages?|documents?|essays?|questions?|responses?|answers?|data\s*points?|observations?|records?|examples?|images?|entries)",
        r"(?:total|overall|in\s+total|comprising|consisting\s+of)\s+(\d[\d,]+)",
        r"(\d[\d,]+)\s+(?:student|human|expert)\s+(?:responses?|answers?|submissions?)",
        r"n\s*[=:]\s*(\d[\d,]+)",
        r"(\d+k?)\s+(?:texts?|samples?|items?|instances?)\b",
    ]
    size = NR
    for pat in size_patterns:
        m = re.search(pat, src, re.IGNORECASE)
        if m:
            size = m.group(1).replace(",", "")
            break

    return name, size


def extr_annotation(s: dict) -> str:
    src = (s["methods"] + " " + s["abstract"]).lower()
    items = []
    checks = [
        (r"\b(human\s+(?:annotation|annotator|label(?:ler)?|rater)|expert\s+(?:label|rater|annotation))\b", "human-annotation"),
        (r"\b(inter.rater\s+(?:agreement|reliability)|inter.annotator\s+agreement|iaa\b|cohen.s\s+kappa|fleiss\s+kappa)\b", "inter-rater-agreement"),
        (r"\b(gold\s+(?:standard|label)|reference\s+(?:label|answer)|ground\s+truth)\b", "gold-label"),
        (r"\b(crowdsourc(?:ed?|ing)|mechanical\s+turk|mturk|amazon\s+turk)\b", "crowdsourcing"),
        (r"\b(automatic\s+(?:annotation|label(?:ling)?)|silver\s+label)\b", "auto-annotation"),
        (r"\b(manually\s+(?:label(?:l?ed)?|annotat(?:ed|ing)|scored|graded|reviewed))\b", "manual-annotation"),
        (r"\b(double[- ]annotat(?:ed|ion)|two\s+annotators|multiple\s+annotators|third\s+annotator|adjudicat(?:ed|ion|or))\b", "multi-annotator"),
        (r"\b(teachers?|instructors?|educators?)\s+(?:scored|graded|labeled|labelled|rated|annotated)\b", "teacher-annotation"),
        (r"\b(consensus\s+(?:label(?:l?ing)?|scoring)|resolved\s+by\s+discussion)\b", "consensus-labeling"),
        (r"\b(pre-?existing\s+(?:labels?|annotations?|ground\s+truth)|original(?:ly)?\s+(?:labeled|scored)\s+by)\b", "pre-existing-labels"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_ethics(s: dict) -> str:
    src = s["full"].lower()
    items = []
    checks = [
        (r"\b(irb\b|institutional\s+review\s+board|ethics\s+(?:approval|committee|review|board))\b", "IRB-approved"),
        (r"\b(informed\s+consent|participant\s+consent)\b", "informed-consent"),
        (r"\b(anonymi[sz](?:ed?|ation)|de.?identified|privacy\s+(?:preserving|protection))\b", "anonymized"),
        (r"\b(gdpr|ferpa|coppa|hipaa)\b", "data-privacy-regulation"),
        (r"\b(data\s+protection|privacy\s+(?:policy|concern))\b", "data-protection"),
        (r"\b(synthetic\s+(?:data|student))\b", "synthetic-data"),
    ]
    for pat, label in checks:
        if re.search(pat, src) and label not in items:
            items.append(label)
    return "; ".join(items) if items else NR


def extr_data_split(s: dict) -> str:
    src = (s["methods"] + " " + s["results"]).lower()
    items = []
    checks = [
        (r"\b(\d+.?\d*[%/]\s*(?:train|training)\s*[/,]\s*\d+.?\d*[%/]\s*(?:val|valid|dev)?\s*[/,]?\s*\d+.?\d*[%/]\s*(?:test))\b", None),
        (r"\b(cross.validation|k.fold|leave.one.out)\b", "cross-validation"),
        (r"\b(held.?out\s+(?:test\s+)?set|independent\s+test\s+set)\b", "held-out-test"),
        (r"\b(data\s+split|train.test\s+split|stratified\s+split)\b", "train-test-split"),
        (r"\b(temporal\s+split|chronological\s+split)\b", "temporal-split"),
        (r"\b(leakage\s+(?:control|prevention)|data\s+(?:contamination|leakage))\b", "leakage-controlled"),
    ]
    found = []
    for pat, label in checks:
        m = re.search(pat, src)
        if m:
            if label is None:
                found.append(m.group(0).strip()[:60])
            elif label not in found:
                found.append(label)
    return "; ".join(found) if found else NR


def extr_baselines(s: dict) -> str:
    src = s["methods"] + " " + s["results"] + " " + s["abstract"]
    # Look for baseline comparison statements
    patterns = [
        r"(?:compare(?:d)?\s+(?:to|with|against)|baseline[s]?(?:\s+include)?[:\s]+|vs\.?\s+|versus\s+)([^.;]{10,200}(?:model|method|approach|system|algorithm|classifier|GPT|BERT|baseline)[^.;]{0,100})",
        r"(?:baselines?|comparison\s+methods?|competing\s+methods?)\s*[:\-]\s*([^.]{10,300})",
        r"(?:outperform(?:s|ing|ed)?|better\s+than|superior\s+to)\s+([^.]{10,150}(?:model|method|approach|baseline|system)[^.]{0,80})",
        # human raters / majority-class / random / zero-shot as baseline
        r"([^.]{0,80}(?:human\s+(?:raters?|graders?|annotators?|experts?)|majority[- ]class|random\s+guessing|zero[- ]shot|few[- ]shot)\s+baseline[^.]{0,100})",
        # "against N baselines including A, B, C"
        r"(?:against|with)\s+(?:\d+\s+)?(?:other\s+)?(?:state[- ]of[- ]the[- ]art|SOTA|existing)?\s*(?:baselines?|methods?|models?|approaches?)\s*(?:,?\s*(?:such\s+as|including|namely|e\.g\.,?))\s*([^.]{10,250})",
        # "we benchmark against X"
        r"(?:benchmark(?:ed)?\s+against|evaluated?\s+against)\s+([^.]{10,200})",
    ]
    results = []
    for p in patterns:
        for m in re.finditer(p, src, re.IGNORECASE):
            text = _clean(m.group(1))[:200]
            if text and text not in results:
                results.append(text)
    if results:
        return "; ".join(results[:3])
    # Fallback: look for model names explicitly compared
    m = re.search(r"(?:compared\s+to|vs\.?)\s+([A-Z][\w\-]+(?:\s+[\w\-]+){0,3})", src)
    if m:
        return _clean(m.group(1))[:200]
    # Last resort: any recognizable model name mentioned alongside "baseline"/"compar-"
    m = re.search(r"([^.]{0,60}\b(?:GPT-?4o?|GPT-?3\.5|ChatGPT|BERT|RoBERTa|LLaMA|Claude|Gemini|Mistral|T5)\b[^.]{0,100}\b(?:baseline|compar\w*)[^.]{0,60})", src, re.IGNORECASE)
    if m:
        return _clean(m.group(1))[:200]
    return NR


def extr_primary_metrics(s: dict) -> str:
    """Extract metric names AND values from results sections."""
    src = s["results"] + " " + s["conclusion"] + " " + s["full"][:8000]
    found = []

    metric_patterns = [
        # Named metric = value patterns
        (r"(?:quadratic\s+weighted\s+kappa|QWK)\s*[=:≈]\s*([0-9.]+)", "QWK"),
        (r"(?:cohen'?s?\s+kappa|kappa\s+(?:score|coefficient))\s*[=:≈]\s*([0-9.]+)", "Cohen's-κ"),
        (r"\baccuracy\s*[=:≈]\s*([0-9.]+\s*%?)", "Accuracy"),
        (r"\bF[- ]?1(?:[- ]?score)?\s*[=:≈]\s*([0-9.]+)", "F1"),
        (r"\bprecision\s*[=:≈]\s*([0-9.]+)", "Precision"),
        (r"\brecall\s*[=:≈]\s*([0-9.]+)", "Recall"),
        (r"\bAUC(?:[- ]?ROC)?\s*[=:≈]\s*([0-9.]+)", "AUC"),
        (r"\bBLEU(?:[- ]?\d)?\s*[=:≈]\s*([0-9.]+)", "BLEU"),
        (r"\bROUGE[- ]?[L12]?\s*[=:≈]\s*([0-9.]+)", "ROUGE"),
        (r"\bPearson\s+(?:r|correlation)\s*[=:≈]\s*([0-9.]+)", "Pearson-r"),
        (r"\bSpearman\s+(?:ρ|rho)?\s*[=:≈]\s*([0-9.]+)", "Spearman-ρ"),
        (r"\bMAE\s*[=:≈]\s*([0-9.]+)", "MAE"),
        (r"\bRMSE\s*[=:≈]\s*([0-9.]+)", "RMSE"),
        (r"\bMSE\s*[=:≈]\s*([0-9.]+)", "MSE"),
        (r"\bboundary\s+adjacent\s+agreement\b.*?[=:≈]\s*([0-9.]+\s*%?)", "Adjacent-Agree"),
        (r"\bexact\s+agreement\s*[=:≈]\s*([0-9.]+\s*%?)", "Exact-Agree"),
        (r"\bBERTScore\s*[=:≈]\s*([0-9.]+)", "BERTScore"),
        (r"\bMETEOR\s*[=:≈]\s*([0-9.]+)", "METEOR"),
        (r"\bCIDEr\s*[=:≈]\s*([0-9.]+)", "CIDEr"),
        (r"\bSPICE\s*[=:≈]\s*([0-9.]+)", "SPICE"),
        (r"\bWER\s*[=:≈]\s*([0-9.]+\s*%?)", "WER"),
        (r"\bCER\s*[=:≈]\s*([0-9.]+\s*%?)", "CER"),
    ]

    seen_metrics = set()
    for pat, name in metric_patterns:
        for m in re.finditer(pat, src, re.IGNORECASE):
            val = m.group(1).strip()
            entry = f"{name}={val}"
            if name not in seen_metrics:
                found.append(entry)
                seen_metrics.add(name)
            if len(found) >= 8:
                break
        if len(found) >= 8:
            break

    # If no exact = values, look for metric names at least
    if not found:
        metric_names = []
        name_pats = [
            (r"\b(QWK|quadratic weighted kappa)\b", "QWK"),
            (r"\b(accuracy|acc\.?)\b", "Accuracy"),
            (r"\b(F1|F-1|F1-score)\b", "F1"),
            (r"\b(kappa|cohen'?s kappa)\b", "Cohen's-κ"),
            (r"\b(Pearson|Spearman)\b", "Pearson/Spearman"),
            (r"\b(BLEU|ROUGE|METEOR|BERTScore)\b", "BLEU/ROUGE"),
        ]
        for p, n in name_pats:
            if re.search(p, src, re.IGNORECASE) and n not in metric_names:
                metric_names.append(n)
        if metric_names:
            return "; ".join(metric_names)

    return "; ".join(found) if found else NR


def extr_key_results(s: dict) -> str:
    """Extract top quantitative results (metric = value sentences)."""
    src = s["results"] + " " + s["conclusion"]
    if not src.strip():
        src = s["full"][-5000:]

    # Find sentences with metric values
    result_sentences = []
    sentences = re.split(r"(?<=[.!?])\s+", src)
    metric_kws = r"accuracy|F1|kappa|QWK|BLEU|ROUGE|Pearson|Spearman|precision|recall|AUC|RMSE|MAE|score|agreement|correlation"
    for sent in sentences:
        if re.search(metric_kws, sent, re.IGNORECASE) and re.search(r"\b\d+\.?\d*\s*%?", sent):
            cleaned = _clean(sent)[:300]
            if cleaned and cleaned not in result_sentences:
                result_sentences.append(cleaned)
        if len(result_sentences) >= 4:
            break

    # Filter junk sentences
    result_sentences = [s for s in result_sentences if not _is_junk(s)]

    if result_sentences:
        return " | ".join(result_sentences[:3])

    # Fallback: look for explicit result statements
    patterns = [
        r"(?:our\s+(?:model|method|approach|system)\s+(?:achieve[sd]?|obtain[sed]?|reach[sed]?)|we\s+achieve[sd]?|results?\s+show\s+that)\s+(.{30,300}?[0-9.]+\s*%?[^.]{0,100}\.)",
        r"(?:best\s+(?:result|performance|score|accuracy)|highest\s+(?:score|accuracy|F1))[^.]{0,50}([0-9.]+\s*%?)[^.]{0,100}\.",
    ]
    for p in patterns:
        m = re.search(p, src, re.IGNORECASE | re.DOTALL)
        if m:
            cand = _clean(m.group(0))[:400]
            if not _is_junk(cand):
                return cand

    return NR


def _is_junk(text: str) -> bool:
    """Return True if text looks like references/URLs/boilerplate, not a finding."""
    t = text.lower()
    if re.search(r"https?://|doi\.org|arxiv\.|github\.com", t):
        return True
    if re.search(r"\[\d+\]|\(\d{4}\).*et al\.", t):
        return True
    if re.search(r"(?:data availability|conflict of interest|acknowledgement|funding|author contribution)", t):
        return True
    if re.search(r"(?:references?|bibliography)\s*\n", t):
        return True
    return False


def extr_main_findings(s: dict) -> str:
    """2-4 sentence factual summary from conclusion."""
    src = s["conclusion"]
    if not src:
        src = s["full"][-4000:]

    # Split to sentences and filter junk
    sentences = re.split(r"(?<=[.!?])\s+", src)
    clean_sents = [_clean(sent) for sent in sentences
                   if len(sent.strip()) > 40 and not _is_junk(sent)]

    patterns = [
        r"(?:in\s+(?:this\s+(?:paper|study|work)|summary|conclusion),?\s*)(.{60,500}?\.)",
        r"(?:we\s+(?:conclude|find|demonstrate|show|present|propose|introduce)\s+that?\s*)(.{60,400}?\.)",
        r"(?:our\s+(?:results?|findings?|experiments?|evaluation)\s+(?:show|demonstrate|indicate|suggest|reveal)\s+that?\s*)(.{60,400}?\.)",
        r"(?:the\s+(?:results?|findings?|experiments?)\s+(?:show|demonstrate|indicate|suggest)\s+that?\s*)(.{60,400}?\.)",
        r"(?:this\s+(?:paper|work|study)\s+(?:proposes?|presents?|introduces?|demonstrates?)\s*)(.{60,400}?\.)",
        r"(?:overall|taken\s+together|in\s+sum),?\s*(.{60,400}?\.)",
    ]
    findings = []
    src_clean = " ".join(clean_sents)
    for p in patterns:
        m = re.search(p, src_clean, re.IGNORECASE | re.DOTALL)
        if m:
            text = _clean(m.group(0))[:400]
            if text and not _is_junk(text) and text not in findings:
                findings.append(text)
        if len(findings) >= 2:
            break

    if findings:
        return " ".join(findings[:2])

    # Last resort: first 3 non-junk sentences of conclusion
    if clean_sents:
        return " ".join(clean_sents[:3])[:500]

    return NR


def extr_limitations(s: dict) -> str:
    src = s["limitations"] + " " + s["conclusion"]
    if not src.strip():
        src = s["full"][-4000:]

    patterns = [
        r"(?:limitations?\s+(?:of\s+(?:this|the)\s+(?:study|work|paper|research)|include|are)?)\s*[:\-]?\s*(.{40,500}?\.)",
        r"(?:one\s+limitation|a\s+(?:key\s+)?limitation|our\s+(?:main\s+)?limitation)\s+(?:is|of\s+this|that)\s+(.{40,400}?\.)",
        r"(?:future\s+(?:work|research)\s+(?:should|could|may|will)?)\s+(.{40,300}?\.)",
        r"(?:we\s+acknowledge|we\s+note\s+that|it\s+should\s+be\s+noted)\s+(.{40,300}?\.)",
    ]
    for p in patterns:
        m = re.search(p, src, re.IGNORECASE | re.DOTALL)
        if m:
            return _clean(m.group(0))[:500]
    return NR


def extr_code_data(s: dict) -> tuple[str, str]:
    full = s["full"].lower()
    code = NR
    data = NR

    if re.search(r"github\.com|gitlab\.com|huggingface\.co/(?!papers)", full):
        code = "yes"
    elif re.search(r"code\s+(?:is\s+)?(?:publicly\s+)?available|source\s+code\s+released?|code\s+release", full):
        code = "yes"
    elif re.search(r"code\s+(?:is\s+)?(?:not\s+)?(?:publicly\s+)?(?:released?|available)|proprietary|closed.source", full):
        code = "no"

    if re.search(r"data(?:set)?\s+(?:is\s+)?(?:publicly\s+)?available|available\s+(?:at|on|from)\s+(?:github|zenodo|figshare|osf|huggingface|kaggle|ieee\s+dataport)", full):
        data = "yes"
    elif re.search(r"(?:data|dataset)\s+(?:available|released?|shared?)\s+(?:upon|on)\s+request", full):
        data = "upon request"
    elif re.search(r"(?:proprietary|confidential|private|institutional|cannot\s+be\s+shared)", full):
        data = "no"

    return code, data


def extr_funding(s: dict) -> str:
    src = s["full"].lower()
    patterns = [
        r"(?:supported?\s+by|funded?\s+by|funding\s+(?:from|provided\s+by)|grant\s+(?:from|number|no\.?))\s+([^.]{10,200}\.)",
        r"(?:acknowledge\s+(?:the\s+)?(?:support|funding|grant)\s+(?:of|from)?)\s+([^.]{10,200}\.)",
        r"(?:conflict\s+of\s+interest|no\s+competing\s+interest|no\s+conflict)\s+([^.]{0,200}\.)",
    ]
    for p in patterns:
        m = re.search(p, src, re.IGNORECASE)
        if m:
            return _clean(m.group(0))[:300]
    return NR


# ─────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────

def extract_from_text(text: str, record: dict) -> dict:
    row = {f: NR for f in evidence_extraction_fieldnames()}
    row["record_id"]     = record.get("record_id", "")
    row["doi_normalized"]= record.get("doi_normalized", "")
    row["citation_key"]  = record.get("citation_key", "")

    if not text or len(text) < 300:
        row["notes"] = "PDF text extraction failed or too short"
        row["extraction_status"] = "needs_review"
        row["human_verified"] = "false"
        return row

    s = split_sections(text)

    row["educational_context"]         = extr_educational_context(s)
    row["educational_level"]           = extr_educational_level(s)
    row["subject_area"]                = extr_subject_area(s)
    row["assessment_task"]             = extr_assessment_task(s)
    row["answer_format"]               = extr_answer_format(s)
    row["input_modalities"]            = extr_input_modalities(s)
    row["document_or_image_type"]      = extr_document_image_type(s)
    row["ocr_or_document_model"]       = extr_ocr_model(s)
    row["generative_model"]            = extr_generative_model(s)
    row["retrieval_or_rag_component"]  = extr_rag_component(s)
    row["rubric_or_reference_material"]= extr_rubric(s)
    row["evidence_grounding_method"]   = extr_evidence_grounding(s)
    row["hallucination_definition_or_test"] = extr_hallucination(s)
    row["calibration_method"]          = extr_calibration(s)
    row["calibration_metric_result"]   = extr_calibration_metric(s)
    row["uncertainty_or_abstention_method"] = extr_uncertainty(s)
    row["explainability_method"]       = extr_explainability(s)
    row["fairness_or_bias_method"]     = extr_fairness(s)
    row["human_in_the_loop_design"]    = extr_hitl(s)

    ds_name, ds_size = extr_dataset_info(s)
    row["dataset_name"]  = ds_name
    row["dataset_size"]  = ds_size

    row["annotation_and_ground_truth"] = extr_annotation(s)
    row["ethics_consent_privacy"]      = extr_ethics(s)
    row["data_split_leakage_controls"] = extr_data_split(s)
    row["baselines"]                   = extr_baselines(s)
    row["primary_metrics"]             = extr_primary_metrics(s)
    row["key_results"]                 = extr_key_results(s)
    row["main_findings"]               = extr_main_findings(s)
    row["author_reported_limitations"] = extr_limitations(s)

    code, data = extr_code_data(s)
    row["code_available"] = code
    row["data_available"] = data
    row["funding_conflicts"] = extr_funding(s)

    # Count non-NR substantive fields
    subst = [f for f in evidence_extraction_fieldnames()
             if f not in ("record_id", "doi_normalized", "citation_key",
                          "extraction_status", "human_verified",
                          "evidence_page_section", "notes")]
    n_filled = sum(1 for f in subst if row.get(f, NR) not in (NR, "", "false", "true"))

    row["evidence_page_section"] = "auto-extracted from abstract/methods/results/conclusion"
    row["extraction_status"]     = "ai_draft"
    row["human_verified"]        = "false"
    row["notes"] = f"v4-comprehensive; {n_filled}/{len(subst)} fields populated"

    # Sanitize: strip characters that break CSV (double-quotes → single, newlines → space)
    for k, v in row.items():
        if isinstance(v, str):
            row[k] = v.replace('"', "'").replace("\n", " ").replace("\r", " ")

    return row


def _citation_key(record: dict) -> str:
    authors = record.get("authors", "")
    year    = record.get("publication_year", "")
    if not authors or not year:
        return record.get("citation_key", "")
    first = authors.split(";")[0].strip()
    parts = first.split()
    surname = parts[-1] if parts else first.split(",")[0]
    return f"{surname}{year}" if surname else ""


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max",    type=int, default=0, help="Max PDFs to process (0=all)")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N PDFs in task list")
    parser.add_argument("--force",  action="store_true",  help="Re-extract all (even human_verified)")
    args = parser.parse_args()

    manifest  = read_csv_rows(MANIFEST)
    worklist  = read_csv_rows(WORKLIST)
    worklist_by_doi = {r["doi_normalized"]: r for r in worklist}

    # Also check master for richer metadata (authors, year)
    # Use first occurrence per DOI to avoid duplicates overriding worklist record_id
    master    = read_csv_rows(MASTER) if MASTER.exists() else []
    master_by_doi: dict = {}
    for r in master:
        doi = r.get("doi_normalized", "")
        if doi and doi not in master_by_doi:
            master_by_doi[doi] = r

    existing = {}
    if EXTRACTION.exists():
        for r in read_csv_rows(EXTRACTION):
            existing[r["record_id"]] = r

    tasks = []
    for entry in manifest:
        doi = entry.get("doi_normalized", "")
        fn  = entry.get("filename", "")
        if not doi or not fn:
            continue
        pdf_path = CORPUS / fn
        if not pdf_path.exists():
            continue
        # Worklist is authoritative for record_id; master adds authors/year only
        worklist_rec = worklist_by_doi.get(doi, {})
        master_rec   = master_by_doi.get(doi, {})
        record = {**master_rec, **worklist_rec}   # worklist overrides master
        if not record.get("record_id"):
            continue
        record["citation_key"] = _citation_key(record) or record.get("citation_key", "")
        tasks.append((record, pdf_path))

    if args.offset > 0:
        tasks = tasks[args.offset:]
    if args.max > 0:
        tasks = tasks[:args.max]

    print(f"Processing {len(tasks)} PDFs with comprehensive v4 extractor (offset={args.offset})...")

    # Start from existing, preserving human_verified rows
    results = list(existing.values())
    extracted = skipped = 0

    for i, (record, pdf_path) in enumerate(tasks):
        rid = record.get("record_id", "")
        prev = existing.get(rid, {})

        if not args.force and prev.get("human_verified", "").lower() == "true":
            skipped += 1
            continue

        print(f"  [{i+1}/{len(tasks)}] {rid} ({pdf_path.name[:50]})...", end=" ")

        text = extract_text(pdf_path)
        row  = extract_from_text(text, record)

        results = [r for r in results if r.get("record_id") != rid]
        results.append(row)
        extracted += 1

        # Show fill rate
        subst = [f for f in evidence_extraction_fieldnames()
                 if f not in ("record_id", "doi_normalized", "citation_key",
                              "extraction_status", "human_verified",
                              "evidence_page_section", "notes")]
        filled = sum(1 for f in subst if row.get(f, NR) not in (NR, ""))
        print(f"OK  text={len(text):,}c  filled={filled}/{len(subst)}")

    import csv as _csv
    fieldnames = evidence_extraction_fieldnames()
    # Sanitize all rows before writing (remove chars that break csv)
    def _san(v: str) -> str:
        if not isinstance(v, str):
            return str(v) if v is not None else ""
        return v.replace('"', "'").replace("\n", " ").replace("\r", " ").strip()
    results = [{k: _san(v) for k, v in r.items()} for r in results]
    EXTRACTION.parent.mkdir(parents=True, exist_ok=True)
    with EXTRACTION.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=fieldnames,
                                 extrasaction="ignore",
                                 quoting=_csv.QUOTE_ALL)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\nDone — extracted={extracted}, skipped(human_verified)={skipped}, total={len(results)}")
    log_run_event({
        "stage": "extract_evidence_v4_comprehensive",
        "pdfs_processed": extracted,
        "skipped": skipped,
        "total_rows": len(results),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
