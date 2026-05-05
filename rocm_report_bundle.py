#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROCm CI/CD Report Bundle
========================
Single-entry-point report generator. Always uses the live generator scripts
and data files next to this file, so any edits to generate_rocm_html.py,
generate_rocm_cicd.py, fetch_rocm_data.py, or rocm_ci_data.py are
automatically picked up.

Usage:
    pip install xlsxwriter

    # Use local snapshot data (rocm_ci_data.py if present, else static defaults):
    python rocm_report_bundle.py

    # Fetch live data from GitHub (requires GITHUB_TOKEN):
    export GITHUB_TOKEN=ghp_...
    python rocm_report_bundle.py

Outputs (written next to this script):
    ROCm_CICD_Comprehensive.html
    ROCm_CICD_Comprehensive.xlsx
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

HERE = Path(__file__).parent

# ── Required source files (must exist alongside this script) ──────────────────
_REQUIRED = [
    "generate_rocm_html.py",
    "generate_rocm_cicd.py",
]

# ── Optional source files (copied if present) ─────────────────────────────────
_OPTIONAL = [
    "fetch_rocm_data.py",
    "rocm_ci_data.py",
]

# ── Local InferenceMAX_rocm directory ─────────────────────────────────────────
_IMAX_DIR = HERE / "InferenceMAX_rocm"


def _check_required() -> None:
    missing = [f for f in _REQUIRED if not (HERE / f).exists()]
    if missing:
        print("ERROR: Required files not found next to rocm_report_bundle.py:", file=sys.stderr)
        for f in missing:
            print(f"  {HERE / f}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    _check_required()

    print("=" * 60)
    print("  ROCm CI/CD Report Generator")
    if token:
        print("  Mode: LIVE (GITHUB_TOKEN detected)")
    else:
        if (HERE / "rocm_ci_data.py").exists():
            print("  Mode: LOCAL SNAPSHOT (rocm_ci_data.py found)")
        else:
            print("  Mode: STATIC DEFAULTS (no rocm_ci_data.py)")
        print("  Tip: set GITHUB_TOKEN to fetch live data instead.")
    print("=" * 60)

    tmp = Path(tempfile.mkdtemp(prefix="rocm_bundle_"))
    try:
        # ── Copy all generator scripts into temp dir ──────────────────────────
        for fname in _REQUIRED:
            shutil.copy2(HERE / fname, tmp / fname)

        for fname in _OPTIONAL:
            src = HERE / fname
            if src.exists():
                shutil.copy2(src, tmp / fname)

        # ── Seed JSON snapshots into temp dir so fetch script can load them ──
        for _snap_name in ("inferencemax_snapshot.json", "therock_ci_snapshot.json"):
            _snap = HERE / _snap_name
            if _snap.exists():
                shutil.copy2(_snap, tmp / _snap_name)

        # ── Copy InferenceMAX_rocm folder so generators can find local data ──
        if _IMAX_DIR.is_dir():
            shutil.copytree(str(_IMAX_DIR), str(tmp / "InferenceMAX_rocm"))
            print(f"\n  Using local InferenceMAX_rocm/ folder for inference data.")

        fetch_script = tmp / "fetch_rocm_data.py"
        has_fetch = fetch_script.exists()
        has_data  = (tmp / "rocm_ci_data.py").exists()
        has_imax  = (tmp / "InferenceMAX_rocm").is_dir()

        if token:
            # ── Live path: fetch_rocm_data.py fetches from GitHub (with local
            # InferenceMAX_rocm as fallback), then calls both generators itself.
            if not has_fetch:
                print("ERROR: fetch_rocm_data.py not found — cannot run in live mode.", file=sys.stderr)
                sys.exit(1)
            print("\nFetching live data from GitHub...")
            subprocess.run(
                [sys.executable, str(fetch_script)],
                check=True,
                cwd=str(tmp),
                env={**os.environ},
            )
        elif has_fetch and has_imax and not has_data:
            # ── No token, no pre-built rocm_ci_data.py, but local InferenceMAX_rocm
            # is present: run fetch_rocm_data.py without a token so it skips
            # GitHub and falls back to the local clone for InferenceMAX data.
            print("\n  No rocm_ci_data.py found — building from local InferenceMAX_rocm/ clone...")
            subprocess.run(
                [sys.executable, str(fetch_script)],
                check=True,
                cwd=str(tmp),
                env={k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"},
            )
        else:
            # ── Snapshot/static path: rocm_ci_data.py already present (or no
            # fetch script available) — run generators directly.
            print("\nGenerating HTML report...")
            subprocess.run(
                [sys.executable, str(tmp / "generate_rocm_html.py")],
                check=True, cwd=str(tmp),
            )

            print("\nGenerating Excel workbook...")
            subprocess.run(
                [sys.executable, str(tmp / "generate_rocm_cicd.py")],
                check=True, cwd=str(tmp),
            )

        # ── Copy outputs (and updated snapshots) next to this bundle script ───
        outputs = [
            "ROCm_CICD_Comprehensive.html",
            "ROCm_CICD_Comprehensive.xlsx",
            "inferencemax_snapshot.json",   # persist updated InferenceMAX snapshot
            "therock_ci_snapshot.json",     # persist updated TheRock CI snapshot
        ]
        # Snapshots are optional — only copied if the fetch script produced/updated them
        _optional_outputs = {"inferencemax_snapshot.json", "therock_ci_snapshot.json"}
        print()
        for fname in outputs:
            src = tmp / fname
            dst = HERE / fname
            if src.exists():
                shutil.copy2(src, dst)
                print(f"  Written: {dst}")
            elif fname not in _optional_outputs:
                print(f"  WARNING: {fname} was not produced", file=sys.stderr)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        print("ERROR: xlsxwriter is not installed.", file=sys.stderr)
        print("Run:  pip install xlsxwriter", file=sys.stderr)
        sys.exit(1)
    main()
