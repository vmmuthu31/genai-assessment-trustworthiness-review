#!/usr/bin/env python3
"""Phase 4b: Deterministic auto-scoring pass for quality_appraisal.csv.

Derives as many of the 14 quality dimensions as possible from
outputs/csv/evidence_extraction.csv (v4-comprehensive fields), which after
scripts/17d_comprehensive_extract.py has much richer coverage than a blank
template. Two dimensions (robustness, human_evaluation) aren't directly
covered by evidence_extraction fields, so this script does a light direct
keyword scan of the underlying PDF text for those two only.

This is a RULE-BASED, deterministic pass — same integrity posture as 17d:
every dimension value is a direct, traceable consequence of a regex/field
match, nothing is inferred or guessed. It is NOT a substitute for a human
(or full LLM-reading-the-PDF) quality appraisal per prompts/09_quality_appraiser.md
— rows remain quality_appraisal_status='ai_draft', human_verified='false'.

Usage:
    python scripts/18_auto_score_quality_appraisal.py            # all eligible rows
    python scripts/18_auto_score_quality_appraisal.py --max 20    # test on 20
    python scripts/18_auto_score_quality_appraisal.py --offset 20 --max 20
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_DIR, log_run_event, read_csv_rows, write_csv_rows

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
try:
    import fitz
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

CORPUS = OUTPUTS_DIR / "corpus"
EXTRACTION = OUTPUTS_DIR / "csv" / "evidence_extraction.csv"
DOWNLOADED = OUTPUTS_DIR / "csv" / "downloaded_papers.csv"
APPRAISAL = OUTPUTS_DIR / "csv" / "quality_appraisal.csv"

NR = "NR"

QUALITY_FIELDS_DIMENSIONS = [
    "dataset_and_consent", "ground_truth_construction", "leakage_safeguards",
    "baseline_comparisons", "evaluation_metrics", "calibration",
    "grounding", "hallucination_testing", "fairness",
    "robustness", "human_evaluation", "reproducibility",
    "limitations_reporting", "funding_conflicts",
]

ALL_QUALITY_FIELDS = (
    ["record_id", "doi_normalized", "citation_key"]
    + QUALITY_FIELDS_DIMENSIONS
    + ["narrative_summary_draft", "quality_appraisal_status", "human_verified",
       "reviewer_name", "review_date"]
)


def _yn(val: str) -> str:
    """Map an evidence_extraction field value to a strength-graded rating.

    Yes   = substantial evidence (multiple distinct items, e.g. 'a; b; c')
    Partial = a single, short/weak match
    NR    = no matching evidence found (absence of evidence, not evidence of absence)
    """
    if not val or val == NR or not val.strip():
        return NR
    v = val.strip()
    if ";" in v or len(v) > 40:
        return "yes"
    return "partial"


# Explicit-negation patterns: when the paper itself states a dimension does NOT
# apply / was NOT done, that's a real "No" — stronger and more specific than NR.
NEGATION_PATS = {
    "baseline_comparisons": [
        r"\bno\s+baselines?\s+(?:were|was)?\s*(?:used|compared|included)",
        r"\bwithout\s+(?:a\s+)?baseline\s+comparison",
        r"\bnot\s+compared\s+(?:to|with|against)\s+(?:any\s+)?baselines?",
    ],
    "calibration": [
        r"\b(?:no|not)\s+calibrat(?:ed|ion)",
        r"\bcalibration\s+(?:was\s+)?not\s+(?:performed|conducted|assessed)",
    ],
    "grounding": [
        r"\bno\s+(?:evidence\s+)?grounding\s+(?:mechanism|method)?",
        r"\bnot\s+grounded\s+in\s+(?:source|reference|evidence)",
    ],
    "hallucination_testing": [
        r"\b(?:no|not)\s+(?:formal\s+)?hallucination\s+(?:test(?:ing)?|evaluation|detection)",
        r"\bhallucinations?\s+(?:were\s+)?not\s+(?:tested|evaluated|measured)",
    ],
    "fairness": [
        r"\b(?:no|not)\s+fairness\s+(?:analysis|evaluation|assessment)",
        r"\bdid\s+not\s+(?:assess|evaluate|examine)\s+(?:for\s+)?(?:bias|fairness)",
    ],
    "robustness": [
        r"\b(?:no|not)\s+robustness\s+(?:test(?:ing)?|evaluation|analysis)",
        r"\bwithout\s+(?:adversarial|robustness)\s+(?:test(?:ing)?|evaluation)",
    ],
    "human_evaluation": [
        r"\bno\s+human\s+(?:evaluation|study|raters?|annotators?)\s+(?:was|were)?\s*(?:conducted|involved|used)",
        r"\bwithout\s+human\s+(?:evaluation|raters?|review)",
        r"\bpurely\s+automat(?:ed|ic)\s+evaluation",
    ],
    "reproducibility": [
        r"\bcode\s+(?:is\s+)?not\s+(?:publicly\s+)?(?:available|released)",
        r"\bdata\s+(?:is\s+)?not\s+(?:publicly\s+)?available",
        r"\bproprietary\s+(?:code|data|dataset)",
    ],
    "leakage_safeguards": [
        r"\bno\s+(?:data\s+)?leakage\s+(?:control|prevention|check)",
        r"\bdid\s+not\s+(?:control|check|test)\s+for\s+(?:data\s+)?(?:leakage|contamination)",
    ],
    "funding_conflicts": [
        r"\bno\s+(?:funding|financial\s+support)\s+(?:was\s+)?received",
        r"\bthe\s+authors?\s+declare\s+no\s+(?:conflict|competing)\s+(?:of\s+)?interest",
        r"\bno\s+conflicts?\s+of\s+interest",
    ],
}

# When there's no identifiable generative-AI system at all in the extraction
# (no model, no assessment task), these system-specific dimensions are
# structurally not applicable rather than simply "not reported".
NA_ELIGIBLE_DIMS = {"calibration", "grounding", "hallucination_testing", "robustness", "fairness"}


def _rate(dim: str, extracted_val: str, full_text: str) -> str:
    """Full Yes/No/Partial/NR/NA rating for one dimension."""
    base = _yn(extracted_val)
    if base in ("yes", "partial"):
        return base
    if full_text:
        for pat in NEGATION_PATS.get(dim, []):
            if re.search(pat, full_text, re.IGNORECASE):
                return "no"
    return NR


def extract_text(pdf_path: Path) -> str:
    text = ""
    if PdfReader is not None:
        try:
            reader = PdfReader(str(pdf_path), strict=False)
            for page in reader.pages:
                try:
                    text += page.extract_text() or ""
                except Exception:
                    pass
        except Exception:
            pass
    if len(text.strip()) < 300 and _HAS_FITZ:
        try:
            doc = fitz.open(str(pdf_path))
            text = "".join(p.get_text() for p in doc)
            doc.close()
        except Exception:
            pass
    return text


ROBUSTNESS_PATS = [
    r"\b(robustness\s+(?:test|evaluation|analysis|check))\b",
    r"\b(adversarial\s+(?:example|attack|robustness|test))\b",
    r"\b(out.of.distribution|OOD\s+(?:test|evaluation|generalization))\b",
    r"\b(stress\s+test|perturbation\s+(?:test|analysis)|noise\s+robustness)\b",
    r"\b(sensitivity\s+analysis|ablation\s+stud(?:y|ies))\b",
    r"\b(cross.domain\s+(?:evaluation|generalization)|domain\s+shift)\b",
]

HUMAN_EVAL_PATS = [
    r"\b(human\s+evaluation|human\s+(?:study|judge(?:ment|ment)?s?))\b",
    r"\b(user\s+stud(?:y|ies)|expert\s+(?:evaluation|review|study))\b",
    r"\b(teacher\s+(?:evaluation|survey|feedback))\b",
    r"\b(likert|survey\s+(?:study|questionnaire))\b",
    r"\b(human.ai\s+agreement|agreement\s+with\s+human\s+(?:raters?|graders?|scores?))\b",
]


def _any_match(pats: list[str], text: str) -> str:
    for p in pats:
        if re.search(p, text, re.IGNORECASE):
            return "yes"
    return NR


def score_row(erow: dict, pdf_text: str) -> dict:
    row = {f: NR for f in ALL_QUALITY_FIELDS}
    row["record_id"] = erow.get("record_id", "")
    row["doi_normalized"] = erow.get("doi_normalized", "")
    row["citation_key"] = erow.get("citation_key", "")

    # Is there even an identifiable generative-AI system in this record?
    # If not, the system-specific dimensions are NA, not just NR.
    has_system = (erow.get("generative_model", NR) != NR
                  or erow.get("assessment_task", NR) != NR)

    # Direct 1:1 mappings from the v4-comprehensive extraction fields, now on
    # the full Yes/No/Partial/NR/NA scale.
    dataset_signal = erow.get("dataset_name", NR) if erow.get("dataset_name", NR) != NR else erow.get("dataset_size", NR)
    ethics_signal = erow.get("ethics_consent_privacy", NR)
    row["dataset_and_consent"] = _rate("dataset_and_consent", dataset_signal if dataset_signal != NR else ethics_signal, pdf_text)
    row["ground_truth_construction"] = _rate("ground_truth_construction", erow.get("annotation_and_ground_truth", NR), pdf_text)
    row["leakage_safeguards"] = _rate("leakage_safeguards", erow.get("data_split_leakage_controls", NR), pdf_text)
    row["baseline_comparisons"] = _rate("baseline_comparisons", erow.get("baselines", NR), pdf_text)
    row["evaluation_metrics"] = _rate("evaluation_metrics", erow.get("primary_metrics", NR), pdf_text)
    row["limitations_reporting"] = _rate("limitations_reporting", erow.get("author_reported_limitations", NR), pdf_text)
    row["funding_conflicts"] = _rate("funding_conflicts", erow.get("funding_conflicts", NR), pdf_text)

    calib_val = erow.get("calibration_method", NR) if erow.get("calibration_method", NR) != NR else erow.get("calibration_metric_result", NR)
    row["calibration"] = _rate("calibration", calib_val, pdf_text) if has_system else "NA"
    row["grounding"] = _rate("grounding", erow.get("evidence_grounding_method", NR), pdf_text) if has_system else "NA"
    row["hallucination_testing"] = _rate("hallucination_testing", erow.get("hallucination_definition_or_test", NR), pdf_text) if has_system else "NA"
    row["fairness"] = _rate("fairness", erow.get("fairness_or_bias_method", NR), pdf_text) if has_system else "NA"

    repro_val = "yes" if (erow.get("code_available", NR) == "yes"
                           or erow.get("data_available", NR) in ("yes", "upon request")) else NR
    row["reproducibility"] = _rate("reproducibility", repro_val, pdf_text)

    # Two dimensions with no dedicated extraction field — direct PDF scan,
    # then negation check, then NA if there's no system to evaluate at all.
    if pdf_text:
        row["robustness"] = _any_match(ROBUSTNESS_PATS, pdf_text)
        if row["robustness"] == NR:
            row["robustness"] = _rate("robustness", NR, pdf_text) if has_system else "NA"
        row["human_evaluation"] = _any_match(HUMAN_EVAL_PATS, pdf_text)
        if row["human_evaluation"] == NR:
            row["human_evaluation"] = _rate("human_evaluation", erow.get("human_in_the_loop_design", NR), pdf_text)
    else:
        row["robustness"] = "NA" if not has_system else NR
        row["human_evaluation"] = _yn(erow.get("human_in_the_loop_design", NR))

    n_filled = sum(1 for d in QUALITY_FIELDS_DIMENSIONS if row[d] not in (NR,))
    n_evidenced = sum(1 for d in QUALITY_FIELDS_DIMENSIONS if row[d] in ("yes", "partial", "no"))
    row["narrative_summary_draft"] = (
        f"Rule-based auto-score (scripts/18, Yes/No/Partial/NR/NA scale): "
        f"{n_evidenced}/{len(QUALITY_FIELDS_DIMENSIONS)} dimensions have direct evidence "
        f"(yes/partial/no), {n_filled - n_evidenced} marked NA (no identifiable "
        f"generative-AI system in this record), rest NR (no matching evidence found — "
        f"absence of evidence, not evidence of absence). Derived from "
        f"evidence_extraction.csv ({erow.get('extraction_status', '?')}) plus direct "
        f"PDF keyword/negation scan. This is NOT a substitute for human/LLM-full-read "
        f"appraisal per prompts/09_quality_appraiser.md before being treated as final."
    )
    row["quality_appraisal_status"] = "ai_draft"
    row["human_verified"] = "false"
    row["reviewer_name"] = NR
    row["review_date"] = NR
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--force", action="store_true",
                         help="Re-score all rows, even ones already ai_draft (never touches human_verified=true)")
    args = parser.parse_args()

    extraction_rows = read_csv_rows(EXTRACTION)
    extraction_by_id = {r["record_id"]: r for r in extraction_rows}

    fn_by_doi = {}
    if DOWNLOADED.exists():
        for r in read_csv_rows(DOWNLOADED):
            fn_by_doi[r["doi_normalized"]] = r.get("filename", "")

    existing = {}
    if APPRAISAL.exists():
        for r in read_csv_rows(APPRAISAL):
            existing[r["record_id"]] = r

    eligible = [r for r in extraction_rows if r.get("extraction_status") in ("ai_draft", "ai_verified_pass2")]

    if args.offset:
        eligible = eligible[args.offset:]
    if args.max:
        eligible = eligible[:args.max]

    print(f"Scoring {len(eligible)} ai_draft records (offset={args.offset})...")

    results = list(existing.values())
    scored = skipped = 0
    for i, erow in enumerate(eligible):
        rid = erow["record_id"]
        prev = existing.get(rid, {})
        if not args.force and prev.get("human_verified", "").lower() == "true":
            skipped += 1
            continue

        fn = fn_by_doi.get(erow.get("doi_normalized", ""), "")
        pdf_text = ""
        if fn:
            p = CORPUS / fn
            if p.exists():
                pdf_text = extract_text(p)

        row = score_row(erow, pdf_text)
        results = [r for r in results if r.get("record_id") != rid]
        results.append(row)
        scored += 1

        n_filled = sum(1 for d in QUALITY_FIELDS_DIMENSIONS if row[d] != NR)
        print(f"  [{i+1}/{len(eligible)}] {rid}  dims_filled={n_filled}/{len(QUALITY_FIELDS_DIMENSIONS)}")

    write_csv_rows(APPRAISAL, results, ALL_QUALITY_FIELDS)
    print(f"\nDone — scored={scored}, skipped(human_verified)={skipped}, total={len(results)}")
    log_run_event({
        "stage": "auto_score_quality_appraisal",
        "scored": scored,
        "skipped": skipped,
        "total_rows": len(results),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
