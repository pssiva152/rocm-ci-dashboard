# -*- coding: utf-8 -*-
"""
Fetch live CI/CD data from ROCm GitHub repos and regenerate HTML + Excel reports.

Usage:
    python fetch_rocm_data.py

Optional env var:
    GITHUB_TOKEN=ghp_...   Raises API limit from 60 to 5000 requests/hour.

Outputs (written to project folder alongside this script):
    rocm_ci_data.py          — generated Python data module (intermediate)
    ROCm_CICD_Comprehensive.html
    ROCm_Components_CICD.xlsx
"""

import base64
import json
import os
import sys
import textwrap
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
TOKEN = os.environ.get("GITHUB_TOKEN", "")


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "rocm-ci-fetcher/1.0"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def gh_file(owner: str, repo: str, path: str) -> str:
    """Fetch a single file from GitHub and return its decoded text content."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return base64.b64decode(data["content"]).decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"  WARN: could not fetch {owner}/{repo}/{path} — {e.code} {e.reason}")
        return ""


def gh_dir(owner: str, repo: str, path: str) -> list[str]:
    """List directory entries (names only, directories only unless all=True)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.loads(r.read())
        return [item["name"] for item in items if item["type"] == "dir"]
    except urllib.error.HTTPError as e:
        print(f"  WARN: could not list {owner}/{repo}/{path} — {e.code} {e.reason}")
        return []


# ── Phase 1: Fetch raw data ───────────────────────────────────────────────────

def fetch_all() -> dict:
    print("Fetching data from GitHub...")

    print("  [1/6] amdgpu_family_matrix.py")
    matrix_src = gh_file("ROCm", "TheRock",
                         "build_tools/github_actions/amdgpu_family_matrix.py")

    print("  [2/6] BUILD_TOPOLOGY.toml")
    topology_src = gh_file("ROCm", "TheRock", "BUILD_TOPOLOGY.toml")

    print("  [3/6] .gitmodules (TheRock)")
    gitmodules_src = gh_file("ROCm", "TheRock", ".gitmodules")

    print("  [4/6] rocm-libraries projects/")
    lib_projects = gh_dir("ROCm", "rocm-libraries", "projects")

    print("  [5/6] rocm-systems projects/")
    sys_projects = gh_dir("ROCm", "rocm-systems", "projects")

    print("  [6/6] ci_nightly.yml (schedule time)")
    nightly_yml = gh_file("ROCm", "TheRock", ".github/workflows/ci_nightly.yml")

    return dict(
        matrix_src=matrix_src,
        topology_src=topology_src,
        gitmodules_src=gitmodules_src,
        lib_projects=lib_projects,
        sys_projects=sys_projects,
        nightly_yml=nightly_yml,
    )


# ── Phase 2: Parse GPU family matrix ─────────────────────────────────────────

def parse_matrix(matrix_src: str) -> dict:
    """
    Execute amdgpu_family_matrix.py in a sandbox and extract the three tier dicts.
    Returns {"presubmit": {...}, "postsubmit": {...}, "nightly": {...}}.
    """
    ns: dict = {"random": __import__("random")}
    try:
        exec(matrix_src, ns)  # noqa: S102 — trusted internal AMD repo file
    except Exception as e:
        print(f"  WARN: could not exec amdgpu_family_matrix.py — {e}")
        return {"presubmit": {}, "postsubmit": {}, "nightly": {}}
    return {
        "presubmit":  ns.get("amdgpu_family_info_matrix_presubmit", {}),
        "postsubmit": ns.get("amdgpu_family_info_matrix_postsubmit", {}),
        "nightly":    ns.get("amdgpu_family_info_matrix_nightly", {}),
    }


# ── Phase 3: Parse BUILD_TOPOLOGY.toml ───────────────────────────────────────

def parse_topology(topology_src: str) -> dict:
    """Return the raw TOML dict, or {} if parsing fails."""
    if not topology_src:
        return {}
    try:
        return tomllib.loads(topology_src)
    except Exception as e:
        print(f"  WARN: could not parse BUILD_TOPOLOGY.toml — {e}")
        return {}


# ── Phase 4: Build RUNNER_DATA ────────────────────────────────────────────────
#
# Format (10 fields, matching generate_rocm_cicd.py):
#   label, platform, os_distro, location, phys_machines,
#   gpu_family, isa, count, used_at, notes

