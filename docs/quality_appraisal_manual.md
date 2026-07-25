# Quality Appraisal Manual

Operational guidance for applying the rubric in `config/quality_appraisal.yaml`
to each included study, producing rows in `outputs/csv/quality_appraisal.csv`.

## 1. Scale

Every one of the 14 dimensions is scored on a four-point scale:

- **strong** — explicit, rigorous treatment with verifiable detail (e.g.,
  a named metric, a described protocol, a reported number).
- **adequate** — present but with limited detail or partial rigor (e.g.,
  mentioned and briefly described, but no quantitative result or no
  methodological detail to assess rigor).
- **weak** — mentioned only superficially, or with a clear methodological
  gap the authors themselves acknowledge or that is evident from the text
  (e.g., "we informally checked for hallucinations" with no protocol or
  metric).
- **NR (Not Reported)** — the dimension is not addressed at all in the
  paper; cannot be determined from the text.

## 2. Worked example — `hallucination_testing`

*Paper excerpt (illustrative, not a real citation):* "To assess
hallucination, we manually reviewed 50 randomly sampled model outputs and
counted instances where the generated justification cited rubric text not
present in the answer. We report a hallucination rate of 8% (4/50) and
provide the annotation protocol in Appendix B."

- Definition present? Yes — hallucination is operationalized as citing
  non-existent rubric text.
- Test/protocol described? Yes — manual review of a random sample, with an
  appendix protocol.
- Metric reported? Yes — 8% (4/50).
- **Score: strong.**

Contrast: "We did not observe significant hallucination in our
qualitative review." — no definition, no protocol, no metric, no sample
size. **Score: weak** (present as a claim, but not rigorous or
verifiable) — not NR, because the topic is at least mentioned; NR is
reserved for dimensions the paper does not address *at all*.

## 3. Distinguishing "weak" from "NR"

This is the most common appraiser error. The test: **could a careful
reader locate a sentence about this dimension anywhere in the paper?**

- If yes, and that sentence lacks a protocol/metric/detail → **weak**.
- If no such sentence exists anywhere (including appendices/supplementary
  material, if accessible) → **NR**.

Do not infer "weak" from silence, and do not infer "strong" from a
dimension being adjacent to something well-reported (e.g., strong
calibration reporting does not imply strong fairness reporting — score
each dimension independently from its own textual evidence).

## 4. Evidence anchoring

Every non-NR score should be accompanied (in the appraisal notes / a
dedicated evidence column, mirroring the extraction sheet's
`evidence_page_section` convention) by a page/section pointer to where
the judgment is grounded, so a second reader — including the researcher
performing human sign-off — can verify the call without re-reading the
whole paper.

## 5. Human sign-off requirement

Per `config/quality_appraisal.yaml: overall_appraisal`, the Quality
Appraisal Agent (`prompts/09_quality_appraiser.md`) produces AI-draft
scores and evidence pointers only. No composite "overall risk" judgment
is computed automatically, and no appraisal record is used in Phase 5
synthesis until the researcher has reviewed and approved it in the
`Quality_Appraisal` workbook sheet, mirroring the same AI-draft/human-
approval pattern used throughout screening and extraction.
