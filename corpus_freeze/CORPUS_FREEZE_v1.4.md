# Corpus Freeze v1.4 (final, used in the manuscript)

**Date:** 2026-10-24 (supersedes v1.3)
**Reason:** PA-007, publication-type restriction to journal articles. See `protocol/amendments_PA-006_PA-007.md`.

| Stage | N |
|---|---|
| Identified (OpenAlex + Crossref) | 13,854 |
| Duplicates removed | 1,826 |
| After deduplication | 12,028 |
| Not carried forward by the relevance heuristic | 11,628 |
| Shortlisted | 400 |
| Full-text assessed | 157 |
| Pending, no usable legal full text | 243 |
| Excluded at full text | 97 (PA-002: 12, PA-004: 52, PA-006: 4, PA-007: 29) |
| **Synthesis corpus** | **60** |

Identities: 13,854 − 1,826 = 12,028; 12,028 − 11,628 = 400; 400 = 157 + 243; 157 = 60 + 97.

Files: `data/synthesis_corpus_v1.4.csv` (60 included), `data/fulltext_exclusions_v1.4.csv` (97 exclusions with reasons),
`data/evidence_extraction.csv` (column `corpus_status_v1_4` gives the status of every record),
`data/replacement_candidates_v1.4.csv` (not part of the corpus).

All 60 records are journal articles (Crossref types `journal-article`), 30 published in 2025 and 30 in 2026.
Headline-field researcher confirmation (12 fields) is recorded in `headline_fields_researcher_confirmed` as the authors'
attestation. Peripheral fields remain AI-verified only (`extraction_status = ai_verified_pass2`).
