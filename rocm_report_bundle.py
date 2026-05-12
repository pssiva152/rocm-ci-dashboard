#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROCm CI/CD Report Bundle
========================
Single-entry-point report generator. Always uses the live generator scripts
and data files next to this file, so any edits to generate_rocm_html.py,
generate_rocm_cicd.py, fetch_rocm_data.py, or rocm_ci_data.py are
automatically picked up.

Two modes:

    LIVE     — selected by default when fetch_rocm_data.py exists alongside
               this script. Performs anonymous git clones of the public ROCm
               repos and an SSH clone of ROCm/InferenceMAX_rocm. Falls back
               automatically to the JSON snapshots on any clone failure.

    SNAPSHOT — selected when fetch_rocm_data.py is absent (or `--snapshot`
               is passed). Skips all network access and uses the committed
               rocm_ci_data.py / *.json snapshot files only.

Usage:
    pip install xlsxwriter
    python rocm_report_bundle.py              # LIVE (clones), falls back to snapshot
    python rocm_report_bundle.py --snapshot   # snapshot-only, no network access

Prerequisites for LIVE mode:
    git installed and on PATH
    SSH key registered with GitHub (only needed for the InferenceMAX_rocm clone)

Outputs (written next to this script):
    ROCm_CICD_Comprehensive.html
    ROCm_CICD_Comprehensive.xlsx
    therock_ci_snapshot.json     (refreshed when LIVE clones succeed)
    inferencemax_snapshot.json   (refreshed when LIVE clones succeed)
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
    snapshot_only = ("--snapshot" in sys.argv) or ("-s" in sys.argv)

    _check_required()

    has_fetch = (HERE / "fetch_rocm_data.py").exists()
    has_data  = (HERE / "rocm_ci_data.py").exists()

    print("=" * 60)
    print("  ROCm CI/CD Report Generator")
    if snapshot_only:
        print("  Mode: SNAPSHOT-ONLY (--snapshot flag; skipping all clones)")
    elif has_fetch:
        print("  Mode: LIVE (anonymous git clones; SSH for InferenceMAX_rocm)")
        print("        falls back to JSON snapshots on any clone failure")
    else:
        print("  Mode: SNAPSHOT (fetch_rocm_data.py not found alongside)")
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

        run_live = has_fetch and not snapshot_only
        if run_live:
            # ── LIVE: fetch_rocm_data.py performs the clones, parses the YAMLs,
            # writes a fresh rocm_ci_data.py + snapshots, and calls both
            # generators itself. Snapshots are used automatically as fallback
            # if any clone fails.
            print("\nFetching live data via git clones...")
            subprocess.run(
                [sys.executable, str(fetch_script)],
                check=True,
                cwd=str(tmp),
                env={**os.environ},
            )
        else:
            # ── SNAPSHOT-only: skip the fetcher entirely, run generators
            # directly against the committed rocm_ci_data.py (or static
            # defaults baked into the generators if rocm_ci_data.py is absent).
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
