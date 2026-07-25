# Corpus Freeze v1.0

**Date:** 2026-07-22
**Git commit at freeze:** `f70723122857b91f674fd46a65b04839a7826a7e` (2026-07-13 15:00:16 +0530)

> Note: the working tree has uncommitted changes as of this freeze (this
> session's PA-002/PA-003 fixes, the pipeline_stage rollout, and the
> reproducibility report are not yet committed — see "Uncommitted work"
> below). This snapshot documents the *data state*, which is authoritative
> regardless of commit status; committing is a housekeeping step, not a
> prerequisite for the numbers being real.

## PRISMA numbers (frozen, fully reconciled — see PA-003)

| Stage | N |
|---|---|
| Identified (OpenAlex + Crossref) | 13,854 |
| After deduplication | 12,028 |
| Screened (title/abstract) | 400 |
| Included | 388 |
| Excluded at full-text (PA-002) | 12 |
| Full-text extracted | 158 |
| **Synthesis corpus** | **146** |
| Pending / no PDF | 242 |

Identities (hold exactly, zero remainder):
```
400 = 388 + 12
158 = 146 + 12
388 = 146 + 242
```

## Authoritative sources for this freeze

- Full detail and cross-file consistency checks: `outputs/reproducibility_report.md`
- PRISMA flow diagram: `docs/prisma_flow.md`
- Amendment history: `outputs/logs/protocol_amendments.md` (PA-001, PA-002, PA-003)
- Descriptive synthesis (taxonomy, modality, evidence gaps): `outputs/manuscript/phase5_synthesis_draft.md`
- Data: `outputs/csv/master_records.csv`, `title_abstract_screening_worklist.csv`, `evidence_extraction.csv`, `quality_appraisal.csv` (all 400 rows in the latter two, matching the worklist exactly)

## What "frozen" means here

No further record identification, deduplication, or re-screening should
happen against this corpus unless a genuine protocol error is discovered
(and if so, it must be logged as a new dated amendment, not a silent
edit). Extraction/appraisal field values *may* still be upgraded from
`AI_VERIFIED` to `RESEARCHER_CONFIRMED` per-record as the researcher
actually reviews them (`scripts/19_apply_human_verification.py`) — that
is expected, ongoing work, not a violation of the freeze. The freeze is
on corpus *membership and composition* (which 146 studies, which 12
exclusions), not on verification depth.

## Uncommitted work as of this freeze

`git status --short` shows modifications to `README.md`, several
`config/*.yaml` files, `docs/protocol.md`, `outputs/csv/master_records.csv`,
`outputs/prisma/*`, and several `scripts/*.py`, plus untracked new files
(`CONTEXT.md`, `docs/prisma_flow.md`, `docs/human_verification_audit_2026-07-22.md`,
`outputs/corpus/`, `outputs/reproducibility_report.md`, this file, and
others). Recommend a single commit capturing this freeze once reviewed,
e.g.:

```bash
git add -A
git commit -m "Corpus freeze v1.0: 388 included / 146 synthesis corpus, PA-001-003"
git tag corpus-freeze-v1.0
```

Tagging (not just committing) is what makes "traceable back to one
immutable snapshot" literal — `git show corpus-freeze-v1.0:outputs/reproducibility_report.md`
will always retrieve exactly this version.