def build_runner_data(matrices: dict) -> list[tuple]:
    """
    Build RUNNER_DATA from the live amdgpu_family_matrix + static supplemental rows
    for build pools and special runners not in the GPU family matrix.
    """
    seen: set[str] = set()
    rows: list[tuple] = []

    def add(label, platform, os_distro, location, phys, gpu_family, isa, count, used_at, notes):
        if label not in seen:
            seen.add(label)
            rows.append((label, platform, os_distro, location, phys,
                         gpu_family, isa, count, used_at, notes))

    # ── GPU runners derived from the live matrix ──────────────────────────────
    tier_used = {
        "presubmit":  "PR · postsubmit · nightly",
        "postsubmit": "Postsubmit · nightly",
        "nightly":    "Nightly only",
    }
    # GPU family → hardware details (static supplement, not in the matrix file)
    _hw: dict[str, dict] = {
        "gfx94X-dcgpu":  dict(gpu="MI300X / MI325X",   isa="gfx942 / gfx94X",   count="1"),
        "gfx950-dcgpu":  dict(gpu="MI355X",             isa="gfx950",             count="1"),
        "gfx90a":        dict(gpu="MI200",              isa="gfx90a",             count="1"),
        "gfx103X-all":   dict(gpu="RX 6000 (RDNA2)",   isa="gfx1030 / gfx103X",  count="1"),
        "gfx110X-all":   dict(gpu="Navi3 / RX 7900",   isa="gfx1100/1101",       count="1"),
        "gfx1150":       dict(gpu="Strix Point",        isa="gfx1150",            count="1"),
        "gfx1151":       dict(gpu="Strix Halo",         isa="gfx1151",            count="1"),
        "gfx1153":       dict(gpu="Krackan Point",      isa="gfx1153",            count="1"),
        "gfx120X-all":   dict(gpu="Navi4 / RX 9070",   isa="gfx1200/1201",       count="1"),
        "gfx900":        dict(gpu="Vega 10",            isa="gfx900",             count="1"),
        "gfx906":        dict(gpu="Vega 20",            isa="gfx906",             count="1"),
        "gfx908":        dict(gpu="Arcturus",           isa="gfx908",             count="1"),
        "gfx101X-dgpu":  dict(gpu="RDNA1",              isa="gfx101X",            count="1"),
        "gfx1152":       dict(gpu="Strix Halo (gfx1152)", isa="gfx1152",          count="1"),
    }
    _location: dict[str, str] = {
        "linux-gfx942-1gpu-ossci-rocm":      "OSSCI",
        "linux-gfx942-1gpu-ccs-ossci-rocm":  "OSSCI",
        "linux-gfx942-1gpu-core42-ossci-rocm":"OSSCI",
        "linux-gfx942-8gpu-ossci-rocm":      "OSSCI",
        "linux-gfx942-8gpu-core42-ossci-rocm":"OSSCI",
        "linux-mi355-1gpu-ossci-rocm":       "OSSCI",
        "linux-gfx90a-gpu-rocm":             "On-Prem (AUS)",
        "linux-gfx1030-gpu-rocm":            "On-Prem",
        "linux-gfx110X-gpu-rocm":            "On-Prem",
        "linux-gfx1150-gpu-rocm":            "On-Prem",
        "linux-gfx1151-gpu-rocm":            "On-Prem",
        "linux-strix-halo-gpu-rocm-oem":     "On-Prem",
        "linux-gfx1153-gpu-rocm":            "On-Prem",
        "linux-gfx120X-gpu-rocm":            "On-Prem",
        "windows-gfx1151-gpu-rocm":          "On-Prem",
        "windows-gfx110X-gpu-rocm":          "On-Prem",
        "windows-gfx1030-gpu-rocm":          "On-Prem",
        "windows-gfx120X-gpu-rocm":          "On-Prem",
    }

    for tier, matrix in matrices.items():
        used_label = tier_used[tier]
        for _family_key, platforms in matrix.items():
            for plat_key, cfg in platforms.items():
                label    = cfg.get("test-runs-on", "")
                fam_name = cfg.get("family", "")
                if not label:
                    continue
                hw      = _hw.get(fam_name, {})
                loc     = _location.get(label, "On-Prem")
                os_ver  = "Windows 11" if plat_key == "windows" else "Ubuntu 22.04 LTS"
                plat    = "Windows" if plat_key == "windows" else "Linux"
                add(label, plat, os_ver, loc, "—",
                    hw.get("gpu", fam_name), hw.get("isa", fam_name),
                    hw.get("count", "1"), used_label, "")

                # Also add weighted alternate labels if present
                for wl in cfg.get("test-runs-on-labels", []):
                    alt = wl.get("label", "")
                    if alt and alt != label:
                        alt_loc = _location.get(alt, "On-Prem")
                        add(alt, plat, os_ver, alt_loc, "—",
                            hw.get("gpu", fam_name), hw.get("isa", fam_name),
                            hw.get("count", "1"), used_label,
                            f"Weighted alternate pool (weight={wl.get('weight', '?')})")

                # Multi-GPU runner
                mg_label = cfg.get("test-runs-on-multi-gpu", "")
                if mg_label and mg_label != label:
                    mg_loc = _location.get(mg_label, "OSSCI")
                    add(mg_label, plat, os_ver, mg_loc, "—",
                        hw.get("gpu", fam_name), hw.get("isa", fam_name),
                        "8", "Nightly · distributed tests · benchmarks",
                        "Multi-GPU runner for distributed tests and benchmarks")

    # ── Static supplemental rows (build pools + special runners) ─────────────
    statics = [
        ("azure-linux-scale-rocm",        "Linux",   "Ubuntu 22.04 LTS",   "OSSCI",
         "~113 elastic",       "None (build only)", "—", "—",
         "All tiers (build jobs)", "Elastic Azure build pool; no GPU"),
        ("azure-windows-scale-rocm",      "Windows", "Windows Server 2022", "OSSCI",
         "~69 elastic",        "None (build only)", "—", "—",
         "All tiers (build jobs)", "Elastic Windows build pool; no GPU"),
        ("nova-linux-slurm-scale-runner", "Linux",   "Ubuntu 22.04 LTS",   "On-Prem",
         "1 (currently offline)", "MI355X multi-node", "gfx950", "N",
         "RCCL only (multi-node Slurm)", "RCCL CI in rocm-systems; Slurm job scheduler"),
        ("rocm-asan-mi325-sandbox",       "Linux",   "Ubuntu 22.04 LTS",   "On-Prem",
         "1 (sandbox)",        "MI325X (sandbox)",  "gfx942", "1",
         "ASAN nightly", "GPU-contamination-safe sandbox for ASAN testing"),
        ("self-hosted (amdsmi/aqlprofile)","Linux",  "Ubuntu 22.04 LTS",   "On-Prem",
         "Varies",             "Various",           "—", "—",
         "Per-component own CI", "amdsmi, aqlprofile own CI runners"),
        ("ubuntu-24.04",                  "Linux",   "Ubuntu 24.04 LTS",   "GitHub-hosted",
         "Unlimited (cloud)",  "None (no GPU)",     "—", "—",
         "Setup / matrix jobs", "GitHub-managed cloud runners"),
        ("windows-2022",                  "Windows", "Windows Server 2022", "GitHub-hosted",
         "Unlimited (cloud)",  "None (no GPU)",     "—", "—",
         "Fallback / fork CI", "GitHub-managed cloud runners"),
    ]
    for row in statics:
        add(*row)

    return rows


