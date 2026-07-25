# Corpus Freeze v1.1

**Date:** 2026-07-22 (supersedes Corpus Freeze v1.0, same date)
**Git commit at freeze:** `f70723122857b91f674fd46a65b04839a7826a7e` (2026-07-13 15:00:16 +0530) — working tree has uncommitted changes; see "Uncommitted work" below.
**Reason for v1.1:** PA-004, a second-pass protocol-conformance audit that found 52 additional false positives beyond PA-002's original 12 (see `outputs/logs/protocol_amendments.md`).

## PRISMA numbers (frozen, fully reconciled)

| Stage | N | v1.0 (superseded) |
|---|---|---|
| Identified (OpenAlex + Crossref) | 13,854 | 13,854 |
| After deduplication | 12,028 | 12,028 |
| Screened (title/abstract) | 400 | 400 |
| Included | 336 | 388 |
| Excluded at full-text (PA-002 + PA-004) | 64 | 12 |
| Full-text extracted | 158 | 158 |
| **Synthesis corpus** | **94** | 146 |
| Pending / no PDF | 242 | 242 |

Identities (hold exactly, zero remainder):
```
400 = 336 + 64
158 = 94 + 64
336 = 94 + 242
```

## Why the corpus shrank from 146 to 94

Not a data-quality accident — a deliberate, escalating-rigor audit:

1. Building a real bibliography surfaced one obviously off-topic record
   (`REC-000011`, fetal ultrasound quality) inside the "included" set.
2. That triggered a full title/abstract read of all 146 against the
   literal protocol criterion (`directly_relevant_to_automated_educational_assessment`)
   rather than trusting the automated relevance pre-filter. Found 45
   high-confidence + 9 ambiguous candidates.
3. Full-text (not abstract-only) read of the 9 ambiguous ones — all 9
   confirmed off-topic.
4. Researcher review of the resulting 54: rejected bulk approval,
   required protocol-literal re-justification (not domain-based),
   personally adjudicated 4 borderline cases (3 exclude, 1 include: the
   AI mock-interview agent), and required a blind 10-record spot-check of
   the remainder before trusting it.
5. Applying the researcher's own "who is assessed, not where" framing
   during the re-check surfaced one more reversal (`REC-003189`, a
   contact-center-agent fairness/coaching study — workplace-training-style
   assessment of a human agent, so it stays included).
6. Spot-check of 10 random records from the remaining 49 passed 10/10.
7. Final: 52 confirmed exclusions, 2 reconsidered back to include.

This is disclosed in the manuscript as a methodological strength (a
secondary protocol-conformance audit), not hidden — see PA-004's
"Manuscript disclosure directive" in `protocol_amendments.md`.

## Authoritative sources for this freeze

- Full detail and cross-file consistency checks: `outputs/reproducibility_report.md`
- PRISMA flow diagram: `docs/prisma_flow.md`
- Amendment history: `outputs/logs/protocol_amendments.md` (PA-001 through PA-004)
- Full triage table with evidence quotes for all 54 PA-004 candidates: `docs/second_pass_offtopic_triage_2026-07-22.md`
- Descriptive synthesis (taxonomy, modality, evidence gaps): `outputs/manuscript/phase5_synthesis_draft.md`
- Bibliography: `outputs/manuscript/refs_synthesis_corpus.bib` (94 entries)
- Data: `outputs/csv/master_records.csv`, `title_abstract_screening_worklist.csv`, `evidence_extraction.csv`, `quality_appraisal.csv`

## What "frozen" means here

No further record identification, deduplication, or re-screening should
happen against this corpus unless a genuine protocol error is discovered
(logged as a new dated amendment). Extraction/appraisal field values may
still be upgraded from `AI_VERIFIED` to `RESEARCHER_CONFIRMED` per-record
as the researcher actually reviews them — that is expected, ongoing work.

## Uncommitted work as of this freeze

Same as v1.0 plus this session's PA-004 CSV edits, the new
`docs/second_pass_offtopic_triage_2026-07-22.md`, and this file. Recommend
a single commit + tag once reviewed:

```bash
git add -A
git commit -m "Corpus freeze v1.1: 336 included / 94 synthesis corpus, PA-001-004"
git tag corpus-freeze-v1.1
```
