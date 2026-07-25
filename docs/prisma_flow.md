# PRISMA 2020 Flow Diagram — Trustworthy Multimodal Gen-AI for Educational Assessment

## Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        IDENTIFICATION                                │
├─────────────────────────────────────────────────────────────────────┤
│  Records identified through database searching (n = 13,854)        │
│    • OpenAlex (5 families): 11,554                                  │
│    • Crossref (5 families): 2,300                                   │
│  Duplicate records removed (n = 1,826)                              │
│  ─────────────────────────────────────────────────────────────────  │
│  Records after deduplication (n = 12,028)                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SCREENING                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Records screened by relevance + OA shortlisting (n = 400)         │
│    • Weighted relevance scoring (axes A-D)                         │
│    • Open-access priority (gold > hybrid > green > bronze)         │
│  Records excluded by screening (n = 0)                             │
│    • (Trusted relevance pre-filter; all 400 met inclusion)        │
│  ─────────────────────────────────────────────────────────────────  │
│  Records advancing to eligibility (n = 400)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ELIGIBILITY (PDF RETRIEVAL)                    │
├─────────────────────────────────────────────────────────────────────┤
│  Full-text articles assessed for eligibility (n = 400)             │
│    • Gold OA: 213                                                   │
│    • Hybrid OA: 73                                                  │
│    • Green OA: 77                                                   │
│    • Bronze OA: 22                                                  │
│    • Licensed: 15                                                   │
│  ─────────────────────────────────────────────────────────────────  │
│  Reports for which full-text was obtained (n = 157)                │
│  Reports for which full-text could not be obtained (n = 243) —     │
│    all 243 are within the 336 included (336 = 93 synthesis + 243)  │
│    • Publisher bot protection / paywall (MDPI, ACM, etc.)         │
│    • doi.org redirects to blocked publishers                       │
│  ─────────────────────────────────────────────────────────────────  │
│  Reports assessed for full-text eligibility (n = 157)              │
│  Reports excluded at full-text assessment (n = 64)                 │
│    • PA-002 (12): wrong document type (E04) x2; no educational-    │
│      assessment setting (E09) x10                                  │
│    • PA-004 (52): no learner as the assessment target (E09) x49;   │
│      editorial + off-topic (E04+E09) x1; secondary review, not a   │
│      primary study (E10) x1; no generative-AI component (E08) x1   │
│    • (relevance-pre-filter false positives, caught only once full  │
│      text was read or on protocol-literal re-audit — see PA-002    │
│      and PA-004 in protocol_amendments.md for per-record reason    │
│      codes + quoted evidence)                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  Reports included in quantitative/qualitative synthesis (n = 93)   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTRACTION                                   │
├─────────────────────────────────────────────────────────────────────┤
│  Reports with data extracted (n = 157)                               │
│    • Rule-based extraction (ai_verified_pass2, pipeline_stage=      │
│      AI_VERIFIED) — human researcher confirmation still pending    │
│      for all except the 64 excluded above                          │
│  Reports pending extraction (no PDF, n = 243)                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Numbers Summary (Corpus Freeze v1.2, supersedes v1.1)

Every row below reconciles exactly: 400 = 336 + 64; 157 = 93 + 64;
336 = 93 + 243. See PA-003 (a bookkeeping fix — a phantom, never-screened
duplicate record), **PA-004** (a second-pass protocol-conformance
audit that found 52 additional false positives beyond PA-002's original
12), and **PA-005** (a wrong-PDF-extraction bug fix: 2 records
re-extracted from their correct source, 1 record with no available
correct source reset to pending, 94 → 93) in `protocol_amendments.md`.

| Stage | Count | Notes |
|-------|-------|-------|
| Identified | 13,854 | OpenAlex + Crossref |
| After dedup | 12,028 | 1,826 duplicates removed |
| Screened (title+abstract) | 400 | Relevance + OA shortlist |
| Passed title/abstract screening | 400 | Trusted pre-filter at this stage |
| PDFs retrieved / full text extracted | 157 | 39.25% of the 400 screened; includes the 64 later excluded (caught only on full-text read / protocol re-audit) |
| Not retrieved (within the 336 included) | 243 | Publisher blocks / no legal OA (unchanged, out of scope this cycle) plus 1 (`REC-001985`) reset by PA-005; documented in `outputs/csv/missing_papers_for_manual_download.csv` |
| Excluded at full-text assessment | 64 | PA-002 (12) + PA-004 (52) — see breakdown above; unaffected by PA-005 |
| **Included in synthesis** | **93** | Frozen corpus for Phase 5 (Corpus Freeze v1.2) |
| Quality-appraisal dimensions rated (Yes/No/Partial/NR/NA) | 93 × 14 | scripts/18, rule-based, `pipeline_stage=AI_VERIFIED` |
| Screening decisions researcher-confirmed | 64 (the exclusions) | Distinct from extraction/appraisal confirmation below — this is confirmation of the *include/exclude call*, not of extracted field values |
| Extraction/appraisal records at `pipeline_stage=RESEARCHER_CONFIRMED` | **0 of 93** | All 93 included records still await individual researcher confirmation of their extracted evidence — see `outputs/review_packet.html` and `scripts/19_apply_human_verification.py` |

Note on the 64 exclusions: PRISMA 2020 permits exclusion at either the
title/abstract or full-text stage depending on when the reason was
actually discovered. All 64 passed the automated title/abstract relevance
pre-filter (a false-negative at that stage) and were only caught once
full text was read (PA-002) or on a protocol-literal second-pass audit
(PA-004) — so they are reported here, in the full-text-assessment box,
which is the accurate and PRISMA-compliant place for them. The manuscript
should disclose PA-004 transparently as a methodological strength (a
secondary protocol-conformance audit), not a silent renumbering — see
PA-004's disclosure directive in `protocol_amendments.md`.

## Justification for Not Retrieved (243)

The 243 reports for which PDFs could not be retrieved were blocked by:

1. **Publisher bot protection** — Tandfonline, MDPI, ACM, Wiley, and other publishers
   return 403 errors or HTML pages instead of PDFs for automated requests.
2. **doi.org redirects** — many records had doi.org URLs that redirected to
   blocked publisher pages.
3. **No direct PDF serving** — Many gold OA publishers serve PDFs only through
   JavaScript-rendered pages (CAPTCHAs, cookie consent).
4. **One case (`REC-001985`)** is different in kind: the record was
   genuinely extracted at one point, but from the wrong paper (a
   `corpus_manifest.csv` bug — see PA-005). No correct legally-obtained OA
   copy of the true paper has ever been found; it is included here as
   "not retrieved" rather than "extraction failed," since no usable PDF of
   the correct paper currently exists in this repository.

This is a standard limitation in systematic reviews relying on automated
corpus retrieval. All 243 non-retrieved records are documented in
`outputs/csv/missing_papers_for_manual_download.csv` (regenerated
2026-07-22 from the current `extraction_status=pending` set) with their
original URLs for potential manual acquisition where available.
