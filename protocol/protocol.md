# Protocol: Trustworthy Multimodal Generative AI for Automated Educational Assessment — A PRISMA 2020 Systematic Review

**Protocol ID:** evalbot-jair-prisma-2026
**Version:** 0.1.0-draft
**Status:** Phase 0 (build only — no records retrieved)
**Machine-readable source of truth:** `config/protocol.yaml` (this document is its narrative counterpart; if the two ever disagree, `config/protocol.yaml` governs script behavior and must be corrected to match any protocol amendment approved here)
**Target journal:** Journal of Artificial Intelligence Research (JAIR)
**Registration:** Not yet registered (e.g., OSF/PROSPERO) — registration is a Phase 0 exit decision left to the researcher; see Supervisor Decision Checklist.

## 1. Background and rationale

Generative multimodal AI — vision-language models (VLMs), multimodal large
language models (MLLMs), and generative document-understanding pipelines —
is increasingly proposed for automated educational assessment: grading
handwritten short answers, interpreting diagrams and STEM work, and
producing rubric-grounded feedback. Unlike earlier automated essay scoring
(AES) systems, these pipelines ingest heterogeneous evidence (answer
images, OCR text, question papers, rubrics, reference answers, layout, and
metadata) and generate rather than merely classify. This shift introduces
trustworthiness failure modes that classical AES does not have to
contend with at the same scale: hallucinated justifications, ungrounded or
fabricated evidence citations, poorly calibrated confidence, brittle
behavior under OCR noise or unfamiliar rubrics, and opaque decision paths
that are difficult for a teacher to audit or challenge.

Existing literature reviews in this space tend to fall into one of two
camps: (a) broad "generative AI in education" surveys that do not isolate
assessment as a task or treat trustworthiness as a first-class dimension,
or (b) narrow technical surveys of a single trust dimension (e.g.,
hallucination benchmarks) with no connection to the assessment domain or
to human-oversight design. Neither camp offers AI researchers a reusable,
evidence-grounded taxonomy of *how* trust is built into multimodal
generative assessment systems, nor a reproducible protocol and
machine-readable evidence dataset that others can extend.

This review is Paper 1 of a four-paper programme. It is designed to (1)
stand alone as a technical contribution to JAIR, and (2) establish the
evidence base that directly motivates Paper 2 (EvalBench, a consent-based
multimodal benchmark), Paper 3 (EvalBot, an evidence-grounded and
confidence-calibrated scoring method), and Paper 4 (an auditable
human-in-the-loop teacher-deferral platform). Every extraction field and
taxonomy dimension in this protocol is chosen because it will later be
operationalized in Papers 2–4; this traceability is itself part of the
review's contribution and is documented explicitly in
`docs/Jair_positioning_and_presubmission.md`.

## 2. Research questions

**Primary RQ:** How are trustworthy multimodal generative-AI systems
designed, evaluated, and governed for automated educational assessment?

- **RQ1.** Which educational assessment tasks, answer formats, and
  modalities are addressed?
- **RQ2.** Which generative multimodal architectures are used, including
  VLMs, MLLMs, OCR-plus-LLM pipelines, multimodal RAG, and rubric-grounded
  systems?
- **RQ3.** How are OCR accuracy, scoring validity, hallucination,
  grounding, calibration, uncertainty, fairness, robustness, and
  explainability evaluated?
- **RQ4.** How are teacher review, human-in-the-loop control, AI
  abstention, and deferral policies implemented and validated?
- **RQ5.** Which datasets, consent/privacy practices, benchmarks, and
  reproducibility artefacts are available?
- **RQ6.** What evidence gaps motivate EvalBench, EvalBot, and an
  auditable teacher-deferral platform?

## 3. Eligibility criteria

Full machine-checkable rules live in `config/inclusion_exclusion.yaml`;
narrative form:

**Amendment PA-001 (logged in `outputs/logs/protocol_amendments.md`):**
the review no longer requires Scopus Q1/Q2 verification as a hard
inclusion gate, and full (peer-reviewed) conference papers are now
core-eligible alongside journal articles. Rationale: a Scopus-only,
journal-only gate systematically excludes work at IEEE, ACM, and other
AI/ML, educational-technology, and HCI conference venues that are central
to this fast-moving literature and are not well captured by journal
quartile metrics. This rule reverts to a hard Scopus/journal-only gate
only if the researcher's supervisor or university explicitly mandates it,
in which case this section, `config/inclusion_exclusion.yaml`, and
`config/protocol.yaml` must be amended back and the change logged.

**Include** only records satisfying **all** of:
1. Published 2025-01-01 through 2026-12-31.
2. Peer-reviewed journal article, or a full (peer-reviewed) conference
   paper — not an extended abstract/poster, and not preprint/arXiv-only.
3. Valid, verified DOI.
4. Direct relevance to automated educational assessment, scoring, grading,
   or feedback (examination, exam-script, rubric-based, short-answer,
   essay, or diagram/STEM assessment; K-12 through higher education).
5. Multimodal component: at least two meaningful modalities/sources
   (answer image, handwriting, OCR text, diagram, question, rubric,
   reference answer, layout, audio/video, assessment metadata).
6. Generative-AI component: LLM, VLM, MLLM, generative document model,
   generative feedback/scoring model, multimodal RAG, or equivalent.
7. At least one trustworthiness dimension: hallucination, grounding,
   calibration, uncertainty, abstention, explainability, fairness,
   robustness, reliability, privacy, auditability, or human oversight.