# ── Phase 5: Build TIER_DATA ─────────────────────────────────────────────────
#
# Format (9 fields, matching generate_rocm_cicd.py TIER_DATA):
#   tier_name, trigger, schedule, test_type,
#   linux_gpu_families, windows_gpu_families,
#   frameworks_built, distro, windows_distro

def build_tier_data(matrices: dict, nightly_yml: str) -> list[tuple]:
    """Build TIER_DATA from the live GPU family matrices."""
    pre  = matrices["presubmit"]
    post = matrices["postsubmit"]
    ngt  = matrices["nightly"]

    def _linux_fams(m: dict) -> list[str]:
        fams = []
        for cfg in m.values():
            lx = cfg.get("linux", {})
            if lx.get("test-runs-on") and not lx.get("test-runs-on") == "":
                fams.append(lx.get("family", ""))
        return [f for f in fams if f]

    def _win_fams(m: dict) -> list[str]:
        fams = []
        for cfg in m.values():
            win = cfg.get("windows", {})
            if win.get("test-runs-on"):
                fams.append(win.get("family", ""))
        return [f for f in fams if f]

    # Build per-tier GPU family strings
    pre_linux_test  = [f for k, v in pre.items()
                       if not v.get("linux", {}).get("nightly_check_only_for_family")
                       for f in [v.get("linux", {}).get("family")] if f and v.get("linux", {}).get("test-runs-on")]
    pre_linux_build = [v.get("linux", {}).get("family")
                       for v in pre.values()
                       if v.get("linux", {}).get("nightly_check_only_for_family")
                       and v.get("linux", {}).get("test-runs-on")]
    pre_win_fams    = _win_fams(pre)

    po_linux  = _linux_fams(pre) + _linux_fams(post)
    po_win    = _win_fams(pre)

    ni_linux_test  = [f for m in [pre, post, ngt]
                      for v in m.values()
                      for f in [v.get("linux", {}).get("family")]
                      if f and v.get("linux", {}).get("test-runs-on")]
    ni_linux_build = ["gfx900", "gfx906", "gfx908", "gfx101X"]  # no HW runners
    ni_win    = list({v.get("windows", {}).get("family")
                      for m in [pre, post, ngt] for v in m.values()
                      if v.get("windows", {}).get("test-runs-on")} - {None, ""})

    def _fmt_fams(test_fams, build_fams=None, label="Build + Test"):
        parts = []
        if test_fams:
            parts.append(", ".join(sorted(set(test_fams))) + f" — {label}")
        if build_fams:
            parts.append(", ".join(sorted(set(build_fams))) + " — Build-only (no HW runners)")
        return "\n".join(parts) if parts else "—"

    pre_linux_str = (
        ", ".join(sorted(set(pre_linux_test))) + " — Build + Test"
        + ("\n" + ", ".join(sorted(set(pre_linux_build))) + " — Build-only (nightly_check_only_for_family)"
           if pre_linux_build else "")
    )
    pre_win_str = (", ".join(sorted(set(pre_win_fams))) + " — Build-only (nightly_check_only on Windows)"
                   if pre_win_fams else "—")

    po_linux_str = ", ".join(sorted(set(po_linux))) + " — Build + Test"
    po_win_str   = (", ".join(sorted(set(po_win))) + " — Build-only"
                    if po_win else "—")

    ni_linux_all = sorted(set(ni_linux_test))
    ni_linux_str = (", ".join(ni_linux_all) + " — Build + Test"
                    + "\n" + ", ".join(ni_linux_build) + " — Build-only (no HW runners)")
    ni_win_str   = ", ".join(sorted(set(ni_win))) + " — Build + Test" if ni_win else "—"

    # Extract nightly schedule from YAML (look for cron line)
    nightly_schedule = "02:00 UTC daily"
    for line in nightly_yml.splitlines():
        if "cron" in line and "*" in line:
            parts = line.split("'")
            if len(parts) >= 2:
                cron = parts[1].strip()
                # cron "0 2 * * *" → 02:00 UTC daily
                nightly_schedule = f"cron: {cron} (approx. 02:00 UTC daily)"
            break

    return [
        ("Pre-commit (PR)",
         "pull_request: opened / synchronized / labeled",
         "On every PR",
         "standard = full unit suite (rocm-libraries/rocm-systems component PRs)\nquick = smoke/sanity only (TheRock infra/build PRs)",
         pre_linux_str, pre_win_str,
         "PyTorch torch package only (no wheel upload)\nNo JAX in PR CI",
         "Ubuntu 22.04 LTS (OSSCI scale pool)", "Windows 11 (azure-windows-11-* runners)"),
        ("Post-commit (Submodule Bump)",
         "push to main / release/therock-* branches\nFires on every merged commit incl. submodule bumps",
         "Every merged commit",
         "quick = smoke/sanity only",
         po_linux_str, po_win_str,
         "PyTorch torch package only\nROCm Python wheels (Ubuntu 24.04 + UBI10 smoke)\nNo JAX",
         "Ubuntu 22.04 LTS", "Windows 11"),
        ("CI Nightly",
         "ci_nightly.yml + ci_nightly_pytorch_full_test.yml (schedule)",
         nightly_schedule + "\n12:00 UTC daily (PyTorch full)",
         "comprehensive = full + integration (ROCm)\nfull = complete suite (PyTorch)",
         ni_linux_str, ni_win_str,
         "PyTorch: all 5 versions × all Pythons × all families\nJAX: all 4 versions × 4 Pythons\nTriton + Apex (Linux)",
         "Ubuntu 22.04 LTS", "Windows 11"),
        ("ASAN / TSAN",
         "ci_asan.yml / ci_tsan.yml (schedule)", "02:00 UTC daily",
         "quick = smoke/sanity only\n(same suite as Post-commit but with sanitizer build)",
         "gfx94X-dcgpu, gfx950-dcgpu — Build + Test", "—",
         "None (sanitizer build validation only)",
         "Ubuntu 22.04 LTS (rocm-asan-mi325-sandbox)", "—"),
        ("Release",
         "workflow_dispatch (rockrel or manual)",
         "On-demand: dev / nightly / prerelease",
         "quick / none (tests not yet fully wired in multi_arch_release)",
         ni_linux_str, ni_win_str,
         "PyTorch all 5 versions × all Pythons\nJAX all 4 versions\nROCm tarballs to S3",
         "Ubuntu 22.04 LTS + RHEL 8.8/9.5 + SLES 15.6", "Windows 11"),
    ]


