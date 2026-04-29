# -*- coding: utf-8 -*-
"""
create_bundle.py — run this once to produce rocm_report_bundle.py.

rocm_report_bundle.py is a fully self-contained single file that embeds
the current data snapshot (COMPONENTS, InferenceMAX configs, runners, etc.)
and both generator scripts. Anyone can run it with just:

    pip install xlsxwriter
    python rocm_report_bundle.py

No GitHub token, no local clone, no extra files needed.
"""
import base64
import datetime
from pathlib import Path

HERE = Path(__file__).parent

_REQUIRED = [
    ("rocm_ci_data.py",       "data snapshot"),
    ("generate_rocm_html.py", "HTML generator"),
    ("generate_rocm_cicd.py", "Excel generator"),
    ("fetch_rocm_data.py",    "live-data fetcher"),
]

for fname, label in _REQUIRED:
    if not (HERE / fname).exists():
        raise FileNotFoundError(
            f"Missing {fname} ({label}). "
            "Run fetch_rocm_data.py first to generate rocm_ci_data.py."
        )

def _encode(path: Path) -> str:
    """Base64-encode a file so it embeds safely as a Python string literal."""
    raw = path.read_bytes()
    return base64.b64encode(raw).decode("ascii")

data_b64  = _encode(HERE / "rocm_ci_data.py")
html_b64  = _encode(HERE / "generate_rocm_html.py")
xlsx_b64  = _encode(HERE / "generate_rocm_cicd.py")
fetch_b64 = _encode(HERE / "fetch_rocm_data.py")

try:
    from zoneinfo import ZoneInfo as _ZI
    _PT = _ZI("America/Los_Angeles")
except ImportError:
    _PT = datetime.timezone(datetime.timedelta(hours=-7))
_now_pt = datetime.datetime.now(_PT)
snapshot_date = _now_pt.strftime(f"%Y-%m-%d %I:%M %p {_now_pt.strftime('%Z')}")

BUNDLE = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROCm CI/CD Report Bundle
========================
Self-contained single-file report generator.
Data snapshot: {snapshot_date}

Usage:
    pip install xlsxwriter

    # Use baked-in snapshot (no token needed):
    python rocm_report_bundle.py

    # Fetch live data from GitHub (requires GITHUB_TOKEN):
    export GITHUB_TOKEN=ghp_...
    python rocm_report_bundle.py

Outputs (written next to this script):
    ROCm_CICD_Comprehensive.html
    ROCm_CICD_Comprehensive.xlsx

When GITHUB_TOKEN is set, live data is fetched from:
  - ROCm/TheRock          (components, runners, CI tiers)
  - ROCm/rocm-libraries   (library component list)
  - ROCm/rocm-systems     (systems component list)
  - ROCm/InferenceMAX_rocm (AMD benchmark configs)
"""
import os
import sys
import base64
import subprocess
import tempfile
import shutil
from pathlib import Path

HERE = Path(__file__).parent

# ── Embedded source files (base64-encoded to avoid any escaping issues) ───────

_DATA_B64 = (
    "{data_b64}"
)

_HTML_B64 = (
    "{html_b64}"
)

_XLSX_B64 = (
    "{xlsx_b64}"
)

_FETCH_B64 = (
    "{fetch_b64}"
)

def _decode(b64: str) -> str:
    return base64.b64decode(b64).decode("utf-8")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    print("=" * 60)
    print("  ROCm CI/CD Report Generator")
    if token:
        print("  Mode: LIVE (GITHUB_TOKEN detected)")
    else:
        print(f"  Mode: SNAPSHOT (data frozen at {snapshot_date})")
        print("  Tip: set GITHUB_TOKEN to fetch live data instead.")
    print("=" * 60)

    tmp = Path(tempfile.mkdtemp(prefix="rocm_bundle_"))
    try:
        # Always write the generator scripts (fetch_rocm_data.py calls them too)
        (tmp / "generate_rocm_html.py").write_text(_decode(_HTML_B64), encoding="utf-8")
        (tmp / "generate_rocm_cicd.py").write_text(_decode(_XLSX_B64), encoding="utf-8")

        if token:
            # ── Live path: run fetch_rocm_data.py which fetches from GitHub
            # then calls both generators itself, writing the outputs to cwd (tmp).
            print("\\nFetching live data from GitHub...")
            (tmp / "fetch_rocm_data.py").write_text(_decode(_FETCH_B64), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(tmp / "fetch_rocm_data.py")],
                check=True,
                cwd=str(tmp),
                env={{**os.environ}},
            )
        else:
            # ── Snapshot path: use baked-in rocm_ci_data.py, run generators directly
            (tmp / "rocm_ci_data.py").write_text(_decode(_DATA_B64), encoding="utf-8")

            print("\\nGenerating HTML report...")
            subprocess.run(
                [sys.executable, str(tmp / "generate_rocm_html.py")],
                check=True, cwd=str(tmp),
            )

            print("\\nGenerating Excel workbook...")
            subprocess.run(
                [sys.executable, str(tmp / "generate_rocm_cicd.py")],
                check=True, cwd=str(tmp),
            )

        # Copy outputs next to this bundle script
        outputs = [
            "ROCm_CICD_Comprehensive.html",
            "ROCm_CICD_Comprehensive.xlsx",
        ]
        print()
        for fname in outputs:
            src = tmp / fname
            dst = HERE / fname
            if src.exists():
                shutil.copy2(src, dst)
                print(f"  Written: {{dst}}")
            else:
                print(f"  WARNING: {{fname}} was not produced", file=sys.stderr)

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
'''

out = HERE / "rocm_report_bundle.py"
out.write_text(BUNDLE, encoding="utf-8")

size_kb = out.stat().st_size / 1024
print(f"Bundle written : {out}")
print(f"Size           : {size_kb:.0f} KB")
print(f"Snapshot date  : {snapshot_date}")
print()
print("Share rocm_report_bundle.py with your manager.")
print()
print("  Snapshot mode (no token needed):")
print("    pip install xlsxwriter")
print("    python rocm_report_bundle.py")
print()
print("  Live mode (fetches fresh data from GitHub):")
print("    export GITHUB_TOKEN=ghp_...")
print("    pip install xlsxwriter")
print("    python rocm_report_bundle.py")
