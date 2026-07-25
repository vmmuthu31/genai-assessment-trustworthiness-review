# Trustworthy Multimodal Generative AI for Automated Educational Assessment: A PRISMA 2020 Systematic Review

This repository contains the reproducibility package for the systematic review submitted to the *Journal of Artificial Intelligence Research* (JAIR): protocol, search/screening/extraction pipeline, frozen evidence dataset, quality-appraisal data, and manual QC audit.

It exists to satisfy JAIR's Reproducibility Checklist and the manuscript's Data Availability statement. The manuscript itself (LaTeX source and compiled PDF) is not included here while under double-blind review; this repository covers the data and pipeline referenced by the Data Availability statement.

## What's here

| Path | Contents |
|---|---|
| `protocol/protocol.md` | Full review protocol, including eligibility criteria and the complete amendment log (PA-001 through PA-005) |
| `data/` | The frozen evidence dataset: `master_records.csv` (deduplicated candidate pool), `evidence_extraction.csv`, `quality_appraisal.csv` |
| `corpus_freeze/` | Dated snapshots of the synthesis corpus (v1.0 → v1.2) documenting exactly how and why the final 93-study corpus changed at each stage |
| `qc/manual_qc_spotcheck_2026-07-22.md` | Manual audit comparing a random sample of extracted/appraised records against source PDFs |
| `docs/` | Search strategy, screening manual, quality-appraisal manual, PRISMA flow documentation, ethical/data-governance notes, AI-use disclosure, and the human-verification and off-topic-triage audit logs |
| `config/` | YAML configuration for the protocol, inclusion/exclusion rules, quality-appraisal rubric, search queries, and data dictionary |
| `scripts/` | The full pipeline, numbered in execution order (`00_setup.py` through `19_apply_human_verification.py`) |

## Corpus at a glance

- 13,854 records identified (OpenAlex + Crossref) → 12,028 after deduplication → 400-record screening shortlist → 336 included at screening → 157 assessed for full-text eligibility → **93 studies in the final synthesis corpus** (Corpus Freeze v1.2, 2026-07-22).
- Full accounting: 336 included at screening = 93 synthesis + 243 pending (no usable full text); 157 extracted = 93 synthesis + 64 excluded. Every count reconciles exactly — see `corpus_freeze/CORPUS_FREEZE_v1.2.md` and `docs/prisma_flow.md`.

## Reproducing the pipeline

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in OPENALEX_MAILTO / CROSSREF_MAILTO at minimum
python scripts/00_setup.py
python scripts/01_fetch_openalex.py
python scripts/02_fetch_crossref.py
# ...continue through the numbered scripts in order; see each script's docstring
```

Each script is numbered in the order it must run. `scripts/_common.py` holds shared utilities (env loading, logging, path resolution). Raw API responses and the legal-OA PDF corpus are not included here (large, regenerable, and in the PDF corpus's case, third-party copyrighted content) — running the fetch scripts against the APIs regenerates them.

## AI-assisted methodology

Screening, full-text eligibility assessment, evidence extraction, and quality appraisal were performed by an AI-assisted, rule-based pipeline whose every decision is logged with quoted evidence and was subject to explicit researcher confirmation. Full disclosure of what the AI tool did and did not do is in `docs/ai_use_disclosure_draft.md` and the manuscript's AI-use statement.

## License

- **Code** (`scripts/`, `config/`): MIT — see `LICENSE`.
- **Data, protocol, and documentation** (`data/`, `protocol/`, `docs/`, `corpus_freeze/`, `qc/`): CC BY 4.0.
- **Manuscript**: matches the license under which it is published; while under review, all rights reserved by the authors.

## Citation

A formal citation (with DOI) will be added here once the manuscript is accepted and published. In the meantime, please cite this repository directly by URL and commit hash.

## Status

This manuscript is currently under review. Some documentation may reference "the review's working repository" — that is this repository.
