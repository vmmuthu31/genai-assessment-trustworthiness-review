# Screening Manual

Operational procedure for title/abstract and full-text screening. Rules
are defined machine-readably in `config/inclusion_exclusion.yaml`; this
manual explains how to apply them consistently, including worked
examples of borderline calls.

## 1. Decision labels

Every screened record receives exactly one of:

- **include** — satisfies all eligibility criteria as far as can be
  determined at this stage.
- **exclude** — fails at least one criterion; an explicit reason code
  (E01–E15, below) is required.
- **unclear** — insufficient information at this stage to decide (common
  at title/abstract stage when multimodality or the generative component
  isn't clear from the abstract alone); routed to full-text screening for
  resolution rather than excluded outright.

## 2. Exclusion reason codes

| Code | Meaning |
|------|---------|
| E01 | arXiv/preprint-only |
| E02 | No DOI |
| E03 | Conference-only, not core (→ `conference_appendix_candidates`) |
| E04 | Wrong document type (editorial/letter/thesis/book chapter/opinion/tutorial/non-peer-reviewed) |
| E05 | Generic GenAI-in-education paper, no assessment/evaluation task |
| E06 | Traditional AES, no generative-AI component |
| E07 | Generative AI, no multimodal component |
| E08 | Multimodal, no generative component |
| E09 | No educational-assessment connection |
| E10 | Venue quartile unverified |
| E11 | Predatory/delisted/unclear-quality journal |
| E12 | Outside date range (2025-01-01 to 2026-12-31) |
| E13 | Not English |
| E14 | Duplicate record |
| E15 | Other (free-text justification required in `notes`) |

Exactly one primary reason code is recorded per exclusion, even when
multiple criteria fail — record the *first* criterion checked in the
canonical order of `config/inclusion_exclusion.yaml:
core_inclusion_requires_all`, and note any additional failing criteria in
`notes` for completeness.

## 3. AI-draft / human-approval workflow

1. The Screening Agent (`prompts/06_title_abstract_screener.md`) reads
   title + abstract (+ keywords) for each record in
   `outputs/csv/master_records.csv` and writes
   `title_abstract_ai_decision`, `title_abstract_ai_reason`, and
   `title_abstract_ai_rationale` (a one-to-two sentence justification).
   Every such row is implicitly labeled "AI draft—human decision
   pending" until `title_abstract_human_decision` is filled in.
2. The researcher reviews each AI draft in the screening workbook
   (`outputs/excel/…Workbook.xlsx`, sheet `Title_Abstract_Screening`) and
   either confirms or overrides, recording
   `title_abstract_human_decision`, `reviewer_name`, `review_date`.
3. The same two-step pattern repeats at full-text stage
   (`fulltext_ai_decision`/`fulltext_ai_reason`/`fulltext_ai_rationale` →
   `fulltext_human_decision`), performed only by
   `prompts/07_full_text_reviewer.md` against legally obtained OA PDFs or
   researcher-supplied PDFs, with page/section evidence recorded.
4. `final_included` is set only after both human decisions are `include`;
   it remains null/pending otherwise. Nothing downstream (extraction,
   appraisal, synthesis) treats a record as included until
   `final_included = true`.

## 4. Conflict resolution

Because this is a single-PhD-researcher-led review (see
`docs/protocol.md` §11, Risk of bias — Reviewer bias), there is no second
independent human screener by default. Conflict resolution instead means:
**AI draft vs. human judgment**, not human vs. human. When the researcher
overrides an AI draft decision, the override and a one-line rationale are
recorded in `notes`; a running log of override patterns (e.g., "AI
consistently over-includes generic GenAI-education papers") is useful
input to refining `prompts/06_title_abstract_screener.md` and should be
raised as a protocol-adjacent observation, not a protocol amendment,
unless it changes an eligibility rule itself. If a second screener
(e.g., a supervisor or co-author) is added at any point, standard
double-screening conflict resolution (discussion → third-reviewer
adjudication) should be documented as a protocol amendment before it is
used.

## 5. Worked examples

**Example A — Traditional AES, no generative component.**
*Abstract:* "We fine-tune a BERT-based regressor to predict holistic
essay scores from student text, achieving QWK of 0.81 on the ASAP
dataset." → No LLM/VLM/MLLM/generative model; the architecture is a
discriminative regressor. **Decision: exclude, E06.**

**Example B — Generic GenAI-in-education, no assessment task.**
*Abstract:* "We study how students use ChatGPT for exam preparation and
report on self-reported learning gains via survey." → No automated
scoring/grading/feedback-generation task; this is a usage/learning-gains
study, not an assessment system. **Decision: exclude, E05.**

**Example C — Generative but single-modality.**
*Abstract:* "We prompt GPT-4 with plain-text student answers and a
text rubric to generate a numeric score and justification." → Only one
modality present (text answer + text rubric both count as "text," and
the criterion requires two *meaningfully distinct* sources such as image
+ OCR text, or image + rubric — text-only rubric-grounded scoring with no
image/document/diagram input does not meet the multimodal bar).
**Decision: exclude, E07.** (Note in `notes`: "borderline — text rubric +
text answer only; revisit if protocol's modality-count definition is
amended.")

**Example D — Multimodal but not generative.**
*Abstract:* "We use a CNN-based diagram classifier alongside OCR'd
handwritten text to assign a rubric category via a trained
softmax classifier." → Multimodal input present, but the model is
discriminative/classification-based with no generative output (no LLM,
VLM, or generative scoring/feedback text). **Decision: exclude, E08.**

**Example E — Meets all criteria.**
*Abstract:* "We present a VLM pipeline that ingests scanned handwritten
answer sheets, question papers, and rubrics; generates a rubric-grounded
score with cited evidence spans; and reports hallucination rate,
calibration (ECE), and a teacher-override interface evaluated with 12
teachers." → Multimodal (image + OCR + rubric + question), generative
(VLM), assessment task (short-answer scoring), ≥1 trust dimension
(hallucination + calibration + human oversight). Pending DOI/venue
verification. **Decision: include** (subject to venue Q1/Q2 verification
downstream).

**Example F — Unclear at title/abstract stage.**
*Abstract:* "A multimodal system for automated grading of student work."
→ Too sparse to determine modality count, generative-vs-discriminative
architecture, or trust dimension. **Decision: unclear** → routed to
full-text screening.
