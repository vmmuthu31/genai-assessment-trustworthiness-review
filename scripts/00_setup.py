#!/usr/bin/env python3
"""Phase 0 environment setup and readiness check.

Safe to run immediately: creates required directories, ensures .env exists
(copied from .env.example with a warning if missing), checks that all
required third-party packages are importable, and prints a readiness
report. Makes no network calls.

Usage:
    python scripts/00_setup.py
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROJECT_ROOT,
    REQUIRED_DIRS,
    ensure_required_dirs,
)

REQUIRED_PACKAGES = [
    "pandas",
    "numpy",
    "yaml",
    "dotenv",
    "requests",
    "tenacity",
    "rapidfuzz",
    "unidecode",
    "openpyxl",
    "xlsxwriter",
    "pypdf",
    "pytest",
    "rich",
    "click",
]

REQUIRED_ENV_VARS = ["OPENALEX_MAILTO", "CROSSREF_MAILTO"]


def ensure_env_file() -> str:
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    if env_path.exists():
        return "exists"
    if example_path.exists():
        shutil.copy(example_path, env_path)
        return "copied_from_example"
    return "missing_no_example"


def load_dotenv_if_available() -> bool:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    return True


def check_packages() -> dict[str, bool]:
    status = {}
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            status[pkg] = True
        except ImportError:
            status[pkg] = False
    return status


def check_env_vars() -> dict[str, bool]:
    return {var: bool(os.environ.get(var)) for var in REQUIRED_ENV_VARS}


def print_report_table(title: str, rows: list[tuple[str, str]]) -> None:
    print(f"\n{title}")
    width = max((len(r[0]) for r in rows), default=10)
    for name, status in rows:
        print(f"  {name.ljust(width)}  {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    print("=" * 70)
    print("EvalBot JAIR PRISMA Review -- Phase 0 setup / readiness check")
    print("=" * 70)

    created = ensure_required_dirs()
    if created:
        print(f"\nCreated {len(created)} missing directories:")
        for d in created:
            print(f"  + {d.relative_to(PROJECT_ROOT)}")
    else:
        print(f"\nAll {len(REQUIRED_DIRS)} required directories already exist.")

    env_status = ensure_env_file()
    print(f"\n.env status: {env_status}")
    if env_status == "copied_from_example":
        print("  WARNING: .env was created from .env.example. Fill in "
              "OPENALEX_MAILTO / CROSSREF_MAILTO before Phase 1.")
    elif env_status == "missing_no_example":
        print("  WARNING: no .env or .env.example found. Create .env manually.")

    dotenv_loaded = load_dotenv_if_available()
    if not dotenv_loaded:
        print("  WARNING: python-dotenv not importable; .env was not loaded "
              "into the environment for this check.")

    pkg_status = check_packages()
    print_report_table(
        "Package import check:",
        [(pkg, "OK" if ok else "MISSING") for pkg, ok in pkg_status.items()],
    )
    missing_pkgs = [p for p, ok in pkg_status.items() if not ok]

    env_var_status = check_env_vars()
    print_report_table(
        "Environment variable check:",
        [(var, "SET" if ok else "NOT SET") for var, ok in env_var_status.items()],
    )
    missing_vars = [v for v, ok in env_var_status.items() if not ok]
    if missing_vars:
        print(f"  WARNING: {', '.join(missing_vars)} not set. Required before "
              "any live Phase 1 fetch (--live) can run politely.")

    print("\n" + "=" * 70)
    if missing_pkgs:
        print("NOT READY: install missing packages first: "
              "pip install -r requirements.txt")
        print(f"Missing: {', '.join(missing_pkgs)}")
        return 1

    print("READY. Directories present, .env present, all packages importable.")
    if missing_vars:
        print("Package/directory checks pass, but mailto env vars are missing "
              "-- fetch scripts will still run with --live but without the "
              "polite pool.")
    print("Phase 1 (discovery) scripts remain dry-run by default -- pass "
          "--live to execute real network calls once approved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
