# Corpus Freeze v1.2

**Date:** 2026-07-22 (supersedes Corpus Freeze v1.1, same date)
**Git commit at freeze:** `f70723122857b91f674fd46a65b04839a7826a7e` (2026-07-13 15:00:16 +0530) — working tree has uncommitted changes; see "Uncommitted work" below.
**Reason for v1.2:** PA-005, a wrong-PDF-extraction bug found during the manual QC spot-check of 25 randomly sampled records from the synthesis corpus (see `outputs/logs/protocol_amendments.md`).

## PRISMA numbers (frozen, fully reconciled)

| Stage | N | v1.1 (superseded) |
|---|---|---|
| Identified (OpenAlex + Crossref) | 13,854 | 13,854 |
| After deduplication | 12,028 | 12,028 |
| Screened (title/abstract) | 400 | 400 |
| Included | 336 | 336 |
| Excluded at full-text (PA-002 + PA-004) | 64 | 64 |
| Full-text extracted | 157 | 158 |
| **Synthesis corpus** | **93** | 94 |
| Pending / no PDF | 243 | 242 |

Identities (hold exactly, zero remainder):
```
400 = 336 + 64
157 = 93 + 64
336 = 93 + 243
```

## Why the corpus shrank from 94 to 93

Not a screening or protocol-judgment change — an objective data-integrity
fix, found incidentally while performing the researcher-prioritized
manual QC spot-check (comparing AI extraction/appraisal against
independent reading of the source PDF for 25 randomly sampled records):

1. `REC-000210`'s extracted evidence didn't match its own title on
   inspection — the extracted content actually described a different
   paper entirely (an "evolutionary explanations scoring" study).
2. Root-cause investigation found `outputs/corpus/corpus_manifest.csv`
   held duplicate rows per `record_id` (183 physical rows for only 159
   unique IDs), each pointing to a different downloaded PDF file, and
   `scripts/17d_comprehensive_extract.py`'s extraction loop let whichever
   manifest row was processed **last** silently overwrite any earlier
   result — with no title/content validation anywhere in that path.
3. A title-word-overlap heuristic was run across all 93 (then 94) records
   to check for further instances, with two classes of false alarm ruled
   out by manual inspection (a non-Latin-script title with no
   Latin-extractable words; a PDF a quick pypdf-only check can't parse
   but the pipeline's fitz fallback reads correctly).
4. Two more genuine cases confirmed: `REC-007489` (same
   duplicate-manifest-row cause as `REC-000210`) and `REC-001985`
   (extracted content belonged to an unrelated Chinese-firms
   ESG-disclosure paper).
5. `REC-000210` and `REC-007489` were re-extracted from their correct
   files — the manifest duplicates removed, evidence re-extracted and
   re-scored. No change to the synthesis-corpus count for these two.
6. `REC-001985` could not be fixed the same way: only one manifest entry
   ever existed for it, and the true paper (Huang et al., 2025,
   `10.1002/tesq.70042`) was never actually downloaded anywhere in this
   repository. Reset to `pending` — synthesis corpus 94 → 93.

This is disclosed in the manuscript as a further methods-rigor finding
(a sampled QC pass catching a pipeline data-integrity bug that a
purely automated check would not surface), not hidden — see PA-005 in
`protocol_amendments.md` and item 3 of the synthesis draft's "Threats to
validity" section.

## Authoritative sources for this freeze

- Full detail and cross-file consistency checks: `outputs/reproducibility_report.md`
- PRISMA flow diagram: `docs/prisma_flow.md`
- Amendment history: `outputs/logs/protocol_amendments.md` (PA-001 through PA-005)
- Full triage table with evidence quotes for all 54 PA-004 candidates: `docs/second_pass_offtopic_triage_2026-07-22.md`
- Manual QC spot-check report (in progress): `docs/manual_qc_spotcheck_2026-07-22.md`
- Descriptive synthesis (taxonomy, modality, evidence gaps): `outputs/manuscript/phase5_synthesis_draft.md`
- Bibliography: `outputs/manuscript/refs_synthesis_corpus.bib` (93 entries)
- Data: `outputs/csv/master_records.csv`, `title_abstract_screening_worklist.csv`, `evidence_extraction.csv`, `quality_appraisal.csv`, `outputs/corpus/corpus_manifest.csv` (179 rows, deduplicated per `record_id` for the two fixed cases)

## What "frozen" means here

No further record identification, deduplication, or re-screening should
happen against this corpus unless a genuine protocol error is discovered
(logged as a new dated amendment). Objective data errors (duplicate
records, wrong PDFs, corrupted extractions) may still be fixed as found —
that is what produced this v1.2 freeze itself. Extraction/appraisal field
values may still be upgraded from `AI_VERIFIED` to `RESEARCHER_CONFIRMED`
per-record as the researcher actually reviews them — that is expected,
ongoing work.

## Uncommitted work as of this freeze

Same as v1.1 plus this session's PA-005 CSV edits (`corpus_manifest.csv`,
`evidence_extraction.csv`, `quality_appraisal.csv`), the regenerated
`outputs/reproducibility_report.md`, `docs/prisma_flow.md`, `CONTEXT.md`,
`README.md`, `outputs/manuscript/phase5_synthesis_draft.md`,
`outputs/manuscript/refs_synthesis_corpus.bib`, and this file. Recommend
a single commit + tag once reviewed:

```bash
git add -A
git commit -m "Corpus freeze v1.2: 336 included / 93 synthesis corpus, PA-001-005"
git tag corpus-freeze-v1.2
```
