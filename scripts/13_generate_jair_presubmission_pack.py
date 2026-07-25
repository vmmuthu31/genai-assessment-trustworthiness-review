#!/usr/bin/env python3
"""Scaffold the JAIR pre-submission pack: five template files under
outputs/jair_presubmission/, created with section headers only, if they do
not already exist. Idempotent — re-running never overwrites researcher edits.

No network calls.

Usage:
    python scripts/13_generate_jair_presubmission_pack.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OUTPUTS_JAIR_PRESUBMISSION, load_yaml, log_run_event  # noqa: E402

TEMPLATES: dict[str, str] = {
    "contribution_statement.md": """# Contribution Statement

## Primary Contributions

- (Fill in: what this review adds that no existing review provides.)

## Methodological Contributions

- (Fill in: PRISMA 2020 rigor, venue quality gating, AI-assisted screening with mandatory human approval, etc.)

## Evidence Contributions

- (Fill in: synthesis of trustworthiness dimensions across included studies.)

## Downstream Contributions

- (Fill in: how this review motivates EvalBench / EvalBot / the teacher-deferral platform.)
""",
    "closest_jair_papers.md": """# Closest JAIR Papers

List of the most closely related papers previously published in JAIR, with a
short note on how this review's scope differs from each.

| Citation | Year | Relation to this review | Key difference |
|---|---|---|---|
| (Fill in) | | | |
""",
    "originality_and_overlap_statement.md": """# Originality and Overlap Statement

## Statement

(Fill in: explicit statement that this is original work, not a resubmission
or substantial overlap with any prior publication by the authors or others.)

## Overlap Check Log

| Source checked | Date | Outcome |
|---|---|---|
| (Fill in) | | |
""",
    "novelty_matrix.md": """# Novelty Matrix

Matrix comparing this review against the closest existing reviews/surveys
along key axes (scope, modality coverage, trustworthiness dimensions,
venue-quality gating, PRISMA rigor, target application).

| Dimension | This Review | Closest Prior Work 1 | Closest Prior Work 2 |
|---|---|---|---|
| Scope | | | |
| Modalities covered | | | |
| Trustworthiness dimensions | | | |
| Venue quality gating | | | |
| PRISMA 2020 compliance | | | |
| Target application | | | |
""",
    "manuscript_structure.md": """# Manuscript Structure (JAIR)

## 1. Introduction
- Motivation, research questions (see config/protocol.yaml)

## 2. Related Work / Positioning
- See closest_jair_papers.md, novelty_matrix.md

## 3. Methods
- PRISMA 2020 protocol, search strategy, eligibility criteria, venue quality
  gating, screening process, extraction process, quality appraisal

## 4. Results
- PRISMA flow diagram, descriptive statistics, RQ1-RQ6 synthesis

## 5. Discussion
- Evidence gaps, implications for EvalBench / EvalBot / teacher-deferral platform

## 6. Limitations

## 7. Conclusion

## Appendices
- Search strings, excluded-study log, conference appendix candidates
""",
}


def scaffold_file(path: Path, content: str) -> bool:
    """Write `content` to `path` only if it does not already exist. Returns
    True if the file was created, False if it already existed (untouched).
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    created = []
    skipped = []
    for filename, content in TEMPLATES.items():
        path = OUTPUTS_JAIR_PRESUBMISSION / filename
        if scaffold_file(path, content):
            created.append(filename)
        else:
            skipped.append(filename)

    if created:
        print(f"Created {len(created)} new template file(s):")
        for f in created:
            print(f"  + {f}")
    if skipped:
        print(f"Skipped {len(skipped)} file(s) already present (left untouched):")
        for f in skipped:
            print(f"  = {f}")

    log_run_event({
        "stage": "generate_jair_presubmission_pack",
        "created": created,
        "skipped": skipped,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