# ── Phase 6: Build COMPONENTS ─────────────────────────────────────────────────
#
# For live data we use the existing carefully-curated COMPONENTS list as the
# authoritative baseline and update only the fields that are reliably derivable
# from the GitHub API (runner labels, GPU family strings).  Any components
# discovered in the projects/ directories that are NOT yet in the baseline are
# appended as "CI Unknown — newly discovered" placeholders.
#
# This hybrid approach avoids losing domain knowledge (shard counts, per-component
# exclusions, notes) while still surfacing new additions and runner/family changes.

def _load_baseline_components() -> list[tuple]:
    """
    Import COMPONENTS from the existing generate_rocm_html.py data section.
    We exec only the first 520 lines (constants + COMPONENTS, before HTML generation).
    """
    html_py = HERE / "generate_rocm_html.py"
    if not html_py.exists():
        return []
    lines = html_py.read_text(encoding="utf-8").splitlines(keepends=True)
    # Find the override block start and stop just before it to avoid the
    # bootstrap catch-22 (rocm_ci_data.py may be stale at this point).
    stop = 530
    for i, line in enumerate(lines):
        if "_data_file = _HERE" in line:
            stop = i
            break
    ns: dict = {"__file__": str(html_py)}
    try:
        exec("".join(lines[:stop]), ns)  # noqa: S102
    except Exception as e:
        print(f"  WARN: could not load baseline COMPONENTS — {e}")
        return []
    return ns.get("COMPONENTS", [])


def _runner_strings(matrices: dict) -> dict:
    """
    Derive the canonical shorthand strings from the live matrix so they
    match amdgpu_family_matrix.py exactly rather than the old hardcoded values.
    Returns a dict of shorthand_name → string value.
    """
    pre  = matrices["presubmit"]
    post = matrices["postsubmit"]
    ngt  = matrices["nightly"]

    # Pre-commit Linux (gfx94X only families with actual GPU tests)
    pre_l_test_fams = []
    pre_l_build_fams = []
    for v in pre.values():
        lx = v.get("linux", {})
        fam = lx.get("family", "")
        if not fam or not lx.get("test-runs-on"):
            continue
        if lx.get("nightly_check_only_for_family"):
            pre_l_build_fams.append(fam)
        else:
            pre_l_test_fams.append(fam)

    PC_L_TEST = (", ".join(pre_l_test_fams) + " — Build + Test\n"
                 + ", ".join(pre_l_build_fams) + " — Build-only (nightly_check_only)"
                 if pre_l_build_fams else ", ".join(pre_l_test_fams) + " — Build + Test")
    PC_L_94   = ", ".join(pre_l_test_fams) + " (Build + Test)" if pre_l_test_fams else "gfx94X (Build + Test)"

    # Pre-commit Windows (nightly_check_only families)
    pre_w_build_fams = []
    for v in pre.values():
        win = v.get("windows", {})
        fam = win.get("family", "")
        if fam and win.get("test-runs-on"):
            pre_w_build_fams.append(fam)
    PC_W_BUILD = ", ".join(pre_w_build_fams) + " (Build-only)" if pre_w_build_fams else "gfx1151 (Build-only)"

    # Post-commit Linux
    po_l_fams = []
    for m in [pre, post]:
        for v in m.values():
            lx = v.get("linux", {})
            fam = lx.get("family", "")
            if fam and lx.get("test-runs-on"):
                po_l_fams.append(fam)
    PO_L_FULL = ", ".join(sorted(set(po_l_fams))) + " (Both Build + Test)"

    # Post-commit Windows
    po_w_fams = [v.get("windows", {}).get("family", "")
                 for v in pre.values()
                 if v.get("windows", {}).get("test-runs-on")]
    PO_W_BUILD = ", ".join(f for f in po_w_fams if f) + " (Build-only)" if po_w_fams else "gfx1151 (Build-only)"

    # Nightly Linux (all families with HW runners)
    ni_l_fams = []
    ni_l_build = []
    for m in [pre, post, ngt]:
        for v in m.values():
            lx = v.get("linux", {})
            fam = lx.get("family", "")
            if not fam:
                continue
            if lx.get("test-runs-on"):
                ni_l_fams.append(fam)
            else:
                ni_l_build.append(fam)
    NL_FULL = (", ".join(sorted(set(ni_l_fams)))
               + "\n(Build-only: " + ", ".join(sorted(set(ni_l_build))) + ")"
               if ni_l_build else ", ".join(sorted(set(ni_l_fams))))

    # Nightly Windows (all families with HW runners)
    ni_w_fams = []
    for m in [pre, post, ngt]:
        for v in m.values():
            win = v.get("windows", {})
            fam = win.get("family", "")
            if fam and win.get("test-runs-on"):
                ni_w_fams.append(fam)
    NW_FULL = ", ".join(sorted(set(ni_w_fams)))

    # Runner label strings
    pre_l_primary = next(
        (v.get("linux", {}).get("test-runs-on", "")
         for v in pre.values()
         if not v.get("linux", {}).get("nightly_check_only_for_family")
         and v.get("linux", {}).get("test-runs-on")),
        "linux-gfx942-1gpu-ossci-rocm",
    )
    pre_l_alts = [
        wl["label"]
        for v in pre.values()
        for wl in v.get("linux", {}).get("test-runs-on-labels", [])
        if wl["label"] != pre_l_primary
    ]
    PCR_L = (pre_l_primary + "\n(alternate pool" + (": " + ", ".join(pre_l_alts) if pre_l_alts else "") + ")")

    po_l_runners = []
    for m in [pre, post]:
        for v in m.values():
            lx = v.get("linux", {})
            r = lx.get("test-runs-on", "")
            fam = lx.get("family", "")
            if r and fam:
                po_l_runners.append(f"{r} ({fam})")
    POR_L = "\n".join(sorted(set(po_l_runners)))

    ni_l_runners = []
    for m in [pre, post, ngt]:
        for v in m.values():
            lx = v.get("linux", {})
            r = lx.get("test-runs-on", "")
            fam = lx.get("family", "")
            if r and fam:
                ni_l_runners.append(f"{r} ({fam})")
    NLR_FULL = "\n".join(sorted(set(ni_l_runners)))

    ni_w_runners = []
    for m in [pre, post, ngt]:
        for v in m.values():
            win = v.get("windows", {})
            r = win.get("test-runs-on", "")
            fam = win.get("family", "")
            if r and fam:
                ni_w_runners.append(f"{r} ({fam})")
    NWR_FULL = "\n".join(sorted(set(ni_w_runners)))

    pre_w_runner = next(
        (v.get("windows", {}).get("test-runs-on", "")
         for v in pre.values()
         if v.get("windows", {}).get("test-runs-on")),
        "windows-gfx1151-gpu-rocm",
    )
    PCR_W = pre_w_runner + " (Build-only)"
    POR_W = pre_w_runner + " (Build-only)"

    return dict(
        PC_L_TEST=PC_L_TEST, PC_L_94=PC_L_94,
        PC_W_BUILD=PC_W_BUILD,
        PO_L_FULL=PO_L_FULL, PO_W_BUILD=PO_W_BUILD,
        NL_FULL=NL_FULL, NW_FULL=NW_FULL,
        PCR_L=PCR_L, POR_L=POR_L,
        PCR_W=PCR_W, POR_W=POR_W,
        NLR_FULL=NLR_FULL, NWR_FULL=NWR_FULL,
    )


