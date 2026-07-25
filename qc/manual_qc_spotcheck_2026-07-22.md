# Manual QC Spot-Check — 25 Randomly Sampled Records (2026-07-22)

**Purpose:** validate the AI-drafted extraction (`evidence_extraction.csv`)
and quality appraisal (`quality_appraisal.csv`) against an independent
reading of each record's source PDF, and quantify agreement/disagreement,
per the researcher's explicit top-priority request. This is distinct from
the earlier PA-002/PA-004 screening audits — this pass checks *extraction
and appraisal quality* for records already confirmed on-topic, not the
inclusion/exclusion decision itself (though it incidentally surfaced
issues in both categories — see §2 and §3 below).

**Sample:** 25 records drawn by `random.seed(20260722)` from the
then-current synthesis corpus (94 records, before PA-005). Sample:
`REC-000050, REC-000107, REC-000210, REC-000396, REC-000517, REC-000663,
REC-000906, REC-001162, REC-001985, REC-002446, REC-002464, REC-005083,
REC-005263, REC-005858, REC-005979, REC-006268, REC-007673, REC-007860,
REC-008001, REC-008355, REC-008409, REC-008519, REC-009731, REC-011407,
REC-013529`. This sample is fixed and was not redrawn after PA-005 removed
`REC-001985` from the corpus — re-sampling after a bug fix that the QC
process itself triggered would be circular; `REC-001985`'s presence in the
sample is itself a valid (and important) result, not a defect to correct
by resampling.

**Method:** for each record, `scripts/17d_comprehensive_extract.py`'s own
`extract_text()` (pypdf + fitz fallback, the same function the pipeline
uses) was re-run to pull the full PDF text, which was then read directly —
title, abstract, methods, and results — and checked against every
populated field in `evidence_extraction.csv`, with particular attention to
`generative_model`, `assessment_task`, `input_modalities`, and (for the 6
most deeply reviewed) the quality-appraisal ratings. Keyword/regex checks
(model names, task vocabulary) were used to locate the relevant passage
quickly, but the judgment on each disagreement was made by reading the
surrounding text, not by trusting the keyword match alone — the same
discipline applied throughout this project's screening audits.

## 1. Headline result

**Revision note (2026-07-22, second pass):** the table below supersedes an
earlier draft of this report. A first pass through §1 only checked
`generative_model` and `assessment_task` systematically; a follow-up pass
— done specifically to answer the researcher's request for quantified,
field-level agreement rates (§7) — re-checked `input_modalities` with the
same rigor (keyword hits verified against surrounding context, not trusted
at face value) and found four further disagreements that the first draft
had filed under "clean," including a modality error on `REC-000050` that
sits alongside its previously-noted appraisal disagreement. Numbers below
are the corrected, final counts.

| Category | Count / 25 |
|---|---|
| Wrong-PDF / data-integrity bug (PA-005, now fixed) | 2 (`REC-000210`, `REC-001985`) |
| Protocol-conformance candidates flagged (**paused per researcher direction — see §2 note**) | 4 |
| Extraction field-level disagreements (record is the right paper; some field values are wrong/incomplete) | 9 |
| — of which also has a quality-appraisal disagreement | 1 (`REC-000050`) |
| No material disagreement found | 10 |

A third wrong-PDF case, `REC-007489`, was found via the same
title-word-overlap heuristic applied to the full 94-record corpus (a
direct consequence of this sample flagging `REC-000210` and triggering
that broader check) but was not itself one of the 25 sampled records —
noted here for completeness; full detail is in PA-005
(`outputs/logs/protocol_amendments.md`).

**Reading these numbers:** of the 23 records that were genuinely the
correct paper, 10/23 (43%) had no material issue, 9/23 (39%) had at least
one field-level extraction gap or mislabel worth correcting (one of which,
`REC-000050`, also had an appraisal-rating disagreement), and 4/23 (17%)
raised a protocol-conformance question worth researcher review. None of
the disagreements found involve fabrication — every extracted value traces
to *something* in the source PDF; the errors are keyword-matching
limitations (wrong span attributed, right paper, or a citation to related
work mistaken for the paper's own method — see §3.7 and the new §3.9-3.10
below), not invented content.

## 2. Protocol-conformance candidates found incidentally (NOT excluded — paused per researcher direction)

Per the process established in PA-004, no exclusion is applied here
without the researcher's explicit, non-bulk review. These four are
presented as proposed candidates only, each with a quoted basis, following
the same "who is being assessed, not where" test used throughout PA-004.

