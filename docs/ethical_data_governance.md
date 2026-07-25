# Ethical Data Governance

Governs how this review handles third-party content (papers, metadata,
PDFs) and any student data referenced within included studies.

## 1. Legal open-access-only PDF policy

- PDFs are downloaded **only** when legal OA access is confirmed by the
  publisher's own OA license, an OpenAlex-reported OA URL, Unpaywall, PMC,
  DOAJ, or a legitimate institutional repository (`scripts/09_download_
  legal_oa_pdfs.py` checks `open_access_status`/`open_access_url` before
  any download and validates the retrieved file is a genuine PDF).
- ResearchGate, Academia.edu, or similar are usable only as *discovery
  pointers* to locate an OA copy elsewhere — never as the authoritative
  source for a "legal PDF" determination, per `config/protocol.yaml` /
  the project's non-negotiable integrity rules.
- Closed-access eligible studies are **not** dropped from the review;
  they remain in the PRISMA count and master record set, with full-text-
  dependent fields coded `NR`/`inaccessible` rather than extracted from
  an unauthorized source.

## 2. No paywall bypassing

No scraping, sci-hub-style mirrors, credential sharing, or any other
paywall circumvention is used at any phase, regardless of retrieval
difficulty. If the researcher has personal or institutional subscription
access to a closed-access paper, extraction may proceed from a
researcher-supplied PDF (Phase 4 allows "legal OA PDFs or PDFs I supply"),
but such PDFs are for the researcher's own extraction use and are **not**
redistributed in `outputs/corpus/` unless their license explicitly
permits it.

## 3. Student data / consent in included studies

This review does not collect any new student data — it reviews *published
papers describing* systems that process student answer sheets. Ethical
handling here means:

- **Extraction focus:** `evidence_extraction_csv` explicitly captures
  `ethics_consent_privacy` as a first-class field (RQ5), so the review can
  report, in aggregate, how the underlying literature handles student
  consent, IRB/ethics approval, and data anonymization — surfacing this as
  an evidence gap where it is `NR` is itself a review finding, not a
  shortcoming to paper over.
- **No re-identification risk:** the review never extracts or stores
  actual student work, names, or identifiers from included papers' data —
  only descriptive metadata about the *dataset and consent practices* the
  paper reports.
- **Downstream relevance:** this field directly informs the consent model
  for Paper 2 (EvalBench), which the researcher has scoped as
  "consent-based" from the outset — the review's findings here are a
  direct input to that design decision.

## 4. AI tool disclosure policy

- No AI tool (Claude Code or otherwise) is ever listed as an author.
- All AI-assisted outputs (search queries, screening drafts, extraction
  drafts, appraisal drafts, manuscript drafting support) are explicitly
  labeled as such throughout the pipeline (`"AI draft—human decision
  pending"` convention) and require human approval before being treated
  as final.
- A truthful, specific AI-use disclosure statement is maintained as a
  living draft at `docs/ai_use_disclosure_draft.md` and finalized in
  Phase 6 for inclusion in the manuscript's Declarations section.

## 5. Data retention and handling of raw metadata exports

- Raw API responses (`data/raw/openalex/`, `data/raw/crossref/`) and
  manual database exports (`data/raw/manual_database_exports/`) are
  retained locally for reproducibility and audit but are excluded from
  version control (`.gitignore`) because bulk bibliographic exports from
  Scopus/WoS are typically subject to the exporting database's own terms
  of use restricting redistribution.
- `outputs/csv/master_records.csv` (normalized, derived metadata — titles,
  DOIs, abstracts, decisions) is the shareable, versionable artifact; it
  is treated as the review's machine-readable evidence dataset
  contribution (see `docs/Jair_positioning_and_presubmission.md`).
- The legal OA PDF corpus (`outputs/corpus/`) is manifest-tracked
  (`outputs/corpus/corpus_manifest.csv`, logging source URL, license if
  available, retrieval timestamp, DOI, checksum) but the PDFs themselves
  are excluded from version control; only OA PDFs with a license
  permitting redistribution would be considered for public release
  alongside the manuscript, and only with explicit researcher approval.

## 6. Researcher responsibilities

The researcher is responsible for: supplying manual database exports
under their own institutional access terms; making and recording every
final screening/extraction/appraisal decision; approving all protocol
amendments; verifying venue quality against authoritative sources rather
than accepting AI or database-reputation shortcuts; and ensuring the
final manuscript's AI-use disclosure is accurate and complete at
submission time.