def _update_component(comp: tuple, rs: dict) -> tuple:
    """
    Replace shorthand constant references in a component tuple with live values.
    Fields we update: pc_lgfx(5), pc_lr(6), pc_wgfx(7), pc_wr(8),
                      po_lgfx(10), po_lr(11), po_wgfx(12), po_wr(13),
                      ni_lgfx(15), ni_lr(16), ni_wgfx(17), ni_wr(18).
    We only replace fields that exactly match the old shorthand strings.
    Per-component overrides (hipSPARSELt, RCCL, etc.) are left untouched.
    """
    # Map old hardcoded shorthand values → new live values
    replacements = {
        # GPU family shorthands
        "gfx94X (Build + Test)":                           rs["PC_L_94"],
        "gfx94X (Build + Test)\ngfx110X, gfx1151, gfx120X — Build-only (nightly_check_only)":
                                                           rs["PC_L_TEST"],
        "gfx1151 (Build-only)":                            rs["PC_W_BUILD"],
        "gfx94X, gfx950 (Both Build + Test)":             rs["PO_L_FULL"],
        "gfx1151 (Build-only)":                            rs["PO_W_BUILD"],
        "gfx1151, gfx110X, gfx103X, gfx120X":             rs["NW_FULL"],
        # Runner shorthands (PC_L runners multi-line string)
        "linux-gfx942-1gpu-ossci-rocm\n(alternate pool: linux-gfx942-1gpu-ccs-ossci-rocm)":
                                                           rs["PCR_L"],
        "linux-gfx942-1gpu-ossci-rocm (gfx94X)\nlinux-mi355-1gpu-ossci-rocm (gfx950)":
                                                           rs["POR_L"],
        "windows-gfx1151-gpu-rocm (Build-only)":          rs["PCR_W"],
    }
    # NL_FULL and NLR_FULL are multi-line; only replace if exact match
    replacements[
        "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X\n"
        "(Build-only: gfx900, gfx906, gfx908, gfx101X)"
    ] = rs["NL_FULL"]
    replacements[
        "linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
        "linux-mi355-1gpu-ossci-rocm (gfx950)\n"
        "linux-gfx90a-gpu-rocm (gfx90a)\n"
        "linux-gfx1030-gpu-rocm (gfx103X)\n"
        "linux-gfx110X-gpu-rocm (gfx110X)\n"
        "linux-gfx1150-gpu-rocm (gfx1150)\n"
        "linux-gfx1151-gpu-rocm (gfx1151)\n"
        "linux-gfx1153-gpu-rocm (gfx1153)\n"
        "linux-gfx120X-gpu-rocm (gfx120X)"
    ] = rs["NLR_FULL"]
    replacements[
        "windows-gfx1151-gpu-rocm (gfx1151)\n"
        "windows-gfx110X-gpu-rocm (gfx110X)\n"
        "windows-gfx1030-gpu-rocm (gfx103X)\n"
        "windows-gfx120X-gpu-rocm (gfx120X)"
    ] = rs["NWR_FULL"]

    lst = list(comp)
    for i, val in enumerate(lst):
        if isinstance(val, str) and val in replacements:
            lst[i] = replacements[val]
    return tuple(lst)


