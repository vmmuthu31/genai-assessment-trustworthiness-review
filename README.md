# Trustworthiness of Generative AI for Automated Educational Assessment: PRISMA 2020 Systematic Review (reproducibility package)

This repository contains the reproducibility package for the systematic review *Trustworthiness of generative AI for automated educational assessment: a PRISMA 2020 systematic review* (submitted to *Artificial Intelligence Review*): protocol, search/screening/extraction pipeline, frozen evidence dataset, quality-appraisal data, and manual QC audit.

It supports the manuscript's Data Availability statement. The manuscript itself is not included here while under review.

## What's here

| Path | Contents |
|---|---|
| `protocol/protocol.md` | Review protocol with eligibility criteria and amendments PA-001 to PA-005 |
| `protocol/amendments_PA-006_PA-007.md` | PA-006 (manual QC adjudication) and PA-007 (journal-article restriction) |
| `data/` | `master_records.csv` (deduplicated pool), `evidence_extraction.csv` (with `corpus_status_v1_4`), `quality_appraisal.csv`, `synthesis_corpus_v1.4.csv` (the 60 included studies), `fulltext_exclusions_v1.4.csv` (97 exclusions), `replacement_candidates_v1.4.csv` |
| `corpus_freeze/` | Dated snapshots v1.0 to v1.4 showing how the corpus changed (final: 60 studies) |
| `qc/` | Manual audit of a random sample against source PDFs |
| `docs/` | Search strategy, screening and appraisal manuals, PRISMA flow notes, governance, AI-use disclosure, audit logs |
| `config/` | YAML configuration |
| `scripts/` | The pipeline, numbered in execution order |

## Corpus at a glance (Corpus Freeze v1.4, 2026-10-24)

- 13,854 records identified (OpenAlex + Crossref), 1,826 duplicates, 12,028 after deduplication, 400 shortlisted, 157 with full text assessed, 243 pending (no usable legal full text).
- 97 excluded at full text (PA-002: 12, PA-004: 52, PA-006: 4, PA-007: 29), leaving **60 journal articles** in the synthesis corpus.
- Identities: 400 = 157 + 243 and 157 = 60 + 97.
- Earlier pipeline scripts, configs and logs mention the journal this work was first submitted to; they are kept unchanged as a record of the original process.

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

See `CITATION.cff`. A Zenodo DOI for the archived release will be added here once deposited.

## Status

This manuscript is currently under review. Some documentation may reference "the review's working repository" — that is this repository.