8. Meets the screening-time quality gate (`config/inclusion_exclusion.yaml:
   quality_criteria`): confirmed peer review, sufficient method detail,
   at least one evaluable/checkable outcome, a clear educational-assessment
   setting, and relevant trustworthiness evidence. Scopus/SCImago quartile,
   where verifiable, is still recorded on every record as a descriptive
   field (for the manuscript's venue-profile table) but does not by itself
   include or exclude a record.
9. English language.

**Exclude:** arXiv/preprint-only papers; records without a DOI;
conference extended abstracts/posters (not full papers); editorials,
letters, theses, book chapters, opinions, generic surveys, tutorials,
non-peer-reviewed documents; generic GenAI-in-education papers with no
assessment/evaluation task; traditional AES with no generative-AI
component; generative-AI papers with no multimodal component; multimodal
systems with no generative component; papers with no educational-
assessment connection; papers failing the screening-time quality gate
(criterion 8); predatory, delisted, or unclear-quality venues.

Exclusion reason codes E01–E15 are enumerated in
`config/inclusion_exclusion.yaml` and used verbatim throughout screening.

## 4. Information sources

- **API-queried:** OpenAlex, Crossref (broad discovery, no venue filter at
  retrieval time; journal articles and full conference papers both
  retrieved).
- **Manually exported by the researcher:** Scopus, Web of Science Core
  Collection, ERIC, IEEE Xplore, ACM Digital Library (journal + full
  conference-paper content types), PubMed (only where the record is
  relevant to medical/health-professions education assessment).
- Under amendment PA-001, full peer-reviewed conference papers from IEEE
  Xplore and ACM DL are core-eligible directly (no longer routed only to
  `outputs/conference_appendix_candidates/`). Non-full-paper conference
  content (extended abstracts, posters, workshop-only submissions without
  peer review) is still excluded (E03) and may be tracked in
  `outputs/conference_appendix_candidates/` for context, never promoted
  without explicit sign-off.

Search is broad and unfiltered by venue quality at discovery time
(Phase 1). Venue/quartile data is still collected in Phase 2 against
authoritative sources (never inferred from reputation) and reported
descriptively, but — per amendment PA-001 — no longer gates inclusion on
its own; the screening-time quality gate (§3, criterion 8) is what
determines inclusion instead.

## 5. Search strategy (summary)

Five concept families (core topic; handwriting/OCR/answer sheets;
trustworthy assessment; rubric grounding and teacher oversight; visual/STEM
answers) are translated into exact, source-specific queries. See
`docs/search_strategy.md` for full rationale and `config/search_queries.yaml`
for the exact query text, filters, and export targets per database. Every
query has a stable `query_id` and is logged (database, filters, date,
result count, export path) to `outputs/csv/prisma_log.csv`.

## 6. Study records management

- Every retrieved/imported record is assigned a stable `record_id`
  (`REC-000001`, …) in `outputs/csv/master_records.csv`, whose full schema
  is defined in `config/data_dictionary.yaml`.
- Raw API responses are preserved unmodified under `data/raw/openalex/` and
  `data/raw/crossref/`; manual database exports are preserved under
  `data/raw/manual_database_exports/`.
- Deduplication is DOI-first (exact match on normalized DOI = duplicate);
  conservative fuzzy title matching applies only to DOI-missing records,
  and never auto-merges — ambiguous matches are routed to
  `data/manual/dedup_manual_review_queue.csv` for human decision. See
  `prompts/04_deduplication_curator.md`.

## 7. Selection process

Two screening stages, both AI-draft-then-human-approved:

1. **Title/abstract screening** — classify include / exclude / unclear
   with an explicit reason code; every AI decision is labeled
   "AI draft—human decision pending" until the researcher records a
   `title_abstract_human_decision`.
2. **Full-text screening** — performed only on legally obtained OA PDFs or
   PDFs the researcher supplies directly; verifies multimodal, generative,
   assessment-relevance, trust-dimension, document-type, DOI, and venue
   eligibility, with page/section evidence recorded.

No record proceeds to extraction or the included-studies set without an
explicit `final_included = true` set by the researcher. See
`docs/screening_manual.md` for the full procedure and worked examples.

## 8. Data extraction items

Extraction fields are defined field-by-field in
`config/data_dictionary.yaml` (`evidence_extraction_csv` block) and cover:
educational context/level/subject, assessment task and answer format,
input modalities, OCR/document model, generative model, RAG/retrieval
component, rubric/reference material, evidence-grounding method,
hallucination definition/test/metric, calibration method/metric,
uncertainty/abstention method, explainability method, fairness/bias
method, human-in-the-loop design, dataset name/size, annotation and
ground-truth process, ethics/consent/privacy, data-split/leakage controls,
baselines, primary metrics, key results, main findings, author-reported
limitations, code/data availability, funding/conflicts. Any field not
reported in the source paper is coded `NR` (Not Reported) — never
inferred. Every major extracted claim carries a page/section/table
reference (`evidence_page_section`). See `docs/screening_manual.md`'s
sibling, `prompts/08_evidence_extractor.md`, for the extraction procedure.

## 9. Quality appraisal

Fourteen dimensions (dataset/consent, ground-truth construction, leakage
safeguards, baseline comparisons, evaluation metrics, calibration,
grounding, hallucination testing, fairness, robustness, human evaluation,
reproducibility, limitations reporting, funding/conflicts), each rated
strong / adequate / weak / NR. Full rubric: `config/quality_appraisal.yaml`;
procedure and worked example: `docs/quality_appraisal_manual.md`. No
automatic composite "risk of bias" score is computed; any narrative
overall judgment is an AI draft requiring explicit human sign-off.

## 10. Synthesis methods

Planned as a **narrative, taxonomy-building synthesis** rather than
meta-analysis (heterogeneous tasks, architectures, and metrics make
pooled effect sizes inappropriate). Synthesis proceeds in three layers:

1. **Descriptive mapping** against RQ1–RQ2 (tasks, modalities,
   architectures) — tables and counts.
2. **Evidence-based thematic analysis** against RQ3–RQ5 (trustworthiness
   mechanisms, human-oversight designs, datasets/reproducibility) —
   organized into the formal taxonomy that is this paper's central JAIR
   contribution (see `docs/Jair_positioning_and_presubmission.md`).
3. **Gap analysis** against RQ6, explicitly connecting identified gaps to
   the design requirements of EvalBench, EvalBot, and the teacher-deferral
   platform.

Synthesis drafting begins only after the researcher has approved final
inclusion and extraction (Phase 5 gate). See
`prompts/13_synthesis_writer.md`.

## 11. Risk of bias in the review process itself

- **Screening bias:** mitigated by requiring human approval of every AI
  screening decision and by logging AI rationale alongside the decision
  for audit.
- **Venue-verification bias:** mitigated by requiring ISSN-first matching
  against authoritative Scopus/SCImago sources and by refusing to infer
  quartile from reputation.
- **Extraction bias:** mitigated by requiring page/section evidence for
  every extracted claim and `NR` coding for anything not directly stated.
- **Publication/availability bias:** legal-OA-only full-text access may
  systematically exclude some eligible closed-access studies from
  full-text-dependent extraction fields; this limitation will be reported
  explicitly in the manuscript's Limitations section, and closed-access
  eligible records are still retained in the PRISMA count with their
  extraction fields marked `NR`/`inaccessible` rather than silently
  dropped.
- **Reviewer bias:** single-researcher screening is a known limitation for
  a PhD-scholar-led review; the AI-draft/human-approval workflow, full
  audit trail, and (optionally) supervisor spot-checks are the mitigation
  strategy, to be disclosed transparently in the manuscript.

## 12. PRISMA 2020 checklist

The manuscript will include the standard PRISMA 2020 27-item checklist and
flow diagram as supplementary material. Flow counts are generated
programmatically by `scripts/10_generate_prisma_counts.py` from
`outputs/csv/master_records.csv` and `outputs/csv/prisma_log.csv`, written
to `outputs/prisma/prisma_flow_counts.json` and
`outputs/prisma/prisma_flow_diagram.md` — never hand-typed, to guarantee
arithmetic consistency (cross-checked by `scripts/14_integrity_audit.py`).

## 13. Protocol amendment policy

Any change to eligibility criteria, search queries, extraction fields, or
target counts after Phase 0 approval is logged in
`outputs/logs/protocol_amendments.md` with: date, section changed, old
value, new value, rationale, and researcher sign-off. `config/protocol.yaml`
and this document are updated together; scripts always read the config
file, so no amendment takes effect until the config is edited.

### Fallback amendment protocol (if fewer than 100 strict Q1/Q2 studies remain)

The target of 100 core included studies (`config/protocol.yaml:
target_core_included_studies`) is a planning target, not a hard
correctness requirement. If, after Phase 2 (cleaning/verification) and
Phase 3–4 (screening), the strict Q1/Q2, 2025–2026, DOI-verified core set
falls materially short of 100, the researcher chooses **one** fallback,
recorded as a logged protocol amendment before Phase 5 synthesis begins:

- **Option A — Widen venue quartile:** extend to Q1–Q3, clearly reporting
  Q3 studies as a separately labeled sensitivity subset in all tables.
- **Option B — Extend date range:** move the start date earlier (e.g., to
  2023-01-01) to capture earlier-generation multimodal GenAI assessment
  work, with a sensitivity note on how this changes RQ2 findings (older
  architectures).
- **Option C — Report reduced-power results:** keep strict criteria and
  proceed with fewer than 100 studies, explicitly framing the review as
  reporting on an early-stage, rapidly emerging literature — a legitimate
  and common framing for 2025–2026-scoped GenAI reviews.
- **Option D — Include the conference appendix in a clearly labeled
  secondary analysis** (not the core Q1/Q2 journal set) to illustrate
  emerging trends, while keeping the primary synthesis restricted to the
  journal core.

No fallback is applied automatically; the researcher selects and approves
one explicitly, and the choice and its rationale are reported transparently
in the manuscript's Methods/Limitations sections.

## 14. Decisions requiring explicit researcher (supervisor) approval

See `docs/supervisor_decision_checklist.md` for the full checklist,
organized by phase. In summary, the researcher must explicitly approve: the
Phase 0 build itself before any retrieval begins; the Phase 1 discovery
scope before broad retrieval; Q1/Q2 venue verification results before
screening; every title/abstract and full-text screening decision; every
extraction record before it is used in synthesis; any protocol amendment
(including the fallback option above); promotion of any conference paper
into the core set; and the final JAIR pre-submission pack before
submission.