def build_components(matrices: dict,
                     lib_projects: list[str],
                     sys_projects: list[str]) -> list[tuple]:
    """
    Build COMPONENTS by:
    1. Loading the curated baseline from generate_rocm_html.py.
    2. Updating runner/GPU-family fields with live values from the matrix.
    3. Appending any brand-new components found in projects/ that are not
       already in the baseline.
    """
    rs = _runner_strings(matrices)
    baseline = _load_baseline_components()

    # Update runner/GPU-family shorthands in baseline with live values
    updated = [_update_component(c, rs) for c in baseline]

    # Collect component names already in baseline (lower-cased for fuzzy match)
    existing_names = {c[2].lower().replace(" ", "").replace("-", "").replace("_", "")
                      for c in updated}

    def _key(name: str) -> str:
        return name.lower().replace(" ", "").replace("-", "").replace("_", "")

    # ── Category map for new components ──────────────────────────────────────
    _cat_map: dict[str, tuple[str, str]] = {
        # rocm-libraries
        "rocblas":          ("Libraries", "Math"),
        "hipblas":          ("Libraries", "Math"),
        "hipblas-common":   ("Libraries", "Math"),
        "hipblaslt":        ("Libraries", "Math"),
        "hipfft":           ("Libraries", "Math"),
        "rocfft":           ("Libraries", "Math"),
        "hiprand":          ("Libraries", "Math"),
        "rocrand":          ("Libraries", "Math"),
        "hipsolver":        ("Libraries", "Math"),
        "rocsolver":        ("Libraries", "Math"),
        "hipsparse":        ("Libraries", "Math"),
        "rocsparse":        ("Libraries", "Math"),
        "hipsparselt":      ("Libraries", "Math"),
        "hiptensor":        ("Libraries", "Math"),
        "rocwmma":          ("Libraries", "Math"),
        "hipcub":           ("Libraries", "Primitives"),
        "rocprim":          ("Libraries", "Primitives"),
        "rocthrust":        ("Libraries", "Primitives"),
        "miopen":           ("Libraries", "ML & CV"),
        "hipdnn":           ("Libraries", "ML & CV"),
        "composablekernel": ("Libraries", "ML & CV"),
        "rccl":             ("Libraries", "Communication"),
        "rocdecode":        ("Libraries", "Media"),
        "rocjpeg":          ("Libraries", "Media"),
        # rocm-systems
        "amdsmi":           ("Tools", "System Mgmt"),
        "rocm-smi-lib":     ("Tools", "System Mgmt"),
        "rdc":              ("Tools", "System Mgmt"),
        "rocminfo":         ("Tools", "Development"),
        "rocdbgapi":        ("Tools", "Development"),
        "rocr-debug-agent": ("Tools", "Development"),
        "rocprofiler-sdk":  ("Tools", "Performance"),
        "rocprofiler-systems": ("Tools", "Performance"),
        "rocprofiler-compute": ("Tools", "Performance"),
        "rocprofiler":      ("Tools", "Performance"),
        "rocprofiler-register": ("Tools", "Performance"),
        "aqlprofile":       ("Tools", "Performance"),
        "roctracer":        ("Tools", "Performance"),
        "rocr-runtime":     ("Runtime", "—"),
        "clr":              ("Runtime", "—"),
        "hip":              ("Runtime", "—"),
        "rocm-core":        ("Runtime", "—"),
        "cuid":             ("Runtime", "—"),
        "hipfile":          ("Runtime", "—"),
        "hipother":         ("Runtime", "—"),
        "hotswap":          ("Runtime", "—"),
        "rocshmem":         ("Libraries", "Communication"),
    }
    # test-only repos + raw directory names already covered by curated baseline entries
    _skip = {
        # test-only, not CI components
        "hip-tests", "rccl-tests", "rocprof-trace-decoder",
        # covered by "HIP Runtime (CLR)"
        "clr", "hip", "hipfile", "hipother", "cuid", "hotswap",
        # covered by "ROCr Runtime (HSA)"
        "rocr-runtime",
        # covered by "ROCm Core"
        "rocm-core",
        # covered by "ROCProfiler (v2)"
        "rocprofiler",
        # covered by "ROCm Compute Profiler"
        "rocprofiler-compute",
        # covered by "ROCm System Profiler"
        "rocprofiler-systems",
        # covered by "ROCm Data Center Tool"
        "rdc",
        # covered by "Composable Kernels"
        "composablekernel",
    }

    def _make_new_row(name: str, repo: str) -> tuple:
        """Create a minimal placeholder row for a new component."""
        cat, sub = _cat_map.get(name.lower(), ("Libraries", "—"))
        pc_lgfx = rs["PC_L_94"]
        pc_lr   = rs["PCR_L"]
        po_lgfx = rs["PO_L_FULL"]
        po_lr   = rs["POR_L"]
        ni_lgfx = rs["NL_FULL"]
        ni_lr   = rs["NLR_FULL"]
        # Windows support: use existing map heuristic
        has_win = cat in ("Libraries",) and sub in ("Math", "Primitives", "ML & CV")
        pc_wgfx, pc_wr = (rs["PC_W_BUILD"], rs["PCR_W"]) if has_win else ("—", "—")
        po_wgfx, po_wr = (rs["PC_W_BUILD"], rs["POR_W"]) if has_win else ("—", "—")
        ni_wgfx = rs["NW_FULL"] if has_win else "—"
        ni_wr   = rs["NWR_FULL"] if has_win else "—"
        plat    = "Both" if has_win else "Linux only"
        return (cat, sub, name, repo, "Yes",
                pc_lgfx, pc_lr, pc_wgfx, pc_wr, "standard",
                po_lgfx, po_lr, po_wgfx, po_wr, "quick",
                ni_lgfx, ni_lr, ni_wgfx, ni_wr, "comprehensive",
                plat, "NEW — auto-discovered from GitHub projects/ directory")

    # Append newly discovered rocm-libraries components
    for name in lib_projects:
        if _key(name) not in existing_names and name.lower() not in _skip:
            print(f"  + New rocm-libraries component: {name}")
            updated.append(_make_new_row(name, "rocm-libraries"))

    # Append newly discovered rocm-systems components
    for name in sys_projects:
        if _key(name) not in existing_names and name.lower() not in _skip:
            print(f"  + New rocm-systems component: {name}")
            updated.append(_make_new_row(name, "rocm-systems"))

    return updated


# ── Phase 7: Write rocm_ci_data.py ───────────────────────────────────────────