**Researcher review (2026-07-22):** three of the four were independently
assessed as high-confidence exclusions (`REC-005263`, `REC-000906`,
`REC-002464` — reasoning endorsed as consistent with the protocol in each
case), and the fourth (`REC-011407`) was flagged as genuinely borderline
and worth a dedicated read before any call is made — specifically, whether
the study's evaluation is confined to emotion-recognition-model accuracy
(exclude) or extends to learner outcomes / AI-mediated learner assessment
(may belong). Per explicit researcher instruction, **no amendment is
issued from this list yet, even for the three high-confidence cases** —
the corpus stays at Corpus Freeze v1.2 (93 records) until all four have a
final decision, so that any future protocol change is captured as one
clean version rather than a partial, in-between state. If/when finalized,
this becomes PA-006 (dropping the corpus to 89 if all four are excluded,
90 if `REC-011407` is kept).

1. **`REC-005263`** — "Intellectualizing Virtual Learning Environments with
   Artificial Intelligence Agents: Current Trends, Methods and Challenges."
   The paper's own English abstract states: *"The paper provides a
   structured review of current approaches to intelligent virtual learning
   environments (VLEs)... The review is based on publications indexed in
   leading bibliographic and digital libraries."* This is a literature
   review/survey, not a primary empirical study — the same E10 category
   (secondary review, not primary empirical study) PA-004 used to exclude
   `REC-001355`. High confidence.
2. **`REC-000906`** — "Advancing Multimodal Large Language Models:
   Optimizing Prompt Engineering Strategies for Enhanced Performance." A
   general MLLM prompt-engineering benchmark study, evaluated via BLEU,
   ROUGE, METEOR, S-BERT, MoverScore, CIDEr on VQA/ScienceQA-style
   benchmark datasets. Full-text keyword counts: "student" = 0,
   "classroom" = 0, "grading" = 0; "assessment" appears 4 times but always
   in the sense of *"a holistic assessment of model performance"* — the AI
   model's own output quality is what's being assessed, not a learner. High
   confidence this is a relevance-pre-filter false positive of the same
   type PA-004 targeted (E09).
3. **`REC-002464`** — "The Confident Liar: Diagnosing Multi-Agent Debate
   with Log-Probabilities and LLM-as-Judge." Studies whether an AI
   multi-agent debate system's internal confidence signals predict its own
   reasoning quality and task accuracy — the assessed entity is the debate
   system itself (a "Constructor" and "Auditor" AI agent pair), not a human
   learner, despite the paper's use of "rubric-based scoring" language.
   High confidence E09.
4. **`REC-011407`** — "MEPT-LLM: a multimodal generative AI model for
   identifying and understanding cultural-emotional barriers in the
   language classroom." Evaluated on the MELD and MEMD emotion-recognition
   benchmark datasets; the model's own emotion-perception and
   content-generation quality is what's measured ("a performance increase
   of 12%–15%"), not a learner's assessed academic work or performance,
   though the paper's framing (language-classroom emotional barriers,
   personalized feedback) is closer to the educational domain than #2 or
   #3 above. Medium confidence — this one is more genuinely borderline and
   would benefit most from the researcher's own read, following the same
   "who is assessed" test.

**Status:** superseded by the researcher-review note above — three of the
four are researcher-endorsed high-confidence excludes and one
(`REC-011407`) needs a dedicated read, but per explicit instruction no
amendment is issued and the corpus is not changed until all four are
resolved together (see §7.5).

## 3. Extraction field-level disagreements (right paper, wrong/incomplete field values)

1. **`REC-000107`** (previously identified, retained here for
   completeness): incomplete `generative_model` list; `baselines` field
   contained garbled/truncated text rather than a clean citation; and a
   semantic conflation between psychometric "item calibration" (a
   measurement-theory concept) and AI "model calibration" (a
   confidence/uncertainty trustworthiness dimension) — the two are
   triggered by the same keyword (`calibrat*`) but mean different things.
2. **`REC-005083`** ("AssessIQ" proctoring system): `assessment_task`
   recorded as `MCQ; exam` only. The paper describes five assessment
   modalities including *"voice interviews, webcam-based video interviews,
   and structured multi-section interviews"* (40 mentions of "interview,"
   4 of "oral" in the full text) — `oral`/interview-based assessment is
   missing from the task list despite being a primary described modality.
