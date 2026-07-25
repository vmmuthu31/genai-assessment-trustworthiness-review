# Search Strategy

Companion to `docs/protocol.md` §5. Exact, executable query text lives in
`config/search_queries.yaml`; this document explains the *why* behind the
structure so the strategy can be defended in the manuscript's Methods
section and reproduced by an independent reviewer.

## 1. Five concept families

The eligibility criteria (multimodal AND generative AND assessment AND
trustworthiness) are too conjunctive to search as one query without
losing recall — a single query ANDing all four concepts returns almost
nothing on current academic search engines, because indexing and
abstracting practices are inconsistent across venues. Instead, the
protocol decomposes the space into **five overlapping concept families**,
each a slightly different combination, and the union of all five results
is deduplicated downstream:

- **F1 — Core topic:** multimodal/generative-AI terms × general automated
  assessment/grading terms. Casts the widest net over the primary topic.
- **F2 — Handwriting, OCR, and answer sheets:** anchors on the
  handwritten/scanned-document angle, which is central to EvalBot's use
  case but may not always co-occur with "multimodal" as a keyword.
- **F3 — Trustworthy assessment AI:** anchors on the trust vocabulary
  (hallucination, calibration, fairness, etc.) crossed with assessment
  terms, catching papers that frame themselves primarily as trust/safety
  work but happen to evaluate on an assessment task.
- **F4 — Rubric grounding and teacher oversight:** anchors on
  evidence-grounding and human-in-the-loop vocabulary, directly aligned
  with EvalBot's rubric-grounded scoring and Paper 4's deferral policy.
  This family is what most differentiates this review from generic
  "GenAI in education" surveys.
- **F5 — Visual and STEM answers:** anchors on diagram/graph/math answer
  content, which is under-served by keyword sets built around "short
  answer" or "essay" and is otherwise likely to be missed.

Each family is defined in `config/search_queries.yaml` as concept groups
(`concept_a`, `concept_b`, …) combined with AND across groups and OR
within a group — the same boolean logic realized differently per
database's syntax (API `search` params for OpenAlex, `query.bibliographic`
+ field queries for Crossref, `TITLE-ABS-KEY(...)` for Scopus, `TS=(...)`
for Web of Science, field-tag/advanced-search equivalents for ERIC, IEEE
Xplore, ACM DL, and PubMed).

## 2. Why these information sources

- **OpenAlex** — free, comprehensive, API-queryable, good abstract/OA
  metadata; primary source for programmatic, fully reproducible discovery.
- **Crossref** — authoritative DOI registry; cross-checks OpenAlex
  coverage and catches records OpenAlex may index differently or later.
- **Scopus** — the authoritative source for journal quartile
  verification in this protocol (`config/inclusion_exclusion.yaml`); also
  searched directly since its indexing differs from OpenAlex/Crossref.
- **Web of Science** — independent major index with different journal
  coverage; reduces single-database bias.
- **ERIC** — the primary education-research-specific index; likely to
  surface education-journal venues that general science indexes rank
  differently or miss entirely.
- **IEEE Xplore, ACM Digital Library** — primary venues for CS/AI
  technical work, including many of the multimodal/generative-model
  papers most relevant to RQ2; also the source for the conference
  appendix (kept separate from the Q1/Q2 core).
- **PubMed** — secondary/opportunistic; included because some
  assessment-adjacent multimodal document-AI work appears in health-
  professions education journals indexed there, but is not expected to
  contribute heavily.

## 3. API vs. manual-export queries

OpenAlex and Crossref are queried programmatically
(`scripts/01_fetch_openalex.py`, `scripts/02_fetch_crossref.py`) so the
exact request parameters, pagination, and result counts are fully
reproducible and logged automatically. The remaining six sources do not
offer API access appropriate for this protocol (Scopus API access is
optional/institutional and not required — see `config/protocol.yaml:
venue_quality_requirement.source_priority`, which treats a *manual* Scopus
Sources export as the primary venue-truth source regardless); the
researcher runs the equivalent advanced-search query directly in each
platform's UI and exports results (RIS/CSV/BibTeX) into
`data/raw/manual_database_exports/`, imported by
`scripts/03_import_manual_exports.py`. Each manual query's exact string is
still recorded in `config/search_queries.yaml` so the *search strategy*
remains fully reproducible even where retrieval itself is manual.

## 4. Date range rationale: 2025-01-01 to 2026-12-31

The review targets *current-generation* multimodal generative AI —
systems built on the class of VLMs/MLLMs that reached broad practical
capability for document-grounded, evidence-citing generation only from
roughly 2024 onward. Restricting to 2025–2026 publication dates:

- Focuses the review on architectures and trust techniques that are
  actually deployable candidates for EvalBot today, rather than diluting
  the taxonomy with earlier-generation, largely non-generative OCR+rules
  or classical-ML AES systems.
- Keeps the corpus tractable for a single-researcher PhD review within
  the strict Q1/Q2 + full extraction + quality appraisal workload.
- Is explicitly revisitable: `docs/protocol.md` §13 Fallback Amendment
  Protocol allows extending the start date backward if the strict window
  yields materially fewer than the target 100 core studies.

## 5. Discovery is broad; venue filtering is a separate, later step

Per `config/search_queries.yaml` and `docs/protocol.md` §4, no Q1/Q2
filter is applied during Phase 1 discovery. All five families are run
without venue restriction, retrieving broadly; deduplication
(`scripts/04_normalize_deduplicate.py`) and venue verification
(`scripts/05_import_venue_quality_sources.py`,
`scripts/06_match_venues_q1_q2.py`) happen afterward, against
authoritative sources. This avoids the failure mode of a search engine's
own (often outdated or incomplete) journal-quality metadata silently
narrowing the corpus before the researcher can verify it independently.

## 6. Logging discipline

Every query execution — API or manual — is logged to
`outputs/csv/prisma_log.csv` with: `query_id` (FK into
`config/search_queries.yaml`), `database`, `query_text`, `filters`,
`retrieval_date`, `result_count`, and `export_path`. This is what makes
the PRISMA flow diagram (`scripts/10_generate_prisma_counts.py`)
arithmetically traceable back to individual searches, and what an
independent reviewer would need to re-run the search exactly.

## 7. Conference-track queries

A parallel `conference_appendix_queries` block in
`config/search_queries.yaml` reuses the same five-family boolean
structure but restricts `Content Type` / `Document Type` to
conference/proceedings. Results are written to
`outputs/conference_appendix_candidates/` and are never merged into the
Q1/Q2 journal core without explicit researcher approval (`docs/protocol.md`
§14).