def _repr_tuple(t: tuple, indent: int = 4) -> str:
    """Pretty-print a tuple across multiple lines."""
    pad = " " * indent
    lines = [f"{pad}("]
    for i, v in enumerate(t):
        comma = "," if i < len(t) - 1 else ""
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            lines.append(f'{pad}    "{escaped}"{comma}')
        else:
            lines.append(f"{pad}    {v!r}{comma}")
    lines.append(f"{pad})")
    return "\n".join(lines)


def write_data_module(
    components: list[tuple],
    runner_data: list[tuple],
    tier_data: list[tuple],
    fw_data_src: str,
    wh_data_src: str,
    imax_data: list[tuple] | None = None,
    inference_runners: dict | None = None,
) -> Path:
    """Write rocm_ci_data.py with all live data structures."""
    out = HERE / "rocm_ci_data.py"
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""Auto-generated by fetch_rocm_data.py — do not edit manually."""',
        "",
        f"# Generated: {(lambda: __import__('datetime').datetime.now(__import__('zoneinfo', fromlist=['ZoneInfo']).ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %I:%M %p %Z'))()}",
        "",
        "COMPONENTS = [",
    ]
    for c in components:
        lines.append(_repr_tuple(c) + ",")
    lines += ["]", "", "RUNNER_DATA = ["]
    for r in runner_data:
        lines.append(_repr_tuple(r) + ",")
    lines += ["]", "", "TIER_DATA = ["]
    for t in tier_data:
        lines.append(_repr_tuple(t) + ",")
    lines += ["]", ""]
    # FW_DATA and WH_DATA are complex / version-specific; copy verbatim from source
    lines.append(fw_data_src)
    lines.append("")
    lines.append(wh_data_src)
    lines.append("")

    # InferenceMAX AMD benchmark data (optional — only written when fetched)
    # Tuple schema: (name, model, model_prefix, runner, precision, framework,
    #                multinode, docker_image)
    lines.append("INFERENCEMAX_DATA = [")
    for row in (imax_data or []):
        lines.append(_repr_tuple(row) + ",")
    lines.append("]")
    lines.append("")
    # INFERENCE_RUNNERS: {"amd": {runner_type: [node_labels]}}
    lines.append("INFERENCE_RUNNERS = " + repr(inference_runners or {}))
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {out}")
    return out


def _extract_block(src: str, var_name: str) -> str:
    """Extract 'VAR_NAME = [...]' block verbatim from a Python source string."""
    lines = src.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{var_name} = ["):
            start = i
            break
    if start is None:
        return f"{var_name} = []"
    depth = 0
    end = start
    for i in range(start, len(lines)):
        depth += lines[i].count("[") - lines[i].count("]")
        if depth <= 0 and i > start:
            end = i
            break
    return "".join(lines[start : end + 1])


# ── Phase 7b: InferenceMAX / InferenceX fetch & parse ────────────────────────

def _read_local_inferencemax(file_rel: str) -> str:
    """Try to read a file from the local InferenceMAX_rocm clone."""
    candidates = [
        HERE / "InferenceMAX_rocm" / file_rel,
        HERE.parent / "InferenceMAX_rocm" / file_rel,
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def fetch_inferencemax() -> tuple[str, str]:
    """
    Fetch InferenceMAX_rocm AMD configs and runner pool.
    Priority: GitHub API (if TOKEN set) → local clone.
    Returns: (amd_yaml, runners_yaml) — empty strings on failure.
    """
    amd_yaml = runners_yaml = ""

    if TOKEN:
        print("  [InferenceMAX] Fetching from GitHub API (ROCm/InferenceMAX_rocm)...")
        amd_yaml     = gh_file("ROCm", "InferenceMAX_rocm", ".github/configs/amd-master.yaml")
        runners_yaml = gh_file("ROCm", "InferenceMAX_rocm", ".github/configs/runners.yaml")

    if not amd_yaml:
        print("  [InferenceMAX] Falling back to local clone...")
        amd_yaml     = _read_local_inferencemax(".github/configs/amd-master.yaml")
        runners_yaml = _read_local_inferencemax(".github/configs/runners.yaml")

    if not amd_yaml:
        print("  WARN: InferenceMAX data not available (no token + no local clone)")
    return amd_yaml, runners_yaml


def parse_benchmark_yaml(yaml_src: str) -> list[dict]:
    """
    Parse amd-master.yaml without pyyaml.
    Returns list of config dicts with keys:
      name, model, model_prefix, runner, precision, framework,
      multinode, docker_image
    """
    import re
    if not yaml_src:
        return []

    lines = yaml_src.splitlines()
    configs = []
    current: dict | None = None

    def _bool(s: str) -> bool:
        return str(s).strip().lower() in ("true", "yes", "1")

    def _val(line: str) -> str:
        parts = line.split(":", 1)
        return parts[1].strip() if len(parts) > 1 else ""

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Top-level key (config name) — not indented, ends with colon
        if indent == 0 and stripped.endswith(":") and not stripped.startswith("-") and stripped != "":
            if current is not None:
                configs.append(current)
            name = stripped.rstrip(":")
            current = dict(name=name, model="", model_prefix="", runner="",
                           precision="", framework="", multinode=False, docker_image="")
            continue

        if current is None:
            continue

        if stripped.startswith("image:"):
            current["docker_image"] = _val(stripped)
        elif stripped.startswith("model:") and "model-prefix" not in stripped:
            current["model"] = _val(stripped)
        elif stripped.startswith("model-prefix:"):
            current["model_prefix"] = _val(stripped)
        elif stripped.startswith("runner:"):
            current["runner"] = _val(stripped)
        elif stripped.startswith("precision:"):
            current["precision"] = _val(stripped)
        elif stripped.startswith("framework:"):
            current["framework"] = _val(stripped)
        elif stripped.startswith("multinode:"):
            current["multinode"] = _bool(_val(stripped))

    if current is not None:
        configs.append(current)

    return configs


def parse_runners_yaml(yaml_src: str) -> dict[str, list[str]]:
    """
    Parse runners.yaml — maps runner-type → list of node instance labels.
    Returns dict: {runner_type: [node_labels]}
    """
    if not yaml_src:
        return {}
    result: dict[str, list[str]] = {}
    current_key: str = ""
    for line in yaml_src.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped.endswith(":") and not stripped.startswith("-"):
            current_key = stripped.rstrip(":")
            result[current_key] = []
        elif current_key and stripped.startswith("- "):
            node = stripped[2:].strip().strip("'\"")
            if node:
                result[current_key].append(node)
    return result


def build_inference_data(
    amd_configs: list[dict],
    amd_runners: dict[str, list[str]],
) -> tuple[list[tuple], dict]:
    """
    Build INFERENCEMAX_DATA and INFERENCE_RUNNERS (AMD only).
    Each data row is an 8-tuple:
      (name, model, model_prefix, runner, precision, framework,
       multinode, docker_image)
    """
    def _to_tuples(cfgs: list[dict]) -> list[tuple]:
        rows = []
        for c in cfgs:
            rows.append((
                c.get("name", ""),
                c.get("model", ""),
                c.get("model_prefix", ""),
                c.get("runner", ""),
                c.get("precision", ""),
                c.get("framework", ""),
                c.get("multinode", False),
                c.get("docker_image", ""),
            ))
        return rows

    imax_data = _to_tuples(amd_configs)

    # Keep only AMD runners (mi300x/mi325x/mi355x pools)
    _amd_keys = {"mi300x", "mi325x", "mi355x", "mi355x-disagg",
                 "mi300x-multinode", "mi325x-multinode", "mi355x-multinode"}
    runners_out = {
        "amd": {k: v for k, v in amd_runners.items()
                if k in _amd_keys or any(gpu in k for gpu in ("mi300", "mi325", "mi355"))},
    }

    return imax_data, runners_out


# ── Phase 8: Generate outputs ─────────────────────────────────────────────────

def generate_outputs() -> None:
    """
    Run generate_rocm_html.py and generate_rocm_cicd.py in-process.
    Both scripts will auto-detect rocm_ci_data.py and load fresh data.
    """
    html_py  = HERE / "generate_rocm_html.py"
    cicd_py  = HERE / "generate_rocm_cicd.py"

    if html_py.exists():
        print("\nGenerating HTML report...")
        src = html_py.read_text(encoding="utf-8")
        ns: dict = {"__file__": str(html_py)}
        exec(src, ns)  # noqa: S102

    if cicd_py.exists():
        print("\nGenerating Excel workbook...")
        src = cicd_py.read_text(encoding="utf-8")
        ns = {"__file__": str(cicd_py)}
        exec(src, ns)  # noqa: S102


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  ROCm CI/CD Data Fetcher")
    print("=" * 60)

    if not TOKEN:
        print("  NOTE: GITHUB_TOKEN not set — using unauthenticated API (60 req/hr limit)")

    raw      = fetch_all()
    matrices = parse_matrix(raw["matrix_src"])
    _topology = parse_topology(raw["topology_src"])  # available for future use

    print("\nBuilding data structures...")
    runner_data = build_runner_data(matrices)
    tier_data   = build_tier_data(matrices, raw["nightly_yml"])
    components  = build_components(matrices, raw["lib_projects"], raw["sys_projects"])

    print(f"  Components : {len(components)} ({sum(1 for c in components if c[0] != 'Frameworks')} non-framework)")
    print(f"  Runners    : {len(runner_data)}")
    print(f"  Tiers      : {len(tier_data)}")

    # Extract FW_DATA and WH_DATA verbatim from the existing cicd generator
    cicd_src = (HERE / "generate_rocm_cicd.py").read_text(encoding="utf-8")
    fw_block  = _extract_block(cicd_src, "FW_DATA")
    wh_block  = _extract_block(cicd_src, "WH_DATA")
    # Include helper strings referenced by FW_DATA / WH_DATA.
    # Extract the entire preamble block (multi-line assignments) by scanning
    # from the first _PT_/_JAX_ line up to (but not including) FW_DATA = [.
    cicd_lines = cicd_src.splitlines(keepends=True)
    preamble_start = None
    fw_data_line = None
    wh_data_line = None
    for i, line in enumerate(cicd_lines):
        stripped = line.strip()
        if preamble_start is None and (stripped.startswith("_PT_") or stripped.startswith("_JAX_")):
            preamble_start = i
        if stripped.startswith("FW_DATA = ["):
            fw_data_line = i
        if stripped.startswith("WH_DATA = ["):
            wh_data_line = i
    preamble = ""
    if preamble_start is not None and fw_data_line is not None:
        preamble = "".join(cicd_lines[preamble_start:fw_data_line])
    fw_block = preamble + "\n" + fw_block
    # Include _WH_SMOKE_* helpers before WH_DATA block
    wh_preamble = ""
    if wh_data_line is not None:
        # scan backwards from WH_DATA to find the start of _WH_ helpers
        wh_preamble_start = wh_data_line
        for i in range(wh_data_line - 1, -1, -1):
            stripped = cicd_lines[i].strip()
            if stripped.startswith("_WH_") or stripped == "" or stripped.startswith("#"):
                wh_preamble_start = i
            else:
                break
        wh_preamble = "".join(cicd_lines[wh_preamble_start:wh_data_line])
    wh_block = wh_preamble + "\n" + wh_block

    # Fetch InferenceMAX AMD data
    print("\nFetching InferenceMAX data...")
    amd_yaml, runners_yaml = fetch_inferencemax()

    amd_configs = parse_benchmark_yaml(amd_yaml)
    amd_runners = parse_runners_yaml(runners_yaml)

    print(f"  AMD benchmark configs: {len(amd_configs)}")
    print(f"  AMD runner pools     : {len(amd_runners)}")

    imax_data, inference_runners = build_inference_data(amd_configs, amd_runners)

    print("\nWriting rocm_ci_data.py...")
    write_data_module(
        components, runner_data, tier_data, fw_block, wh_block,
        imax_data=imax_data, inference_runners=inference_runners,
    )

    generate_outputs()

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
