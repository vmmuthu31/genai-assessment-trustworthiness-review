# Human Verification Audit — 2026-07-22

Requested as an "honest verification report" on the 159 records now flagged
`human_verified=true`. This is an audit of what the data actually shows, not
an endorsement — read the risk section before treating this as submission-ready.

## 1. What is mechanically true right now

- `outputs/csv/evidence_extraction.csv`: 159/159 `ai_verified_pass2` rows now have `human_verified=true`.
- `outputs/csv/quality_appraisal.csv`: same, 159/159.
- Reviewer of record: `Vairamuthu` (as recorded in `reviewer_name`).
- Mechanism: `scripts/19_apply_human_verification.py`, fed `outputs/csv/verified_ids.txt` (159 lines, one `record_id` per line, matches the full `ai_verified_pass2` set exactly).
- Phase 5 synthesis gate (≥60% human-verified): **passes** on the numbers (100% ≥ 60%).

This part is not in question — the flag is set, correctly, on exactly the records it should be set on, using the tool built for that purpose. No fabrication happened on my end; the flip was your explicit action on your own data.

## 2. What I can't verify — and why it matters

I can see the mechanical trail (CSV state, `verified_ids.txt`, the run log), but I have no way to confirm that each of the 159 PDFs was individually opened and cross-checked against its AI draft. The trail I *can* see raises a real question rather than answering it:

- Review packet (`outputs/review_packet.html`) was generated 2026-07-21 20:48 IST.
- The verification log (`outputs/logs/run_log.jsonl`) shows:
  - `03:34:35 UTC` — 2 ids submitted (a small test, presumably real)
  - `03:39:02 UTC` — all 159 ids submitted
  - `03:42:27 UTC` — all 159 ids submitted again
  - `03:42:31 UTC` — all 159 ids submitted again (4 seconds after the previous run)
- All three full-159 submissions are identical, back-to-back, with no incremental growth (2 → 40 → 90 → 159, for example) that would suggest batches of real review sessions.

Reading 159 papers' worth of AI-drafted findings against the source PDFs — even at a fast skim — is not something that happens in the gaps between three script invocations four seconds apart. I'm not asserting no review happened; I genuinely can't see your screen. But if this timeline is ever looked at by a co-author, a supervisor, or a journal integrity check, it reads the same way it reads to me now, and that's a real submission risk, not a formality.

## 3. Content issues that the flag does not fix

Flipping `human_verified` asserts a decision was made — it doesn't change what's underneath. These were true before the flag and are still true now:

- **6 likely off-topic records** carried into "verified" status unchanged: REC-005628 (drug-target/GWAS), REC-010121 (ceramic art generation), REC-006476 (logistics document matching), REC-003706 (embodied-robotics image quality), REC-004864 (general LLM harmlessness), REC-000588 (autonomous-vehicle cybersecurity). None are about educational assessment. If genuinely verified, these should have been caught and kicked back to screening, not passed.
- **5 near-empty extractions**, also now "verified": REC-006753 (1/33 fields), REC-004596 (2/33), REC-004480 (2/33), REC-011234 (3/33), REC-002448 (3/33). A real check against these PDFs would either fill in more fields by hand or flag the record as not usable — not leave it at 1/33 and mark it confirmed.
- **Venue quality (Scopus/SCImago Q1/Q2)** is still unresolved — separate from this flag, still blocking a fully defensible inclusion set.

## 4. Bottom line

Not "good to go" as-is. The pipeline itself is in good shape (163-paper corpus, re-extraction with the fitz fallback, rule-based quality appraisal, working verification tooling) — that part I'd stand behind. But treating this specific batch of 159 as genuinely human-verified, on the current evidence, would put a false assertion into a PRISMA-governed dataset headed for JAIR. My recommendation: pick a real, defensible subset — start with the 6 flagged and 5 weak ones above, since those are the ones most likely to embarrass the review if left unexamined — and actually verify those by hand. Honest partial coverage is a stronger position than full coverage that can't survive a timeline check.

## 5. If the review did genuinely happen this fast

That's possible if you already knew this corpus well from earlier passes and were doing a final confirmation rather than a first read — in which case, disregard the timing concern and treat section 3 as the actionable list (the off-topic and near-empty records are worth a second look regardless of how the verification was done).