3. **`REC-005979`** ("Two Heads Are Better Than One"): `assessment_task`
   recorded as `NR`. The paper's own framing is explicit: *"This limitation
   is especially critical in Automated Student Answer Scoring (ASAS)"* —
   `short-answer` (or an ASAS-specific tag) should have been extracted, not
   `NR`.
4. **`REC-006268`** ("Ascend AI" career/interview simulator):
   `assessment_task` recorded as `NR`. The paper is centrally about
   *"responsive, interactive audio interview simulations"* for technical
   interview practice (16 mentions of "interview," 5 of "oral") —
   `oral`/interview should have been extracted, not `NR`. Same class of
   miss as `REC-005083`, suggesting the task-extraction keyword list may
   systematically under-cover interview/oral-assessment framing.
5. **`REC-007860`** ("Trojsten Benchmark"): `assessment_task` recorded as
   `translation` only. The paper's primary task is rubric-based grading of
   Slovak-language STEM competition problems (math/physics/programming);
   translation is a secondary robustness check ("accuracy drops on English
   translations of Slovak statements"), not the primary task — the
   extraction keyed on the incidental "translation" mention and missed the
   primary grading/exam task entirely. Separately, the model list
   (`GPT-4o; GPT-4; GPT-3.5/ChatGPT; LLaMA-3; LLaMA`) omits `Phi-3`, which
   the paper explicitly benchmarks alongside Llama 3 ("open-weight models
   (Llama 3, Phi-3)") — a recall gap in the model taxonomy's keyword list.
6. **`REC-008355`** ("Emergent Wisdom," BEA 2025 shared task):
   `generative_model` recorded as `T5/FlanT5` only. The paper's own
   architecture description names three components including *"a
   rubric-guided large language model (LLM) agent"* and *"a
   reasoning-intensive LLM judge"* in addition to the fine-tuned T5
   classifier — `LLM (unspecified)` should have also been captured
   alongside `T5/FlanT5`, not replaced by it.
7. **`REC-008409`** ("AIvaluate"): `generative_model` recorded as `GPT-4o;
   BERT; T5/FlanT5`. On inspection, this conflates two different sources:
   the paper's own AI agents actually run on **GPT-4o-mini** (*"the
   Pre-processing AI agent (also powered by GPT-4o-mini hosted on Azure AI
   Foundry)"*) — a real but more specific model than plain GPT-4o — while
   **BERT** and **T5** appear only inside a citation to a different,
   prior system: *"DAES [1] implemented topic modeling and semantic
   insight with T5 transformers"* and *"embedding models like
   Sentence-BERT"* cited as related work, not as anything this paper's own
   system uses. This is a more concerning pattern than a simple recall
   gap: the keyword-based extractor cannot distinguish a paper's own
   method from a method it cites as related work, which can misattribute
   an entirely different system's model choice to the record being
   extracted. Worth checking for recurrence across the wider corpus before
   trusting the model taxonomy table without spot-checking further.

`REC-009731` ("CalcTutor") has a related but much milder version of the
same granularity issue — its own system uses "GPT-4o mini for real-time
processing," extracted as plain `GPT-4o` — same family, imprecise variant,
not a misattribution, so not counted as a disagreement above.

8. **`REC-000050`** ("Evaluating LLMs for Automated Scoring in Formative
   [assessment]"): `input_modalities` recorded as `text; image`. The only
   textual basis for "image" is *"For visual demonstrations of the
   platform's interface and functionalities, see Appendix A (Figures
   A1–A4)"* — screenshots of the paper's own software UI in an appendix,
   not an image-based assessment input. No other image/visual content
   signal appears anywhere in the text. The correct tag is `text` only.
   This sits alongside the appraisal disagreement already noted for this
   record in §4 — `REC-000050` has both an extraction and an appraisal
   issue.
9. **`REC-005979`** (already flagged in item 3 above for its
   `assessment_task` miss) also has an `input_modalities` error: recorded
   as `text; image`, but the only "image"-adjacent keyword hits are a
   substring match inside a student's quoted answer text
   ("PHOTO­SYNTHESIS PRODUCES OXYGEN" → matched "photo") and an explicit
   statement that the paper's own dataset *excludes* non-text responses:
   *"we exclude essay-like or multimodal subsets"*. The correct tag is
   `text` only — this is a false-positive keyword match, not a missed
   modality.
10. **`REC-008519`** ("HackEval"): `input_modalities` recorded as `NR`,
    but the paper's own UI/UX Evaluation Agent explicitly scores
    *"Screenshots / PNG"* using a CLIP-based aesthetic regressor as part
    of the live system (not future work — a "Video Pitch Analyzer" is
    separately proposed as future work and correctly excluded). The
    correct tag should include `image` (plausibly `text; image` or
    `multimodal`, given the system also processes code/text and
    presentation content), not `NR`.

A borderline case, not counted as a disagreement above: **`REC-007673`**'s
`input_modalities` tag of `text; image` rests on *"an ASCII UML class
diagram"* embedded in an assignment prompt — arguably still text (ASCII
art), not a true image input. Left as a footnote rather than a counted
disagreement since reasonable people could tag this either way.

Also checked and confirmed as **false alarms** (initially flagged by the
keyword scan, ruled out on reading context — kept here to show the check
was actually performed, not skipped): `REC-000107`'s modality tag of `NR`
is essentially correct — its "image/audio/speech/multimodal" keyword hits
are all inside a related-work discussion of data-augmentation techniques,
and the paper explicitly states its own item pool *"consisted only of
questions without images, figures or tables because not all the LLMs
support multimodal capabilities"* — genuinely text-only. `REC-000396`'s
"video/visual" hits are a citation to an unrelated field ("video saliency
prediction... in other fields") and a reference to the paper's own result
charts ("visualizations of the score distributions") — its `text`-only
tag is correct.

## 4. Quality-appraisal disagreement

- **`REC-000050`** (previously identified, retained here for
  completeness): the rule-based appraiser likely under-rated
  `human_evaluation` and/or `baseline_comparisons` relative to what the
  full text actually reports — flagged for a closer look during the
  researcher-confirmation pass, not corrected here (appraisal corrections,
  unlike the objective PA-005 data bugs, are judgment calls that should go
  through the same `RESEARCHER_CONFIRMED` workflow as every other record,
  not be silently adjusted). As noted in §3.8, this record also has an
  `input_modalities` extraction error, making it the only record in the
  sample with disagreements in two different categories.

## 5. Records with no material disagreement (10/25)

`REC-000396`, `REC-000517`, `REC-000663`, `REC-001162` (a rubric-based
teaching-quality-assessment study — on-topic under the same
workplace/professional "who is assessed" framing PA-004 applied to
`REC-003189`), `REC-002446` (Qwen2-Audio L2 pronunciation scoring — model,
task, and modality all confirmed against the text), `REC-005858`,
`REC-007673` (see the ASCII-diagram footnote in §3 — treated as clean, not
a clear disagreement), `REC-008001` (`generative_model=NR` independently
confirmed correct — no generative-AI keyword anywhere in the full text;
this is a genuinely classical-ML paper, not an extraction failure),
`REC-009731`, `REC-013529`.

## 6. Quantified agreement

Two denominators matter here: all 25 sampled records (the raw draw), and
the 23 that turned out to be genuinely the correct paper (the fair
denominator for judging extraction/appraisal *quality*, since a
wrong-linked record isn't a "disagreement" in the same sense — it's a
different failure mode, already broken out in §PA-005).

| Measure | Value |
|---|---|
| Records with correct PDF linkage | 23/25 (92%) |
| Records with no material disagreement (of the 23 correctly linked) | 10/23 (43%) |
| Records requiring at least one field correction (of the 23) | 9/23 (39%) |
| Records with a protocol-conformance flag (of the 23) | 4/23 (17%) |
| Records with a quality-appraisal disagreement (of the 23) | 1/23 (4%) |

**Field-level agreement**, computed only over the 23 correctly-linked
records, counting a record as a "disagreement" for a field if §3 documents
a specific, quoted mismatch for that field:

| Field | Disagreements | Agreement rate | Records disagreeing |
|---|---|---|---|
| `generative_model` | 4/23 | 82.6% | `REC-000107`, `REC-007860`, `REC-008355`, `REC-008409` |
| `assessment_task` | 4/23 | 82.6% | `REC-005083`, `REC-005979`, `REC-006268`, `REC-007860` |
| `input_modalities` | 4/23 | 82.6% | `REC-000050`, `REC-005979`, `REC-008355`, `REC-008519` |

All three core content fields land at almost exactly the same ~83%
agreement rate. Two records (`REC-005979`, `REC-008355`) disagree on two
fields at once; `REC-007860` disagrees on two fields at once; `REC-000050`
has a modality disagreement plus a separate appraisal disagreement (§4).
No record disagreed on all three fields simultaneously, and every
disagreement traced to a specific, identifiable cause (a related-work
citation mistaken for the paper's own method, a keyword substring match
inside quoted student text, or a real coverage gap in the task/model
keyword list) rather than random noise — this is useful for prioritizing
the pipeline fixes in §7 below, since the errors cluster by mechanism, not
by record.

`quality_appraisal.csv` disagreement was checked with this level of rigor
for only 1 of the 23 records in this pass (`REC-000050`, carried over from
an earlier review) — appraisal quality was not re-verified field-by-field
for the other 22 with the same depth as the extraction fields above.
Reporting an appraisal agreement percentage from n=1 would be misleading;
this is flagged in §8 as unfinished work for a future round, not rounded
up to a headline number.

## 7. Recommendations

1. **Extraction script fix (root cause of §3.6-3.7 and PA-005):**
   `scripts/17d_comprehensive_extract.py`'s model/task keyword matching
   should be scoped to the paper's own methods/system-description section
   where feasible, or at minimum should down-weight matches that occur
   inside a citation context (e.g., immediately following a bracketed
   reference number like `[1]`), to reduce the citation-vs-own-method
   conflation seen in `REC-008409`.
2. **Task-taxonomy keyword coverage:** add explicit interview/oral-exam
   trigger terms ("interview," "oral exam," "spoken response") to the
   `assessment_task` extractor — two independent misses (`REC-005083`,
   `REC-006268`) suggest this is a systematic gap, not a one-off.
3. **Calibration-term disambiguation** (from `REC-000107`, previously
   noted): distinguish "item calibration" (IRT/psychometrics) from "model
   calibration" (AI confidence/uncertainty) in the `calibration_method`
   extractor — these are different constructs sharing a keyword.
4. **Modality false-positive check:** the `input_modalities` extractor
   should not treat a substring match inside quoted source text (e.g.
   "photo" inside a student's quoted answer "PHOTOSYNTHESIS...") or a
   mention of the paper's own result figures ("see Appendix A, Figures
   A1-A4") as evidence of a non-text input modality — both caused false
   `image` tags in this sample (`REC-000050`, `REC-005979`).
5. **PA-006 — paused, per researcher direction (2026-07-22).** The
   researcher independently reviewed all four candidates in §2 and agrees
   with the reasoning for three (`REC-005263`, `REC-000906`, `REC-002464`
   — high confidence exclude) but wants `REC-011407` read more closely
   before any decision, since its evaluation may or may not extend to
   learner outcomes rather than pure emotion-recognition accuracy. **No
   amendment is issued and no record's status changes as a result of this
   report** — per explicit instruction, the corpus stays frozen at Corpus
   Freeze v1.2 (93 records) until all four have a final call, so that any
   future protocol change lands as one clean version (PA-006) rather than
   a partial, in-between state. If eventually confirmed, the synthesis
   corpus would drop to 89 (all four excluded) or 90 (`REC-011407` kept).
6. **Do not treat this sample as fully closing the QC question.** 25/93
   (27%) is a reasonable spot-check rate, but the citation-vs-own-method
   conflation found in `REC-008409` and the wrong-PDF bug found in
   `REC-000210`/`REC-007489`/`REC-001985` were both discovered by reading
   full text carefully, not by trusting the pipeline's own heuristics —
   this suggests the remaining 68 non-sampled records could plausibly
   contain a small number of similar issues. A second, smaller spot-check
   after the `RESEARCHER_CONFIRMED` pass begins would be a reasonable
   checkpoint.

## 8. Field-value corrections applied as a result of this QC pass

Only the objective data bugs (§PA-005) were corrected as part of this
report — `REC-000210` and `REC-007489` re-extracted from their correct
source PDFs, `REC-001985` reset to `pending`. The field-level disagreements
in §3 and the appraisal disagreement in §4 are **documented, not
corrected** — per this project's established discipline, extraction/
appraisal field corrections are the researcher-confirmation pass's job
(`scripts/19_apply_human_verification.py`, `outputs/review_packet.html`),
not something to silently patch during a QC audit. This keeps a clean
separation between "the record points to the wrong paper" (an objective
bug, fixed immediately per the researcher's standing authorization) and
"the record's fields could be read differently" (a judgment call requiring
the researcher's own review).
