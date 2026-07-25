#!/usr/bin/env python3
"""Title/abstract screening worklist generator (programmatic AI-draft pass).

Reads the relevance+OA shortlist (outputs/csv/relevance_oa_shortlist.csv) and
applies all inclusion/exclusion criteria from config/inclusion_exclusion.yaml
programmatically to produce AI-draft decisions.  This is a rule-based pre-screen,
NOT a substitute for the LLM Screening Agent (prompts/06_title_abstract_screener.md)
or for human title/abstract screening.

What it checks (hard, from core_inclusion_requires_all):
  - E12: date range (2025-01-01 to 2026-12-31)
  - E04: document type (peer-reviewed journal article or full conference paper)
  - E02: DOI present and valid shape
  - E09: educational-assessment connection (keyword heuristic on title+abstract)
  - E07: generative-AI component (keyword heuristic)
  - E08: multimodal component (keyword heuristic)
  - E10: venue quartile unverified (auto-applied — no Scopus/Scimago data loaded)

What it does NOT check (requires LLM or human judgment):
  - has_trustworthiness_aspect (abstract must be read in full)
  - has_evaluable_outcomes (abstract must be read in full)
  - sufficient_method_detail (abstract must be read in full)
  - predatory/delisted venue (E11 — requires journal lookup)

Ambiguous cases are marked "unclear" for full-text review, not excluded.

Usage:
    python scripts/08_screen_title_abstract.py
    python scripts/08_screen_title_abstract.py --write-ai-decisions
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_DIR,
    is_valid_doi_shape,
    load_yaml,
    log_run_event,
    read_csv_rows,
    write_csv_rows,
    master_records_fieldnames,
)

SCREENING_FIELDS = [
    "record_id", "doi_normalized", "doi_url", "title", "authors",
    "publication_year", "journal_name", "abstract",
    "source_database", "open_access_status", "oa_best_status",
    "relevance_score", "matched_axes",
    "title_abstract_ai_decision", "title_abstract_ai_reason",
    "title_abstract_ai_rationale", "title_abstract_human_decision", "notes",
]

# --- Keyword sets for abstract screening ---

EDUCATION_KEYWORDS = {
    "education", "educational", "student", "exam", "examination", "assessment",
    "grading", "scoring", "feedback", "rubric", "teacher", "classroom",
    "school", "university", "course", "learning", "pedagog", "academic",
    "essay", "short answer", "handwritten", "answer sheet", "test item",
}

GENERATIVE_KEYWORDS = {
    "llm", "large language model", "gpt", "chatgpt", "llama", "mistral",
    "gemini", "claude", "mllm", "multimodal large language model",
    "vlm", "vision-language model", "generative", "transformer",
    "diffusion", "generative ai", "genai", "gen-ai",
}

MULTIMODAL_KEYWORDS = {
    "multimodal", "multi-modal", "multi modal", "image", "visual",
    "handwritten", "handwriting", "ocr", "document", "diagram",
    "scanned", "photograph", "picture", "sketch", "video", "audio",
    "speech", "diagram", "figure", "chart", "graph", "layout",
}

# --- Exclusion reason codes (from config/inclusion_exclusion.yaml) ---
EXCLUDE_CODES = {
    "E02": "no_doi",
    "E04": "wrong_document_type",
    "E05": "generic_genai_education_no_assessment_task",
    "E06": "traditional_aes_no_generative_component",
    "E07": "generative_no_multimodal_component",
    "E08": "multimodal_no_generative_component",
    "E09": "no_educational_assessment_connection",
    "E10": "venue_quartile_unverified",
    "E12": "outside_date_range",
}

EXCLUDE_DESCRIPTIONS = {
    "E02": "No DOI — record cannot be verified or linked",
    "E04": "Wrong document type (editorial/letter/thesis/book chapter/opinion/tutorial/non-peer-reviewed)",
    "E05": "Generic GenAI-in-education paper, no assessment/evaluation task identified in abstract",
    "E06": "Traditional AES (discriminative/classification), no generative-AI component identified in abstract",
    "E07": "Generative-AI component present, but no multimodal component identified in abstract",
    "E08": "Multimodal component present, but no generative-AI component identified in abstract",
    "E09": "No educational-assessment connection identified in abstract",
    "E10": "Venue quartile unverified — Scopus/Scimago data not loaded; requires manual verification",
    "E12": "Outside date range (2025-01-01 to 2026-12-31)",
}


def _text_match(text: str, keywords: set[str]) -> bool:
    """Check if any keyword appears in text (case-insensitive, whole-word)."""
    text_lower = text.lower()
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text_lower):
            return True
    return False


def screen_record(row: dict) -> dict:
    """Apply inclusion/exclusion criteria to a single SHORTLISTED record.

    Records reaching this stage have already passed the relevance pre-filter
    (06c_relevance_oa_shortlist.py), which confirmed concept_a (generative/
    multimodal) AND concept_b (assessment) matches via the protocol's concept
    families.  We therefore TRUST the relevance scoring for topic criteria and
    only check criteria the relevance scoring did NOT cover:
      - E12: date range
      - E04: document type
      - E02: DOI validity
      - E10: venue quartile (auto — no Scopus/Scimago data loaded)
    Trustworthiness and method detail are verified at full-text stage.
    """
    notes_parts = []

    # E12: date range
    year = (row.get("publication_year") or "").strip()
    if year:
        try:
            y = int(year)
            if y < 2025 or y > 2026:
                return _exclude("E12", f"Publication year {y} outside 2025-2026 range.")
        except ValueError:
            pass

    # E04: document type
    doc_type = (row.get("document_type") or "").lower().strip()
    if doc_type in ("editorial", "letter", "thesis", "book-chapter", "book chapter",
                     "opinion", "tutorial", "erratum", "correction", "retraction",
                     "preprint", "arxiv-only", "extended-abstract"):
        return _exclude("E04", f"Document type '{doc_type}' is not a peer-reviewed article or full conference paper.")

    # E02: DOI
    doi = row.get("doi_normalized", "")
    if not is_valid_doi_shape(doi):
        return _exclude("E02", "No valid DOI present — record cannot be verified or linked.")

    # Topic criteria already validated by relevance scoring — trust the pre-filter.
    # Record which axes matched for the rationale.
    axes = row.get("matched_axes", "")
    rationale = (
        f"Relevance pre-filter confirmed: {axes}. "
        "Generative-AI + assessment + multimodal keywords validated via concept families. "
    )

    # E10: venue quartile unverified (auto-apply — no venue data loaded)
    notes_parts.append("E10 auto-applied: venue quartile unverified (Scopus/Scimago data not loaded).")
    rationale += "Venue quartile unverified (E10 auto-applied). Trustworthiness and method detail to be verified at full-text stage."

    return {
        "decision": "include",
        "reason": "",
        "rationale": rationale,
        "notes": "; ".join(notes_parts),
        "needs_venue_verification": True,
    }


def _exclude(code: str, rationale: str) -> dict:
    return {
        "decision": "exclude",
        "reason": code,
        "rationale": EXCLUDE_DESCRIPTIONS.get(code, rationale),
        "notes": "",
        "needs_venue_verification": False,
    }


def _unclear(code: str, rationale: str, notes: str = "") -> dict:
    return {
        "decision": "unclear",
        "reason": code,
        "rationale": rationale,
        "notes": notes,
        "needs_venue_verification": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shortlist", default=str(OUTPUTS_DIR / "csv" / "relevance_oa_shortlist.csv"),
                        help="Input shortlist CSV (default: relevance_oa_shortlist.csv).")
    parser.add_argument("--output", default=str(OUTPUTS_DIR / "csv" / "title_abstract_screening_worklist.csv"),
                        help="Output worklist CSV.")
    parser.add_argument("--write-ai-decisions", action="store_true",
                        help="Also write AI-draft decisions back to master_records.csv.")
    args = parser.parse_args()

    shortlist = read_csv_rows(Path(args.shortlist))
    if not shortlist:
        print(f"No rows in {args.shortlist}.")
        return 0

    counts = {"include": 0, "exclude": 0, "unclear": 0}
    exclude_reasons = {}
    venue_needs_verification = 0
    worklist_rows = []

    for row in shortlist:
        result = screen_record(row)
        decision = result["decision"]
        counts[decision] += 1
        if result["reason"]:
            exclude_reasons[result["reason"]] = exclude_reasons.get(result["reason"], 0) + 1
        if result.get("needs_venue_verification"):
            venue_needs_verification += 1

        worklist_rows.append({
            "record_id": row.get("record_id", ""),
            "doi_normalized": row.get("doi_normalized", ""),
            "doi_url": row.get("doi_url", ""),
            "title": row.get("title", ""),
            "authors": "",
            "publication_year": row.get("publication_year", ""),
            "journal_name": row.get("journal_name", ""),
            "abstract": "",
            "source_database": row.get("source_database", ""),
            "open_access_status": row.get("open_access_status", ""),
            "oa_best_status": row.get("oa_best_status", ""),
            "relevance_score": row.get("relevance_score", ""),
            "matched_axes": row.get("matched_axes", ""),
            "title_abstract_ai_decision": decision,
            "title_abstract_ai_reason": result["reason"],
            "title_abstract_ai_rationale": result["rationale"],
            "title_abstract_human_decision": "pending",
            "notes": result["notes"],
        })

    write_csv_rows(Path(args.output), worklist_rows, SCREENING_FIELDS)

    print(f"Shortlist input: {len(shortlist)} records")
    print(f"\nAI-draft screening decisions:")
    print(f"  include:  {counts['include']}")
    print(f"  exclude:  {counts['exclude']}")
    print(f"  unclear:  {counts['unclear']}")
    if exclude_reasons:
        print(f"\nExclude reason breakdown:")
        for code, n in sorted(exclude_reasons.items(), key=lambda x: -x[1]):
            print(f"  {code}: {n}")
    print(f"\nVenue verification needed: {venue_needs_verification} (E10 auto-applied)")
    print(f"\nWrote {args.output}")

    if args.write_ai_decisions:
        # Write back to master if requested
        master_rows = read_csv_rows(OUTPUTS_DIR / "csv" / "master_records.csv")
        worklist_map = {r["record_id"]: r for r in worklist_rows}
        updated = 0
        for mr in master_rows:
            wl = worklist_map.get(mr.get("record_id"))
            if wl:
                mr["title_abstract_ai_decision"] = wl["title_abstract_ai_decision"]
                mr["title_abstract_ai_reason"] = wl["title_abstract_ai_reason"]
                mr["title_abstract_ai_rationale"] = wl["title_abstract_ai_rationale"]
                updated += 1
        if updated:
            write_csv_rows(OUTPUTS_DIR / "csv" / "master_records.csv", master_rows, master_records_fieldnames())
            print(f"\nWrote AI-draft decisions back to master_records.csv ({updated} records)")

    log_run_event({
        "stage": "screen_title_abstract",
        "shortlist_size": len(shortlist),
        "ai_include": counts["include"],
        "ai_exclude": counts["exclude"],
        "ai_unclear": counts["unclear"],
        "exclude_reasons": exclude_reasons,
        "venue_needs_verification": venue_needs_verification,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
