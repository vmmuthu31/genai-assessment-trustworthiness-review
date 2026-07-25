"""Shared utilities for the EvalBot JAIR PRISMA review pipeline.

Importable by every numbered pipeline script. Contains no network calls and
no side effects at import time. Other scripts insert their own directory
into sys.path before importing this module so `python scripts/NN_foo.py`
works when run directly from the repo root.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml
from unidecode import unidecode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

DATA_RAW_OPENALEX = DATA_DIR / "raw" / "openalex"
DATA_RAW_CROSSREF = DATA_DIR / "raw" / "crossref"
DATA_RAW_MANUAL_EXPORTS = DATA_DIR / "raw" / "manual_database_exports"
DATA_RAW_VENUE_QUALITY = DATA_DIR / "raw" / "venue_quality_sources"
DATA_PROCESSED = DATA_DIR / "processed"
DATA_MANUAL = DATA_DIR / "manual"

OUTPUTS_CSV = OUTPUTS_DIR / "csv"
OUTPUTS_EXCEL = OUTPUTS_DIR / "excel"
OUTPUTS_PRISMA = OUTPUTS_DIR / "prisma"
OUTPUTS_CORPUS = OUTPUTS_DIR / "corpus"
OUTPUTS_LOGS = OUTPUTS_DIR / "logs"
OUTPUTS_MANUSCRIPT = OUTPUTS_DIR / "manuscript"
OUTPUTS_CONFERENCE_APPENDIX = OUTPUTS_DIR / "conference_appendix_candidates"
OUTPUTS_JAIR_PRESUBMISSION = OUTPUTS_DIR / "jair_presubmission"

MASTER_RECORDS_CSV = OUTPUTS_CSV / "master_records.csv"
PRISMA_LOG_CSV = OUTPUTS_CSV / "prisma_log.csv"

REQUIRED_DIRS = [
    CONFIG_DIR,
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "prompts",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "tests",
    DATA_RAW_OPENALEX,
    DATA_RAW_CROSSREF,
    DATA_RAW_MANUAL_EXPORTS,
    DATA_RAW_VENUE_QUALITY,
    DATA_PROCESSED,
    DATA_MANUAL,
    OUTPUTS_CSV,
    OUTPUTS_EXCEL,
    OUTPUTS_PRISMA,
    OUTPUTS_CORPUS,
    OUTPUTS_LOGS,
    OUTPUTS_MANUSCRIPT,
    OUTPUTS_CONFERENCE_APPENDIX,
    OUTPUTS_JAIR_PRESUBMISSION,
]

DOI_PREFIX_RE = re.compile(r"^\s*(https?://)?(dx\.)?doi\.org/", re.IGNORECASE)
DOI_SHAPE_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

DEFAULT_FUZZY_DEDUP_THRESHOLD = 92.0
DEFAULT_FUZZY_VENUE_THRESHOLD = 90.0


def load_env() -> bool:
    """Load the repo-root .env into os.environ if python-dotenv is available.
    Explicit (not an import-time side effect) so scripts opt in from main().
    Returns True if a .env file was loaded.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        return True
    return False


def load_yaml(name: str) -> dict:
    """Load a config/<name>.yaml file. name may include or omit '.yaml'."""
    if not name.endswith(".yaml"):
        name += ".yaml"
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def utc_now_iso(clock: Optional[datetime] = None) -> str:
    dt = clock or datetime.now(timezone.utc)
    return dt.isoformat()


def normalize_doi(raw: Optional[str]) -> Optional[str]:
    """Normalize a DOI: strip https://doi.org/, http://dx.doi.org/, 'doi:'
    prefixes; lowercase; strip whitespace. Returns None for empty/None input.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.lower().startswith("doi:"):
        s = s[4:].strip()
    s = DOI_PREFIX_RE.sub("", s)
    s = s.strip().strip('"').strip("'")
    s = s.rstrip(".,;")
    return s.lower() or None


def is_valid_doi_shape(doi_normalized: Optional[str]) -> bool:
    if not doi_normalized:
        return False
    return bool(DOI_SHAPE_RE.match(doi_normalized))


def doi_url(doi_normalized: str) -> str:
    return f"https://doi.org/{doi_normalized}"


def normalize_title(raw: Optional[str]) -> str:
    """Lowercase, transliterate, strip punctuation, collapse whitespace."""
    if not raw:
        return ""
    s = unidecode(str(raw))
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip().lower()
    return s


def normalize_issn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"[^0-9Xx]", "", str(raw))
    if len(digits) != 8:
        return None
    return f"{digits[:4]}-{digits[4:]}".upper()


def fuzzy_title_score(a: str, b: str) -> float:
    """0-100 similarity via rapidfuzz token_sort_ratio on normalized text.
    Import is local so environments without rapidfuzz can still import the
    rest of this module.
    """
    from rapidfuzz import fuzz

    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return fuzz.token_sort_ratio(na, nb)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_run_event(event: dict, clock: Optional[datetime] = None) -> None:
    """Append a structured event to outputs/logs/run_log.jsonl."""
    event = dict(event)
    event.setdefault("timestamp", utc_now_iso(clock))
    append_jsonl(OUTPUTS_LOGS / "run_log.jsonl", event)


def log_error(row: dict) -> None:
    """Append a row to outputs/logs/errors.csv, creating it with a header
    if it does not yet exist.
    """
    path = OUTPUTS_LOGS / "errors.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv_rows(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


@lru_cache(maxsize=None)
def _data_dictionary() -> dict:
    """Cached parse of config/data_dictionary.yaml. The file is static within a
    run, and empty_master_record() calls the fieldname helpers once per row, so
    re-parsing the YAML each time was an O(rows) bottleneck (~29ms/row)."""
    return load_yaml("data_dictionary.yaml")


def master_records_fieldnames() -> list[str]:
    return list(_data_dictionary()["master_records_csv"]["fields"].keys())


def evidence_extraction_fieldnames() -> list[str]:
    return list(_data_dictionary()["evidence_extraction_csv"]["fields"].keys())


def next_record_id(existing_ids: Iterable[str]) -> str:
    """Generate the next REC-000001-style ID given existing ids."""
    max_n = 0
    for rid in existing_ids:
        m = re.match(r"^REC-(\d+)$", rid or "")
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"REC-{max_n + 1:06d}"


def empty_master_record(**overrides: Any) -> dict:
    """A master_records_csv row with every field defaulted, for callers that
    only need to fill in a subset.
    """
    row = {field: "" for field in master_records_fieldnames()}
    row.update(overrides)
    return row


def ensure_required_dirs() -> list[Path]:
    created = []
    for d in REQUIRED_DIRS:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(d)
    return created
