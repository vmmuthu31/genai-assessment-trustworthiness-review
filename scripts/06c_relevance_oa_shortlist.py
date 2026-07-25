#!/usr/bin/env python3
"""AI-draft relevance + open-access-priority shortlist (hardened heuristics).

This is a keyword-heuristic AI-draft PRE-FILTER, NOT a substitute for the
LLM-based Screening Agent (prompts/06_title_abstract_screener.md) or for
human title/abstract screening (docs/screening_manual.md). It cuts a large,
topically-broad raw pool (thousands of records from broad discovery queries)
down to a manageable, defensibly on-topic shortlist before the full
AI-draft/human-approval screening workflow runs on it.

Every row it touches is written as an "AI draft—human decision pending"
per config/inclusion_exclusion.yaml:ai_draft_policy — nothing here sets
title_abstract_human_decision or final_included.

Relevance scoring (explicit, weighted, reproducible)
=====================================================
Each search vocabulary term (config/search_queries.yaml concept_families) is
mapped to one of four relevance AXES:
    A = multimodal / VLM / MLLM / generative AI   (weight 2.0)   (core_inclusion:
        has_generative_ai_component + has_multimodal_component)
    B = educational assessment / grading / scoring (weight 2.0)   (core_inclusion:
        directly_relevant_to_automated_educational_assessment)
    C = trustworthiness aspects                    (weight 1.0)   (core_inclusion:
        has_trustworthiness_aspect)
    D = handwritten / visual / STEM assessment      (weight 1.5)   (domain sharpening)

A record must still match >=1 term from concept_a (group A/D generative/multimodal)
AND >=1 term from concept_b (group B assessment) in the SAME concept family to be
considered on-topic at all (mirrors core_inclusion_requires_all). The relevance
score is then the sum of per-axis contributions across ALL families that match,
each contribution = axis_weight * (# distinct terms matched in that axis). This
rewards records that hit several axes / several families rather than a single
incidental keyword.

PENALTY terms (non-educational domains) deduct a fixed amount per matched term:
medical/clinical, finance, legal, climate/weather, sports, autonomous-driving,
etc. This prevents broad generative-AI or "assessment" hits from irrelevant
fields inflating the score. Penalties are recorded in the output for auditability.

Open-access logic (explicit, structured, evidence-annotated)
=============================================================
oa_best_status is derived from structured metadata with a priority order:
    gold > hybrid > green > bronze > closed > unknown
and the SOURCE of that status is recorded in oa_evidence_source:
    - OpenAlex : record.open_access_status (verified OA tier from OpenAlex API)
    - Crossref : record.crossref_license CC URL (evidence of an open license;
                 we do NOT infer a legal tier from it, recorded as "licensed")
    - Unpaywall: only when --enrich-unpaywall is given (authoritative oa_status)
    - unknown  : no OA signal available in this pipeline
A record is OA-eligible (preferred) iff oa_best_status in {gold, hybrid, green}
or (OpenAlex bronze) — i.e. any verified-open tier. Records with only a Crossref
license are treated as "licensed" (encouraged but not tier-verified).

Ranking prefers OA-eligible records via a small OA bonus S_OA added to the
relevance score. The shortlist is filled from the top-ranked on-topic records
up to --target, preferring the OA-eligible pool; if that pool is smaller than
--target, non-OA-eligible on-topic records backfill the remainder (flagged
oa_eligible=False), so the shortlist still reaches the target and stays
over-inclusive at this stage (human screening follows). Use --strict to disable
backfill (shortlist may then be smaller than --target).

Intra-shortlist de-duplication: the same work is often retrieved from both
OpenAlex and Crossref (different record_ids, same DOI). Before the OA/non-OA
split, records are collapsed by normalized DOI, keeping the representative with
the best OA status (then highest adjusted score, then the OpenAlex copy). This
is a lightweight within-shortlist de-dup; Phase-2 scripts/04 remains the
canonical de-duplication stage across the whole master corpus.

Usage:
    python scripts/06c_relevance_oa_shortlist.py --target 400
    python scripts/06c_relevance_oa_shortlist.py --target 400 --strict
    python scripts/06c_relevance_oa_shortlist.py --target 400 --enrich-unpaywall
        --unpaywall-email sudhanm@srmist.edu.in
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUTPUTS_DIR,
    load_yaml,
    log_run_event,
    read_csv_rows,
    write_csv_rows,
    master_records_fieldnames,
)

SHORTLIST_FIELDS = [
    "record_id", "source_database", "doi_normalized", "doi_url", "title",
    "publication_year", "journal_name", "document_type", "open_access_status",
    "oa_best_status", "oa_evidence_source", "oa_eligible",
    "relevance_score", "s_oa", "adjusted_score",
    "matched_axes", "matched_concept_a", "matched_concept_b", "matched_concept_c",
    "matched_penalties", "oa_backfilled", "dup_sources", "rationale",
]

# ---------------------------------------------------------------------------
# Relevance axis weights and family-term -> axis classification
# ---------------------------------------------------------------------------
AXIS_WEIGHTS = {"A": 2.0, "B": 2.0, "C": 1.0, "D": 1.5}
AXIS_LABELS = {
    "A": "multimodal_generative_ai",
    "B": "educational_assessment",
    "C": "trustworthiness",
    "D": "handwritten_visual_stem",
}
# Concept-group default axis. concept_a -> generative/multimodal, concept_b ->
# assessment, concept_c -> trustworthiness. Handwriting/OCR/visual/STEM terms
# are reclassified to D (see TERM_OVERRIDES below).
GROUP_DEFAULT_AXIS = {"concept_a": "A", "concept_b": "B", "concept_c": "C"}
TERM_OVERRIDES = {
    "handwritten": "D", "handwriting": "D", "answer sheet": "D",
    "exam script": "D", "examination script": "D", "OCR": "D",
    "document understanding": "A", "diagram": "D", "graph": "D",
    "mathematics": "D", "STEM": "D", "visual answer": "D",
}

# Non-educational / off-topic domains; matching terms PENALIZE the score.
PENALTY_PATTERNS = [
    (re.compile(r"\b(clinical|medical|biomedical|radiolog|patholog|patient|"
                r"disease|diagnos|healthcare|ehr|electronic health)\b", re.IGNORECASE), "medical/clinical"),
    (re.compile(r"\b(financ|stock|trading|bank|credit risk|fraud detection)\b", re.IGNORECASE), "finance"),
    (re.compile(r"\b(legal|law|judicial|court|contract review)\b", re.IGNORECASE), "legal"),
    (re.compile(r"\b(climate|weather|forecast|remote sensing)\b", re.IGNORECASE), "climate/weather"),
    (re.compile(r"\b(sports|athlet|soccer|football match)\b", re.IGNORECASE), "sports"),
    (re.compile(r"\b(autonomous driving|self-driving|traffic)\b", re.IGNORECASE), "autonomous-driving"),
]

# ---------------------------------------------------------------------------
# Open-access tier priority
# ---------------------------------------------------------------------------
OA_PRIORITY = {"gold": 0, "hybrid": 1, "green": 2, "bronze": 3, "closed": 4, "unknown": 5}
OA_ELIGIBLE_TIERS = {"gold", "hybrid", "green", "bronze"}  # verified-open tiers
OA_SCORE_FULL = 1.0  # S_OA for the best tier
W_OA = 1.0  # S_OA weight in adjusted score

# Crossref license URL substrings that indicate an open license.
_CC_LICENSE_RE = re.compile(r"creativecommons\.org/licenses", re.IGNORECASE)
_OPEN_LICENSE_RE = re.compile(r"/(by|by-sa|by-nc|by-nd|0\.html|publicdomain|mit|apache|bsd)", re.IGNORECASE)


def _word_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.strip())
    if " " in term:
        return re.compile(escaped, re.IGNORECASE)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def build_family_patterns(concept_families: dict) -> dict:
    """{family_name: {concept_a: [(term, pattern, axis), ...], ...}}"""
    out = {}
    for fam_name, fam in concept_families.items():
        out[fam_name] = {}
        for key in ("concept_a", "concept_b", "concept_c"):
            default_axis = GROUP_DEFAULT_AXIS[key]
            entries = []
            for t in (fam.get(key) or []):
                axis = TERM_OVERRIDES.get(t, default_axis)
                entries.append((t, _word_pattern(t), axis))
            out[fam_name][key] = entries
    return out


def _axis_label(axis: str) -> str:
    return AXIS_LABELS[axis]


def score_record(text: str, family_patterns: dict) -> dict:
    """Score a record's title+abstract text across all concept families.

    Returns relevance_score plus matched terms per axis and per concept group,
    and any matched penalty domains.
    """
    axes_hits: dict[str, set[str]] = {"A": set(), "B": set(), "C": set(), "D": set()}
    grp_hits: dict[str, set[str]] = {"a": set(), "b": set(), "c": set()}
    # Track which (family) had a simultaneous a+b match for on-topic gating.
    family_a_b: set[str] = set()
    per_family_a: dict[str, set[str]] = {}
    per_family_b: dict[str, set[str]] = {}

    for fam_name, groups in family_patterns.items():
        a_hits = {t for t, p, _ in groups.get("concept_a", []) if p.search(text)}
        b_hits = {t for t, p, _ in groups.get("concept_b", []) if p.search(text)}
        c_hits = {t for t, p, _ in groups.get("concept_c", []) if p.search(text)}
        per_family_a[fam_name] = a_hits
        per_family_b[fam_name] = b_hits
        if a_hits and b_hits:
            family_a_b.add(fam_name)
        for t in a_hits:
            ax = next(ax for (tt, _, ax) in groups["concept_a"] if tt == t)
            axes_hits[ax].add(t)
            grp_hits["a"].add(t)
        for t in b_hits:
            ax = next(ax for (tt, _, ax) in groups["concept_b"] if tt == t)
            axes_hits[ax].add(t)
            grp_hits["b"].add(t)
        for t in c_hits:
            ax = next(ax for (tt, _, ax) in groups["concept_c"] if tt == t)
            axes_hits[ax].add(t)
            grp_hits["c"].add(t)

    # On-topic gate: must have >=1 concept_a AND >=1 concept_b in the SAME family.
    if not family_a_b:
        return {
            "relevance_score": 0.0, "on_topic": False, "axes": axes_hits,
            "grp": grp_hits, "penalties": [],
        }

    relevance = sum(AXIS_WEIGHTS[ax] * len(axes_hits[ax]) for ax in axes_hits)

    penalties = []
    for pat, label in PENALTY_PATTERNS:
        if pat.search(text):
            penalties.append(label)
            relevance -= 3.0  # fixed penalty per off-topic domain hit

    relevance = max(relevance, 0.0)
    return {
        "relevance_score": round(relevance, 3),
        "on_topic": True,
        "axes": axes_hits,
        "grp": grp_hits,
        "penalties": penalties,
    }


def derive_oa_best_status(record: dict, enrich_cache: dict | None = None,
                          unpaywall_email: str | None = None) -> tuple[str, str]:
    """Return (oa_best_status, evidence_source) for a record.

    Priority: OpenAlex verified tier > Unpaywall (if enriched) > Crossref
    license signal > unknown.
    """
    oa_status = (record.get("open_access_status") or "").strip().lower()
    if record.get("source_database") == "OpenAlex" and oa_status:
        return oa_status, "OpenAlex"

    doi = (record.get("doi_normalized") or "").strip()
    if enrich_cache is not None and doi in enrich_cache:
        st = enrich_cache[doi]
        if st in OA_PRIORITY:
            return st, "Unpaywall"

    if unpaywall_email and doi:
        st = _query_unpaywall(doi, unpaywall_email, enrich_cache)
        if st in OA_PRIORITY:
            return st, "Unpaywall"

    license_field = (record.get("crossref_license") or "").strip()
    if license_field:
        return "licensed", "Crossref"

    return "unknown", "unknown"


def _query_unpaywall(doi: str, email: str, cache: dict | None) -> str:
    import urllib.request

    if cache is None:
        cache = {}
    url = f"https://api.unpaywall.org/v2/{doi}?email={urllib.parse.quote(email)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        cache[doi] = "unknown"
        return "unknown"
    oa_status = (data.get("oa_status") or "").strip().lower()
    best = data.get("best_oa_location") or {}
    if oa_status in OA_PRIORITY:
        cache[doi] = oa_status
    elif best.get("version"):
        cache[doi] = "green"
    else:
        cache[doi] = "unknown"
    return cache[doi]


def s_oa_for(tier: str) -> float:
    if tier not in OA_PRIORITY:
        return 0.0
    return round(OA_SCORE_FULL * (1.0 - OA_PRIORITY[tier] / 5.0), 3)


def dedup_by_doi(items: list[dict], prefer_openalex: bool = True) -> tuple[list[dict], int]:
    """Collapse records sharing a normalized DOI to a single best representative.

    Phase-2 (scripts/04) is the canonical de-duplication stage, but the same
    work can appear from both OpenAlex and Crossref (different record_ids, same
    DOI). To keep the shortlist de-duplicated we collapse within the scored pool
    here: for each DOI group, keep the representative with the best OA status
    (OpenAlex verified tier > Unpaywall > Crossref "licensed" > unknown), then
    the highest adjusted score. `prefer_openalex` breaks OA-tier ties toward the
    OpenAlex copy (verified metadata). Records without a DOI are kept as-is.
    Returns (deduped_items, n_collapsed).
    """
    by_doi: dict[str, list[dict]] = {}
    no_doi: list[dict] = []
    for it in items:
        doi = (it["r"].get("doi_normalized") or "").strip()
        if doi:
            by_doi.setdefault(doi, []).append(it)
        else:
            no_doi.append(it)

    kept: list[dict] = []
    collapsed = 0
    for group in by_doi.values():
        if len(group) == 1:
            kept.append(group[0])
            continue
        collapsed += len(group) - 1
        best = sorted(
            group,
            key=lambda i: (
                OA_PRIORITY.get(i["tier"], 99),
                -i["adjusted"],
                0 if i["r"].get("source_database") == "OpenAlex" else 1,
            ),
        )[0]
        best = dict(best)
        best["dup_sources"] = "; ".join(
            sorted({i["r"].get("source_database", "") for i in group})
        )
        kept.append(best)
    kept.extend(no_doi)
    return kept, collapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(OUTPUTS_DIR / "csv" / "master_records.csv"))
    parser.add_argument("--output", default=str(OUTPUTS_DIR / "csv" / "relevance_oa_shortlist.csv"))
    parser.add_argument("--target", type=int, default=400,
                        help="Target shortlist size; fewer kept if fewer clear the on-topic bar.")
    parser.add_argument("--target-min", type=int, default=350,
                        help="Lower bound of the target range, for reporting only.")
    parser.add_argument("--s-min", type=float, default=4.0,
                        help="Minimum relevance score to be considered shortlistable.")
    parser.add_argument("--strict", action="store_true",
                        help="Do not backfill non-OA-eligible records; shortlist may be < target.")
    parser.add_argument("--enrich-unpaywall", action="store_true",
                        help="Query Unpaywall (by DOI) to obtain authoritative OA status for records "
                             "lacking OpenAlex status. Requires network + --unpaywall-email.")
    parser.add_argument("--unpaywall-email", default="",
                        help="Email for the Unpaywall polite pool (required with --enrich-unpaywall).")
    parser.add_argument("--unpaywall-cache", default=str(OUTPUTS_DIR / "cache" / "unpaywall_oa_cache.json"),
                        help="Path to cache Unpaywall responses across runs.")
    parser.add_argument("--write-ai-decisions", action="store_true",
                        help="Also write title_abstract_ai_decision/reason/rationale AI-draft columns back to master_records.csv.")
    args = parser.parse_args()

    if args.enrich_unpaywall and not args.unpaywall_email:
        print("ERROR: --enrich-unpaywall requires --unpaywall-email.")
        return 2

    cfg = load_yaml("search_queries.yaml")
    family_patterns = build_family_patterns(cfg["concept_families"])

    enrich_cache: dict | None = None
    if args.enrich_unpaywall:
        cache_path = Path(args.unpaywall_cache)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            try:
                enrich_cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                enrich_cache = {}
        else:
            enrich_cache = {}

    rows = read_csv_rows(Path(args.input))
    if not rows:
        print(f"No rows in {args.input}.")
        return 0

    # The shortlist is a PRE-FILTER applied BEFORE deduplication (Phase 2,
    # scripts/04). A fresh consolidation leaves new rows with
    # deduplication_status="pending" (not yet de-duplicated). Such rows are
    # eligible here: the on-topic scoring is independent of dedup, and any
    # duplicates will be collapsed downstream. Only rows already marked
    # "duplicate" (or "needs_manual_review") are excluded.
    unique_rows = [
        r for r in rows
        if (r.get("deduplication_status") or "pending") not in ("duplicate",)
    ]
    n_pending = sum(1 for r in unique_rows if r.get("deduplication_status") != "unique")
    print(f"Total records: {len(rows)}  |  shortlist-eligible (unique or pre-dedup): {len(unique_rows)} "
          f"({n_pending} not yet de-duplicated)")

    scored = []
    for r in unique_rows:
        text = f"{r.get('title', '')} . {r.get('abstract', '')}"
        res = score_record(text, family_patterns)
        if not res["on_topic"] or res["relevance_score"] < args.s_min:
            continue
        tier, source = derive_oa_best_status(
            r,
            enrich_cache=enrich_cache if args.enrich_unpaywall else None,
            unpaywall_email=args.unpaywall_email if args.enrich_unpaywall else None,
        )
        eligible = tier in OA_ELIGIBLE_TIERS or tier == "licensed"
        s_oa = s_oa_for(tier) if tier in OA_PRIORITY else (0.6 if tier == "licensed" else 0.0)
        adjusted = round(res["relevance_score"] + W_OA * s_oa, 3)
        scored.append({
            "r": r, "res": res, "tier": tier, "source": source,
            "eligible": eligible, "s_oa": round(s_oa, 3), "adjusted": adjusted,
        })

    print(f"On-topic (>=1 gen/multimodal AND >=1 assessment term, score>={args.s_min}): {len(scored)}")
    if args.enrich_unpaywall and enrich_cache is not None:
        Path(args.unpaywall_cache).write_text(json.dumps(enrich_cache), encoding="utf-8")

    def sort_key(item):
        return -item["adjusted"]

    scored.sort(key=sort_key)

    # De-duplicate within the scored pool (Phase-2 scripts/04 is canonical, but
    # OpenAlex+Crossref copies of the same work should not both appear here).
    scored, n_collapsed = dedup_by_doi(scored)
    print(f"Intra-shortlist de-duplicated by DOI: collapsed {n_collapsed} duplicate record(s) "
          f"(kept best-OA representative per DOI).")

    oa_pool = [i for i in scored if i["eligible"]]
    non_oa_pool = [i for i in scored if not i["eligible"]]

    shortlist = oa_pool[: args.target]
    backfilled = []
    if len(shortlist) < args.target and not args.strict:
        need = args.target - len(shortlist)
        backfilled = non_oa_pool[:need]
        shortlist += backfilled
    # strict mode: cap at target, do NOT backfill non-OA-eligible records

    tier_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    out_rows = []
    for item in shortlist:
        r = item["r"]
        res = item["res"]
        tier = item["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        source_counts[item["source"]] = source_counts.get(item["source"], 0) + 1
        axes = [AXIS_LABELS[a] for a in ("A", "B", "C", "D") if res["axes"][a]]
        rationale = (
            f"axes={axes}; family_a+concept_b match; "
            f"concept_a={sorted(res['grp']['a'])}; concept_b={sorted(res['grp']['b'])}; "
            f"concept_c(trust)={sorted(res['grp']['c']) or 'none'}"
            + (f"; penalties={res['penalties']}" if res["penalties"] else "")
        )
        out_rows.append({
            "record_id": r.get("record_id", ""),
            "source_database": r.get("source_database", ""),
            "doi_normalized": r.get("doi_normalized", ""),
            "doi_url": r.get("doi_url", ""),
            "title": r.get("title", ""),
            "publication_year": r.get("publication_year", ""),
            "journal_name": r.get("journal_name", ""),
            "document_type": r.get("document_type", ""),
            "open_access_status": r.get("open_access_status", ""),
            "oa_best_status": tier,
            "oa_evidence_source": item["source"],
            "oa_eligible": "True" if item["eligible"] else "False",
            "relevance_score": res["relevance_score"],
            "s_oa": item["s_oa"],
            "adjusted_score": item["adjusted"],
            "matched_axes": "; ".join(axes),
            "matched_concept_a": "; ".join(sorted(res["grp"]["a"])),
            "matched_concept_b": "; ".join(sorted(res["grp"]["b"])),
            "matched_concept_c": "; ".join(sorted(res["grp"]["c"])),
            "matched_penalties": "; ".join(res["penalties"]),
            "oa_backfilled": "True" if item in backfilled else "False",
            "dup_sources": item.get("dup_sources", ""),
            "rationale": rationale,
        })

    write_csv_rows(Path(args.output), out_rows, SHORTLIST_FIELDS)

    print(f"\nShortlist written: {len(out_rows)} records -> {args.output}")
    print(f"Target range was {args.target_min}-{args.target}.")
    print("OA best-status breakdown (oa_best_status):")
    for tier in ("gold", "hybrid", "green", "bronze", "licensed", "closed", "unknown"):
        if tier in tier_counts:
            print(f"    {tier}: {tier_counts[tier]}")
    print("OA evidence source breakdown:")
    for src, n in sorted(source_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {src}: {n}")
    print(f"Backfilled (non-OA-eligible, over-inclusive): {len(backfilled)}")
    dropped_off_topic = len(unique_rows) - len(scored)
    dropped_over_target = max(0, len(scored) - len(shortlist))
    print(f"\nDropped as off-topic / below s_min: {dropped_off_topic}")
    print(f"Dropped for exceeding target size (on-topic but lower-ranked): {dropped_over_target}")

    if args.write_ai_decisions:
        shortlisted_ids = {o["record_id"] for o in out_rows}
        scored_ids = {i["r"]["record_id"] for i in scored}
        for r in unique_rows:
            rid = r.get("record_id")
            if rid in shortlisted_ids:
                r["title_abstract_ai_decision"] = "include"
                r["title_abstract_ai_reason"] = ""
                r["title_abstract_ai_rationale"] = (
                    "AI draft (keyword relevance + OA-priority pre-filter, "
                    "scripts/06c_relevance_oa_shortlist.py) — on-topic and within "
                    "OA-priority shortlist target; human decision pending."
                )
            elif rid in scored_ids:
                r["title_abstract_ai_decision"] = "unclear"
                r["title_abstract_ai_reason"] = "E15"
                r["title_abstract_ai_rationale"] = (
                    "AI draft — matched core topic terms but ranked below the shortlist "
                    "target cutoff; not excluded on relevance grounds, deprioritized by "
                    "OA-tier/score ranking. Human decision pending."
                )
            else:
                r["title_abstract_ai_decision"] = "exclude"
                r["title_abstract_ai_reason"] = "E09"
                r["title_abstract_ai_rationale"] = (
                    "AI draft (keyword relevance pre-filter) — no title/abstract match for both a "
                    "generative/multimodal term and an assessment/scoring term from any concept "
                    "family; likely off-topic. Human decision pending — keyword matching can miss "
                    "genuinely relevant papers using different terminology; spot-check before final exclusion."
                )
        write_csv_rows(Path(args.input), rows, master_records_fieldnames())
        print(f"\nWrote AI-draft title_abstract_ai_decision/reason/rationale back to {args.input}")

    log_run_event({
        "stage": "relevance_oa_shortlist",
        "input_unique_records": len(unique_rows),
        "on_topic_records": len(scored),
        "shortlist_size": len(out_rows),
        "target_range": [args.target_min, args.target],
        "oa_best_status_breakdown": tier_counts,
        "oa_evidence_source_breakdown": source_counts,
        "backfilled": len(backfilled),
        "strict": args.strict,
        "unpaywall_enriched": bool(args.enrich_unpaywall),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
