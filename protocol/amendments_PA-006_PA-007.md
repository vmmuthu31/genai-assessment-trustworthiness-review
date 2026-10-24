# Protocol amendments PA-006 and PA-007

PA-001 to PA-005 are documented in `protocol/protocol.md` and `corpus_freeze/CORPUS_FREEZE_v1.2.md`.
This file adds the two amendments made after Corpus Freeze v1.2.

## PA-006 — manual quality-control adjudication (2026-08-17)

- **Trigger:** manual audit of a random sample of 25 records against the source PDFs (see `qc/`).
- **Decision:** four records were excluded at full-text assessment after researcher adjudication:
  REC-005263, REC-000906, REC-002464, REC-011407.
- **Effect:** synthesis corpus 93 → 89 (157 − 68 = 89). Frozen as Corpus Freeze v1.3.
- **Type:** protocol-conformance exclusion (eligibility), not a data-integrity fix.

## PA-007 — publication-type restriction (2026-10-24)

- **Trigger:** target journal's reference and evidence rules for the manuscript: no retracted articles,
  no preprints or archives, no books or book chapters, at most three IEEE conference papers,
  no duplicates, DOI required.
- **Decision:** the synthesis corpus is restricted to peer-reviewed journal articles with a DOI.
  Crossref document type was checked for all 89 records; no retraction/withdrawal notices,
  duplicates or books were found. 29 records were excluded:
  - 28 conference proceedings papers (ACL-family venues, workshops and similar; none IEEE),
  - 1 Zenodo archive record (REC-008001).
- **Effect:** synthesis corpus 89 → 60 (157 − 97 = 60). Frozen as Corpus Freeze v1.4.
- **Replacements:** none were admitted. `data/replacement_candidates_v1.4.csv` lists 29 journal articles
  from the 243 pending records that pass the metadata checks. Admission would require full-text
  eligibility assessment and extraction under the protocol and a further amendment.
- **Sensitivity:** principal not-reported proportions change by at most 4.2 percentage points
  between n = 89 and n = 60 (see the manuscript, Section 4.3).
