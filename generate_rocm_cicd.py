# -*- coding: utf-8 -*-
"""Generate ROCm CI/CD Excel — tier-grouped column layout (mirrors HTML)"""
import xlsxwriter, os, sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path as _Path
_HERE = _Path(__file__).parent
OUT = str(_HERE / "ROCm_CICD_Comprehensive.xlsx")

# ─── Reuse all constants + COMPONENTS from the HTML generator ────────────────
# Exec through the live-data override block (includes COMPONENTS + rocm_ci_data.py load).
# Line count: find the boundary dynamically so adding lines to generate_rocm_html.py
# doesn't break this exec slice.
_src_lines = open(_HERE / "generate_rocm_html.py", encoding="utf-8").readlines()
_xlsx_out = OUT   # save our output path before exec overwrites OUT
# Find the first line of "Summary counts" section — exec everything before it
_exec_end = next(
    (i for i, l in enumerate(_src_lines) if "─── Summary counts" in l),
    560,  # fallback if marker moves
)
exec("".join(_src_lines[:_exec_end]))
OUT = _xlsx_out   # restore

# ── Live data override for RUNNER_DATA / TIER_DATA (Excel-only data) ─────────
_data_file2 = _HERE / "rocm_ci_data.py"
if _data_file2.exists():
    _data_ns2: dict = {}
    exec(_data_file2.read_text(encoding="utf-8"), _data_ns2)
    if "RUNNER_DATA" in _data_ns2:
        RUNNER_DATA = _data_ns2["RUNNER_DATA"]
    if "TIER_DATA" in _data_ns2:
        TIER_DATA = _data_ns2["TIER_DATA"]

# ─── Colour palette ───────────────────────────────────────────────────────────
AMD_RED   = "#CC0000"
AMD_DARK  = "#1A1A1A"
WHITE     = "#FFFFFF"

# Tier header colours (matching HTML: PC=blue, PO=green, NI=orange)
PC_BG  = "#1565C0"   # Pre-commit deep blue
PO_BG  = "#2E7D32"   # Post-commit deep green
NI_BG  = "#E65100"   # Nightly deep orange
META_BG= "#558B2F"   # Platform/Notes olive
BASE_BG= "#37474F"   # Left-fixed cols slate

# Sub-header colours (lighter tints of tier colours)
PC_SUB  = "#1976D2"
PO_SUB  = "#388E3C"
NI_SUB  = "#F57C00"

YES_GRN   = "#C6EFCE"
NO_RED    = "#FFCCCC"
PART_YEL  = "#FFEB9C"

cat_bg = {
    "Libraries": "#EBF3FB",
    "Tools":     "#EBF5EB",
    "Compilers": "#FFF9E6",
    "Runtime":   "#FFF0E6",
    "iree-libs": "#FDE7F3",
    "Sysdeps":   "#FAFAFA",
    "Frameworks":"#E8F5E9",
}
sub_bg_map = {
    "Math":                  "#D6E4F7",
    "Communication":         "#D5E8D4",
    "Primitives":            "#FFF2CC",
    "ML & Computer Vision":  "#F8CECC",
    "Media":                 "#FCE4EC",
    "DNN Providers":         "#E8EAF6",
    "System Management":     "#E1D5E7",
    "Performance":           "#E0F7FA",
    "Development":           "#F3E5F5",
}

# ─── Runner & Tier/Framework data (same as v1 xlsx) ──────────────────────────
RUNNER_DATA = [
    ("linux-gfx942-1gpu-ossci-rocm",     "Linux",   "Ubuntu 22.04 LTS",  "OSSCI",          "84 (vth9c-*: 83 online + 1 offline)",         "MI300X / MI325X",          "gfx942 / gfx94X",  "1", "PR · postsubmit · nightly",               "Primary Linux GPU runner; largest pool"),
    ("linux-gfx942-1gpu-ccs-ossci-rocm", "Linux",   "Ubuntu 22.04 LTS",  "OSSCI",          "0 (label not present in fleet)",              "MI300X / MI325X",          "gfx942 / gfx94X",  "1", "PR · postsubmit · nightly",               "Label not assigned to any runner in current fleet; effectively retired"),
    ("linux-gfx942-8gpu-ossci-rocm",     "Linux",   "Ubuntu 22.04 LTS",  "OSSCI",          "4 (8g2wk-* pool)",                            "MI300X / MI325X",          "gfx942 / gfx94X",  "8", "Nightly · distributed tests · benchmarks", "PyTorch distributed (3 shards); RCCL multi-GPU"),
    ("linux-mi355-1gpu-ossci-rocm",      "Linux",   "Ubuntu 22.04 LTS",  "OSSCI",          "3 (j5v9z-* pool)",                            "MI355X",                   "gfx950",            "1", "Postsubmit · nightly",                    "gfx950 not tested at PR"),
    ("linux-gfx90a-gpu-rocm",            "Linux",   "Ubuntu 22.04 LTS",  "On-Prem (AUS)",  "12 GPU slots (3 nodes x 4 GPUs — smci250-ccs)","MI200",                   "gfx90a",            "1", "Nightly only",                            "Supermicro nodes in Australia datacenter"),
    ("linux-gfx1030-gpu-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "2 (linux-rx6950-gpu-rocm-1/2)",               "RX 6000 (RDNA2)",          "gfx1030 / gfx103X", "1", "Nightly only",                            "Consumer GPU (RX 6950 XT)"),
    ("linux-gfx110X-gpu-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "6 (gfx110X-gpu-rocm-1/2/3/4 + labctr-gfx1103 + labxsj-gfx1103)", "Navi3 / RX 7900",          "gfx1100/1101",      "1", "Nightly only",                            "nightly_check_only_for_family=True"),
    ("linux-gfx1150-gpu-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "1-2 (linux-strix-gpu-rocm-2 + labblr)",       "Strix Point",              "gfx1150",           "1", "Nightly only",                            "APU — Strix Point"),
    ("linux-gfx1151-gpu-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "4 (strix-halo-6/7 + shark-strixhalo-17/18; strix-halo-3 lacks gfx1151 label)", "Strix Halo",               "gfx1151",           "1", "Nightly only",                            "nightly_check_only; OEM pool also exists; strix-halo-3 offline and mis-labelled"),
    ("linux-strix-halo-gpu-rocm-oem",    "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "4 (shark-strixhalo-17/18 + strix-halo-6/7)",  "Strix Halo (OEM)",         "gfx1151",           "1", "Nightly only",                            "OEM kernel variant"),
    ("linux-gfx1153-gpu-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "3 (labxsj-linux-u2404-gfx1153-*)",            "Krackan Point (Radeon 820M)","gfx1153",         "1", "Nightly only",                            "APU — Krackan Point; disabled since 7.12.0a20260214 (CK instability)"),
    ("linux-gfx120X-gpu-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "4 (rx9070-1/3/4 + rx9700-1; rx9070-2 lacks gfx120X label)", "Navi4 / RX 9070",          "gfx1200/1201",      "1", "Nightly only",                            "Consumer GPU; nightly_check_only; rx9070-2 mis-labelled"),
    ("windows-gfx1151-gpu-rocm",         "Windows", "Windows 11",         "On-Prem",        "11 (strix-halo-1/4/6/8/10-16; -7 DO-NOT-ENABLE)", "Strix Halo",               "gfx1151",           "1", "PR · postsubmit · nightly",               "Primary Windows GPU runner; strix-halo-7 excluded (DO-NOT-ENABLE)"),
    ("windows-gfx110X-gpu-rocm",         "Windows", "Windows 11",         "On-Prem",        "23 (22 online + 1 offline; azure-windows-11-gfx1101-*)", "Navi3 / RX 7900",          "gfx1100/1101",      "1", "Nightly only",                            "nightly_check_only"),
    ("windows-gfx1030-gpu-rocm",         "Windows", "Windows 11",         "On-Prem",        "2 (azure-windows-11-gfx1030-00/01)",          "RX 6000 (RDNA2)",          "gfx1030",           "1", "Nightly only",                            ""),
    ("windows-gfx120X-gpu-rocm",         "Windows", "Windows 11",         "On-Prem",        "0 (label doesn't exist; runners use windows-gfx1201-gpu-rocm)", "Navi4 / RX 9070",          "gfx1200/1201",      "1", "Nightly only",                            "Label windows-gfx120X-gpu-rocm not present in fleet; actual label is windows-gfx1201-gpu-rocm"),
    ("azure-linux-scale-rocm",           "Linux",   "Ubuntu 22.04 LTS",  "OSSCI",          "~113 (112 ccqkb-* online + 1 heavy runner)",  "None (build only)",        "—",                 "—", "All tiers (build jobs)",                  "Elastic Azure build pool; no GPU"),
    ("azure-windows-scale-rocm",         "Windows", "Windows Server 2022","OSSCI",          "69 (ckv2f-*: 67 online + 2 offline)",         "None (build only)",        "—",                 "—", "All tiers (build jobs)",                  "Elastic Windows build pool; no GPU"),
    ("nova-linux-slurm-scale-runner",    "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "1 (currently offline)",                       "MI355X multi-node",        "gfx950",            "N", "RCCL only (multi-node Slurm)",            "RCCL CI in rocm-systems; Slurm job scheduler; 1 runner offline as of Apr 20 snapshot"),
    ("rocm-asan-mi325-sandbox",          "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "1 (rocm-banff-asan-mi325-sandbox; currently offline)", "MI325X (sandbox)",         "gfx942",            "1", "ASAN nightly",                            "GPU-contamination-safe sandbox; offline as of Apr 20 snapshot"),
    ("self-hosted (amdsmi/aqlprofile)",  "Linux",   "Ubuntu 22.04 LTS",  "On-Prem",        "Varies",                                      "Various",                  "—",                 "—", "Per-component own CI",                    "amdsmi, aqlprofile own CI runners"),
    ("ubuntu-24.04",                     "Linux",   "Ubuntu 24.04 LTS",  "GitHub-hosted",  "Unlimited (cloud)",                           "None (no GPU)",            "—",                 "—", "Setup / matrix jobs",                     "GitHub-managed cloud runners"),
    ("windows-2022",                     "Windows", "Windows Server 2022","GitHub-hosted",  "Unlimited (cloud)",                           "None (no GPU)",            "—",                 "—", "Fallback / fork CI",                      "GitHub-managed cloud runners"),
]

TIER_DATA = [
    ("Pre-commit (PR)",
     "pull_request: opened / synchronized / labeled", "On every PR",
     "standard = full unit suite\n  → rocm-libraries / rocm-systems component PRs\n\nquick = smoke/sanity only\n  → TheRock infra/build PRs; default when no test:* label",
     "gfx94X-dcgpu — Build + Test (MI300X/MI325X)\ngfx110X, gfx1151, gfx120X — Build-only (nightly_check_only_for_family)",
     "gfx1151 — Build-only (nightly_check_only on Windows too)",
     "PyTorch torch package only (no wheel upload)\nNo JAX in PR CI",
     "Ubuntu 22.04 LTS (OSSCI scale pool)", "Windows 11 (azure-windows-11-* runners)"),
    ("Post-commit (Submodule Bump)",
     "push to main / release/therock-* branches\nFires on every merged commit incl. submodule bumps",
     "Every merged commit",
     "quick = smoke/sanity only",
     "gfx94X-dcgpu — Build + Test\ngfx950-dcgpu — Build + Test (MI355X; postsubmit matrix only)\ngfx110X, gfx1151, gfx120X — Build-only",
     "gfx1151 — Build-only",
     "PyTorch torch package only\nROCm Python wheels (Ubuntu 24.04 + UBI10 smoke)\nNo JAX",
     "Ubuntu 22.04 LTS", "Windows 11"),
    ("CI Nightly",
     "ci_nightly.yml + ci_nightly_pytorch_full_test.yml (schedule)",
     "02:00 UTC daily (ROCm)\n12:00 UTC daily (PyTorch full)",
     "comprehensive = full + integration (ROCm)\nfull = complete suite (PyTorch)",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — all Build + Test\ngfx900/906/908/101X — Build-only (no HW runners)",
     "gfx1151, gfx110X, gfx103X, gfx120X — all Build + Test",
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
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build + Test (quick)\nBuild-only (no HW runners): gfx900, gfx906, gfx908, gfx101X",
     "gfx1151, gfx110X, gfx103X, gfx120X — Build + Test (quick)",
     "PyTorch all 5 versions × all Pythons\nJAX all 4 versions\nROCm tarballs to S3",
     "Ubuntu 22.04 LTS + RHEL 8.8/9.5 + SLES 15.6", "Windows 11"),
]

_PT_BUILD_L  = "Linux: azure-linux-scale-rocm"
_PT_BUILD_LW = "Linux: azure-linux-scale-rocm\nWindows: azure-windows-scale-rocm"
_PT_TEST_28  = ("Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
                "linux-mi355-1gpu-ossci-rocm (gfx950)\n"
                "linux-gfx90a-gpu-rocm (gfx90a)\n"
                "linux-gfx1030-gpu-rocm (gfx103X)\n"
                "linux-gfx110X-gpu-rocm (gfx110X)\n"
                "linux-gfx1150-gpu-rocm (gfx1150)\n"
                "linux-gfx1151-gpu-rocm (gfx1151)\n"
                "linux-gfx120X-gpu-rocm (gfx120X)\n"
                "linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)\n"
                "gfx1153: excluded entirely")
_PT_TEST_LW  = ("Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
                "linux-mi355-1gpu-ossci-rocm (gfx950)\n"
                "linux-gfx90a-gpu-rocm (gfx90a)\n"
                "linux-gfx1030-gpu-rocm (gfx103X)\n"
                "linux-gfx110X-gpu-rocm (gfx110X)\n"
                "linux-gfx1150-gpu-rocm (gfx1150)\n"
                "linux-gfx1151-gpu-rocm (gfx1151)\n"
                "linux-gfx1153-gpu-rocm (gfx1153)\n"
                "linux-gfx120X-gpu-rocm (gfx120X)\n"
                "linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)\n"
                "Windows: windows-gfx1151-gpu-rocm (gfx1151)\n"
                "windows-gfx110X-gpu-rocm (gfx110X)\n"
                "windows-gfx1030-gpu-rocm (gfx103X)\n"
                "windows-gfx120X-gpu-rocm (gfx120X)")
_JAX_BUILD   = "azure-linux-scale-rocm"
_JAX_TEST    = "linux-gfx942-1gpu-ossci-rocm (gfx94X only — other families built but not GPU-tested)"

FW_DATA = [
    # fw, version, py_vers, distro, linux_pkgs, win_pkgs, branch, nightly_gpu, ci_test, ni_test, build_runner, test_runner, notes
    ("PyTorch","2.8","3.10, 3.11, 3.12, 3.13",
     "Linux: Ubuntu 22.04 LTS (OSSCI scale pool)",
     "torch, torchaudio, torchvision, triton, apex","—",
     "ROCm/pytorch release/2.8",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx120X — Build + Test\nBuild-only: gfx900, gfx906, gfx908, gfx101X; gfx1153 excluded",
     "sanity + smoke (quick)","11 parallel jobs: Default suite (6) + Distributed training (3, 8-GPU runner) + Compiler/Inductor (2)",
     _PT_BUILD_L, _PT_TEST_28,
     "py3.14 excluded; aotriton incompatible with gfx90X/101X/103X/1152/1153"),
    ("PyTorch","2.9","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (OSSCI scale pool)\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex","torch, torchaudio, torchvision",
     "ROCm/pytorch release/2.9",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build + Test (Linux)\ngfx1151, gfx110X, gfx103X, gfx120X — Build + Test (Windows)\nBuild-only: gfx900/906/908/101X",
     "sanity + smoke (quick)","11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)",
     _PT_BUILD_LW, _PT_TEST_LW,
     "gfx1153 excluded Linux-only"),
    ("PyTorch","2.10 (default CI pin)","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (OSSCI scale pool)\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex","torch, torchaudio, torchvision",
     "ROCm/pytorch release/2.10",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build + Test (Linux)\ngfx1151, gfx110X, gfx103X, gfx120X — Build + Test (Windows)\nBuild-only: gfx900/906/908/101X",
     "sanity + smoke (quick)","11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)",
     _PT_BUILD_LW, _PT_TEST_LW,
     "Default CI pin"),
    ("PyTorch","2.11","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (OSSCI scale pool)\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex","torch, torchaudio, torchvision",
     "ROCm/pytorch release/2.11",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build + Test (Linux)\ngfx1151, gfx110X, gfx103X, gfx120X — Build + Test (Windows)\nBuild-only: gfx900/906/908/101X",
     "sanity + smoke (quick)","11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)",
     _PT_BUILD_LW, _PT_TEST_LW,
     ""),
    ("PyTorch","nightly","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (OSSCI scale pool)\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex","torch, torchaudio, torchvision",
     "pytorch/pytorch main",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build + Test (Linux)\ngfx1151, gfx110X, gfx103X, gfx120X — Build + Test (Windows)\nBuild-only: gfx900/906/908/101X",
     "sanity + smoke (quick)","11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)",
     _PT_BUILD_LW, _PT_TEST_LW,
     "Triton pin from pytorch/.ci/docker/ci_commit_pins/triton.txt"),
    ("JAX","0.8.0","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (release pipeline)",
     "jaxlib + jax_rocm7_plugin + jax_rocm7_pjrt","—",
     "ROCm/rocm-jax rocm-jaxlib-v0.8.0",
     "gfx94X — Build + Test\ngfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build-only (no GPU test)\nBuild-only (no HW runners): gfx900, gfx906, gfx908, gfx101X",
     "—","pytest: multi_device_test, core_test, util_test, scipy_stats_test (JAX_PLATFORMS=rocm)",
     _JAX_BUILD, _JAX_TEST,
     "Full jaxlib built from source"),
    ("JAX","0.8.2","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (release pipeline)",
     "jaxlib + jax_rocm7_plugin + jax_rocm7_pjrt","—",
     "ROCm/rocm-jax rocm-jaxlib-v0.8.2",
     "gfx94X — Build + Test\ngfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build-only (no GPU test)\nBuild-only (no HW runners): gfx900, gfx906, gfx908, gfx101X",
     "—","pytest: multi_device_test, core_test, util_test, scipy_stats_test",
     _JAX_BUILD, _JAX_TEST,
     "Full jaxlib from source"),
    ("JAX","0.9.0","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (release pipeline)",
     "jaxlib + jax_rocm7_plugin + jax_rocm7_pjrt","—",
     "ROCm/rocm-jax rocm-jaxlib-v0.9.0",
     "gfx94X — Build + Test\ngfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build-only (no GPU test)\nBuild-only (no HW runners): gfx900, gfx906, gfx908, gfx101X",
     "—","pytest: multi_device_test, core_test, util_test, scipy_stats_test",
     _JAX_BUILD, _JAX_TEST,
     "Full jaxlib from source"),
    ("JAX","0.9.1","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS (release pipeline)",
     "jax_rocm7_plugin + jax_rocm7_pjrt (jaxlib from PyPI)","—",
     "ROCm/rocm-jax rocm-jaxlib-v0.9.1",
     "gfx94X — Build + Test\ngfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build-only (no GPU test)\nBuild-only (no HW runners): gfx900, gfx906, gfx908, gfx101X",
     "—","pytest: multi_device_test, core_test, util_test, scipy_stats_test",
     _JAX_BUILD, _JAX_TEST,
     "jaxlib from upstream PyPI; only plugin+pjrt built from source"),
]

# ════════════════════════════════════════════════════════════════════════════
# BUILD WORKBOOK
# ════════════════════════════════════════════════════════════════════════════
wb = xlsxwriter.Workbook(OUT)

def fmt(wb, **kw):
    return wb.add_format(kw)

def _f(**kw):
    """Shorthand: add Arial 11 + center + vcenter defaults, then override with kw."""
    base = dict(font_name="Arial", font_size=11, align="center", valign="vcenter",
                text_wrap=True, border=1)
    base.update(kw)
    return fmt(wb, **base)

def auto_col_w(headers, data_rows, pad=2, mn=10, mx=60):
    """Calculate column widths from header and data content."""
    widths = [len(str(h)) for h in headers]
    for row in data_rows:
        for i, v in enumerate(row):
            if i < len(widths) and v and str(v) != "—":
                ml = max(len(line) for line in str(v).split("\n"))
                widths[i] = max(widths[i], ml)
    return [min(max(w + pad, mn), mx) for w in widths]

def auto_row_h(row_data, pts=14, mn=20):
    """Calculate row height from max line count in any cell."""
    lines = max((str(v).count("\n") + 1 for v in row_data if v and str(v) != "—"), default=1)
    return max(lines * pts, mn)

# ── Shared formats ────────────────────────────────────────────────────────────
title_fmt = fmt(wb, bold=True, font_name="Arial", font_size=12, font_color=WHITE,
                bg_color=AMD_RED, align="center", valign="vcenter")

# Tier-coloured header row 1 (group labels)
hdr_pc   = _f(bold=True, font_color=WHITE, bg_color=PC_BG,   font_size=10)
hdr_po   = _f(bold=True, font_color=WHITE, bg_color=PO_BG,   font_size=10)
hdr_ni   = _f(bold=True, font_color=WHITE, bg_color=NI_BG,   font_size=10)
hdr_meta = _f(bold=True, font_color=WHITE, bg_color=META_BG, font_size=10)
hdr_base = _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=10)

# Tier sub-headers row 2
sub_pc   = _f(bold=True, font_color=WHITE, bg_color=PC_SUB)
sub_po   = _f(bold=True, font_color=WHITE, bg_color=PO_SUB)
sub_ni   = _f(bold=True, font_color=WHITE, bg_color=NI_SUB)
sub_meta = _f(bold=True, font_color=WHITE, bg_color=META_BG)

yes_fmt  = _f(bg_color=YES_GRN, bold=True)
no_fmt   = _f(bg_color=NO_RED,  bold=True)
part_fmt = _f(bg_color=PART_YEL,bold=True)

# ─── Column layout ─────────────────────────────────────────────────────────────
# Fixed cols: Category(0), Sub-Cat(1), Component(2), Super Repo(3), CI Enabled(4)
# Pre-commit:  Linux gfx(5), Linux Runners(6), Windows gfx(7), Windows Runners(8), Test Type(9)
# Post-commit: Linux gfx(10), Linux Runners(11), Windows gfx(12), Windows Runners(13), Test Type(14)
# Nightly:     Linux gfx(15), Linux Runners(16), Windows gfx(17), Windows Runners(18), Test Type(19)
# Meta:        Platform(20), Notes(21)

_comp_hdr_labels = [
    "Category","Sub-Category","Component","Super Repo","CI Enabled",
    "Linux gfx","Linux Runners","Windows gfx","Windows Runners","Test Type",
    "Linux gfx","Linux Runners","Windows gfx","Windows Runners","Test Type",
    "Linux gfx","Linux Runners","Windows gfx","Windows Runners","Test Type",
    "Platform","Notes",
]
COL_WIDTHS = auto_col_w(_comp_hdr_labels, [list(c) for c in COMPONENTS])
TOTAL_COLS = len(COL_WIDTHS)   # 22

# ─── Sheet 1: Component CI Matrix ─────────────────────────────────────────────
ws1 = wb.add_worksheet("Component CI Matrix")
ws1.set_zoom(80)
ws1.freeze_panes(2, 5)   # freeze 2 header rows, 5 left columns
ws1.set_row(0, 36)
ws1.set_row(1, 28)

for ci, w in enumerate(COL_WIDTHS):
    ws1.set_column(ci, ci, w)

# Row 0: tier group headers
ws1.merge_range(0, 0, 1, 0, "Category",    hdr_base)
ws1.merge_range(0, 1, 1, 1, "Sub-Category",hdr_base)
ws1.merge_range(0, 2, 1, 2, "Component",   hdr_base)
ws1.merge_range(0, 3, 1, 3, "Super Repo",  hdr_base)
ws1.merge_range(0, 4, 1, 4, "CI\nEnabled", hdr_base)

ws1.merge_range(0, 5,  0, 9,  "Pre-commit (PR)",           hdr_pc)
ws1.merge_range(0, 10, 0, 14, "Post-commit (Sub Bump)",    hdr_po)
ws1.merge_range(0, 15, 0, 19, "CI Nightly",                hdr_ni)
ws1.merge_range(0, 20, 1, 20, "Platform",                  hdr_meta)
ws1.merge_range(0, 21, 1, 21, "Notes",                     hdr_meta)

# Row 1: sub-headers per tier
SUB_LABELS = ["Linux gfx", "Linux Runners", "Windows gfx", "Windows Runners", "Test Type"]
for base_col, sfmt in [(5, sub_pc), (10, sub_po), (15, sub_ni)]:
    for i, lbl in enumerate(SUB_LABELS):
        ws1.write(1, base_col + i, lbl, sfmt)

# Data rows
row = 2
for rec in COMPONENTS:
    (cat, sub, comp, repo, ci_en,
     pc_lgfx, pc_lr, pc_wgfx, pc_wr, pc_tt,
     po_lgfx, po_lr, po_wgfx, po_wr, po_tt,
     ni_lgfx, ni_lr, ni_wgfx, ni_wr, ni_tt,
     plat, notes) = rec

    bg = sub_bg_map.get(sub, cat_bg.get(cat, WHITE))

    def cell(wb_=wb, bg_=bg):
        return _f(bg_color=bg_)

    cf = cell()
    ci_fmt = (yes_fmt if ci_en == "Yes"
              else no_fmt if ci_en == "No"
              else part_fmt)

    ws1.set_row(row, auto_row_h(list(rec)))
    vals = [cat, sub, comp, repo, ci_en,
            pc_lgfx, pc_lr, pc_wgfx, pc_wr, pc_tt,
            po_lgfx, po_lr, po_wgfx, po_wr, po_tt,
            ni_lgfx, ni_lr, ni_wgfx, ni_wr, ni_tt,
            plat, notes]
    for ci2, v in enumerate(vals):
        ws1.write(row, ci2, v, ci_fmt if ci2 == 4 else cell())
    row += 1

ws1.autofilter(1, 0, row-1, TOTAL_COLS-1)

# ── Server count summary table below component data (mirrors HTML section) ────
_sc_gap = 2   # blank rows between matrix and summary
_sc_start = row + _sc_gap

# Title banner
ws1.merge_range(_sc_start, 0, _sc_start, TOTAL_COLS-1,
                "Component CI Matrix — Unique Server Counts by Tier",
                _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=11))

_sc_hdr_labels = ["CI Tier", "Pool Type", "Count", "Azure Build Pool (no GPU)",
                  "Physical GPU Machines", "Runner Labels & Counts", "Notes"]
_sc_hdr_fmt = _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=10)
_sc_col_w   = [18, 22, 10, 28, 22, 60, 40]
for ci, w in enumerate(_sc_col_w):
    ws1.set_column(ci, ci, max(COL_WIDTHS[ci] if ci < len(COL_WIDTHS) else w, w))

_sc_r = _sc_start + 1
for ci, h in enumerate(_sc_hdr_labels):
    ws1.write(_sc_r, ci, h, _sc_hdr_fmt)
_sc_r += 1

# Re-derive counts (same logic as HTML generator)
import re as _re
def _psc(s):
    m = _re.match(r'\s*~?\s*(\d+)', str(s))
    return int(m.group(1)) if m else 0
_rc = {rec[0]: _psc(rec[4]) for rec in RUNNER_DATA}
_build_vms_x   = _rc.get("azure-linux-scale-rocm", 0) + _rc.get("azure-windows-scale-rocm", 0)
_pc_gpu_x      = _rc.get("linux-gfx942-1gpu-ossci-rocm", 0) + _rc.get("windows-gfx1151-gpu-rocm", 0)
_po_gpu_x      = _pc_gpu_x + _rc.get("linux-mi355-1gpu-ossci-rocm", 0)
_ni_gpu_labels = [
    ("linux-gfx942-1gpu-ossci-rocm","gfx94X"),("linux-gfx942-8gpu-ossci-rocm","gfx94X 8-GPU"),
    ("linux-mi355-1gpu-ossci-rocm","gfx950"),("linux-gfx90a-gpu-rocm","gfx90a"),
    ("linux-gfx1030-gpu-rocm","gfx103X L"),("linux-gfx110X-gpu-rocm","gfx110X L"),
    ("linux-gfx1150-gpu-rocm","gfx1150"),("linux-gfx1151-gpu-rocm","gfx1151 L"),
    ("linux-gfx1153-gpu-rocm","gfx1153"),("linux-gfx120X-gpu-rocm","gfx120X"),
    ("windows-gfx1151-gpu-rocm","gfx1151 W"),("windows-gfx110X-gpu-rocm","gfx110X W"),
    ("windows-gfx1030-gpu-rocm","gfx103X W"),
]
_ni_gpu_x = sum(_rc.get(lbl,0) for lbl,_ in _ni_gpu_labels)

_tier_yellow = "#FFF9E6"
_tier_blue   = "#EBF3FB"
_tier_green  = "#EBF5EB"
_tier_orange = "#FFF3E0"
_subtot_blue = "#D0E8F8"
_subtot_grn  = "#C8E6C9"
_subtot_org  = "#FFE0B2"
_grand_bg    = BASE_BG

def _sc_fmt(bg, bold=False, color="#1A1A1A"):
    return _f(bg_color=bg, bold=bold, font_color=color, align="left", font_size=10)
def _sc_num(bg, bold=False, color="#1A1A1A"):
    return _f(bg_color=bg, bold=bold, font_color=color, align="center", font_size=12)

# All Tiers — Azure Build Pool
ws1.merge_range(_sc_r, 0, _sc_r+1, 0, "All Tiers", _sc_fmt(_tier_yellow, bold=True, color="#555555"))
ws1.write(_sc_r, 1, "Azure Build Pool\n(cloud VMs, no GPU — compile & package only)", _sc_fmt(_tier_yellow))
ws1.write(_sc_r, 2, _build_vms_x, _sc_num(_tier_yellow))
ws1.write(_sc_r, 3, f"Linux VMs: {_rc.get('azure-linux-scale-rocm',0)}\nWindows VMs: {_rc.get('azure-windows-scale-rocm',0)}", _sc_fmt(_tier_yellow))
ws1.write(_sc_r, 4, "— (no GPU)", _sc_fmt(_tier_yellow, color="#999"))
ws1.write(_sc_r, 5, f"azure-linux-scale-rocm = {_rc.get('azure-linux-scale-rocm',0)}  •  azure-windows-scale-rocm = {_rc.get('azure-windows-scale-rocm',0)}", _sc_fmt(_tier_yellow))
ws1.write(_sc_r, 6, "Shared across all tiers; elastic — can scale beyond snapshot count under load", _sc_fmt(_tier_yellow, color="#555"))
ws1.set_row(_sc_r, auto_row_h([f"azure-linux-scale-rocm = {_rc.get('azure-linux-scale-rocm',0)}  •  azure-windows-scale-rocm = {_rc.get('azure-windows-scale-rocm',0)}", "Azure Build Pool\n(cloud VMs, no GPU — compile & package only)"]))
_sc_r += 1
ws1.write(_sc_r, 1, "Build Subtotal", _sc_fmt(_tier_yellow, bold=True))
ws1.write(_sc_r, 2, _build_vms_x, _sc_num(_tier_yellow, bold=True))
ws1.write(_sc_r, 3, f"{_build_vms_x} VMs total ({_rc.get('azure-linux-scale-rocm',0)} Linux + {_rc.get('azure-windows-scale-rocm',0)} Windows)", _sc_fmt(_tier_yellow))
ws1.write(_sc_r, 4, "No GPU hardware", _sc_fmt(_tier_yellow, color="#999"))
ws1.write(_sc_r, 5, "", _sc_fmt(_tier_yellow))
ws1.write(_sc_r, 6, "Azure-managed; no physical server count exposed", _sc_fmt(_tier_yellow, color="#555"))
ws1.set_row(_sc_r, 22)
_sc_r += 1

# Pre-commit
ws1.merge_range(_sc_r, 0, _sc_r+1, 0, "Pre-commit\n(PR)", _sc_fmt(_tier_blue, bold=True, color=PC_BG))
ws1.write(_sc_r, 1, "GPU Test Pool\n(2 physical runner types)", _sc_fmt(_tier_blue))
ws1.write(_sc_r, 2, _pc_gpu_x, _sc_num(_tier_blue, bold=True, color=PC_BG))
ws1.write(_sc_r, 3, f"Build VMs: {_build_vms_x} (shared)", _sc_fmt(_tier_blue, color="#555"))
ws1.write(_sc_r, 4, f"{_pc_gpu_x} unique nodes", _sc_fmt(_tier_blue))
_pc_breakdown = (f"linux-gfx942-1gpu-ossci-rocm (gfx94X) = {_rc.get('linux-gfx942-1gpu-ossci-rocm',0)}\n"
                 f"windows-gfx1151-gpu-rocm (gfx1151, build-only) = {_rc.get('windows-gfx1151-gpu-rocm',0)}")
ws1.write(_sc_r, 5, _pc_breakdown, _sc_fmt(_tier_blue))
ws1.write(_sc_r, 6, "gfx94X: Build + Test  •  gfx1151 Win: Build-only (nightly_check_only)", _sc_fmt(_tier_blue, color="#555"))
ws1.set_row(_sc_r, auto_row_h([_pc_breakdown]))
_sc_r += 1
ws1.write(_sc_r, 1, "Pre-commit Subtotal", _sc_fmt(_subtot_blue, bold=True))
ws1.write(_sc_r, 2, _pc_gpu_x, _sc_num(_subtot_blue, bold=True, color=PC_BG))
ws1.write(_sc_r, 3, f"{_build_vms_x} shared build VMs", _sc_fmt(_subtot_blue, color="#555"))
ws1.write(_sc_r, 4, f"{_pc_gpu_x} physical GPU", _sc_fmt(_subtot_blue))
ws1.write(_sc_r, 5, f"{_build_vms_x} Azure VMs  +  {_pc_gpu_x} GPU machines  =  {_build_vms_x + _pc_gpu_x} total", _sc_fmt(_subtot_blue))
ws1.write(_sc_r, 6, "", _sc_fmt(_subtot_blue))
ws1.set_row(_sc_r, 22)
_sc_r += 1

# Post-commit
ws1.merge_range(_sc_r, 0, _sc_r+1, 0, "Post-commit\n(Sub Bump)", _sc_fmt(_tier_green, bold=True, color=PO_BG))
ws1.write(_sc_r, 1, "GPU Test Pool\n(3 physical runner types)", _sc_fmt(_tier_green))
ws1.write(_sc_r, 2, _po_gpu_x, _sc_num(_tier_green, bold=True, color=PO_BG))
ws1.write(_sc_r, 3, f"Build VMs: {_build_vms_x} (shared)", _sc_fmt(_tier_green, color="#555"))
ws1.write(_sc_r, 4, f"{_po_gpu_x} unique nodes", _sc_fmt(_tier_green))
_po_breakdown = (f"linux-gfx942-1gpu-ossci-rocm (gfx94X) = {_rc.get('linux-gfx942-1gpu-ossci-rocm',0)}\n"
                 f"linux-mi355-1gpu-ossci-rocm (gfx950/MI355X) = {_rc.get('linux-mi355-1gpu-ossci-rocm',0)}\n"
                 f"windows-gfx1151-gpu-rocm (gfx1151, build-only) = {_rc.get('windows-gfx1151-gpu-rocm',0)}")
ws1.write(_sc_r, 5, _po_breakdown, _sc_fmt(_tier_green))
ws1.write(_sc_r, 6, "Adds gfx950 (MI355X) vs Pre-commit; gfx1151 Win remains build-only", _sc_fmt(_tier_green, color="#555"))
ws1.set_row(_sc_r, auto_row_h([_po_breakdown]))
_sc_r += 1
ws1.write(_sc_r, 1, "Post-commit Subtotal", _sc_fmt(_subtot_grn, bold=True))
ws1.write(_sc_r, 2, _po_gpu_x, _sc_num(_subtot_grn, bold=True, color=PO_BG))
ws1.write(_sc_r, 3, f"{_build_vms_x} shared build VMs", _sc_fmt(_subtot_grn, color="#555"))
ws1.write(_sc_r, 4, f"{_po_gpu_x} physical GPU", _sc_fmt(_subtot_grn))
ws1.write(_sc_r, 5, f"{_build_vms_x} Azure VMs  +  {_po_gpu_x} GPU machines  =  {_build_vms_x + _po_gpu_x} total", _sc_fmt(_subtot_grn))
ws1.write(_sc_r, 6, "", _sc_fmt(_subtot_grn))
ws1.set_row(_sc_r, 22)
_sc_r += 1

# Nightly
_ni_breakdown = "  •  ".join(f"{desc} ({lbl}) = {_rc.get(lbl,0)}" for lbl, desc in _ni_gpu_labels)
ws1.merge_range(_sc_r, 0, _sc_r+1, 0, "CI Nightly", _sc_fmt(_tier_orange, bold=True, color=NI_BG))
ws1.write(_sc_r, 1, f"GPU Test Pool\n({len(_ni_gpu_labels)} physical runner types)", _sc_fmt(_tier_orange))
ws1.write(_sc_r, 2, _ni_gpu_x, _sc_num(_tier_orange, bold=True, color=NI_BG))
ws1.write(_sc_r, 3, f"Build VMs: {_build_vms_x} (shared)", _sc_fmt(_tier_orange, color="#555"))
ws1.write(_sc_r, 4, f"{_ni_gpu_x} unique nodes", _sc_fmt(_tier_orange))
ws1.write(_sc_r, 5, "\n".join(f"{lbl} ({desc}) = {_rc.get(lbl,0)}" for lbl, desc in _ni_gpu_labels), _sc_fmt(_tier_orange))
ws1.write(_sc_r, 6, "Full GPU family coverage — all unique physical machines, each counted once", _sc_fmt(_tier_orange, color="#555"))
ws1.set_row(_sc_r, auto_row_h(["\n".join(f"{lbl} ({desc}) = {_rc.get(lbl,0)}" for lbl, desc in _ni_gpu_labels)]))
_sc_r += 1
ws1.write(_sc_r, 1, "Nightly Subtotal", _sc_fmt(_subtot_org, bold=True))
ws1.write(_sc_r, 2, _ni_gpu_x, _sc_num(_subtot_org, bold=True, color=NI_BG))
ws1.write(_sc_r, 3, f"{_build_vms_x} shared build VMs", _sc_fmt(_subtot_org, color="#555"))
ws1.write(_sc_r, 4, f"{_ni_gpu_x} physical GPU", _sc_fmt(_subtot_org))
ws1.write(_sc_r, 5, f"{_build_vms_x} Azure VMs  +  {_ni_gpu_x} GPU machines  =  {_build_vms_x + _ni_gpu_x} total", _sc_fmt(_subtot_org))
ws1.write(_sc_r, 6, "", _sc_fmt(_subtot_org))
ws1.set_row(_sc_r, 22)
_sc_r += 1

# Grand total
_sc_grand_fmt     = _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=11, align="center")
_sc_grand_sub_fmt = _f(bold=False, font_color=WHITE, bg_color=BASE_BG, font_size=10, align="left")
ws1.merge_range(_sc_r, 0, _sc_r, 1, "Grand Total (all tiers, unique)", _sc_grand_fmt)
ws1.write(_sc_r, 2, _build_vms_x + _ni_gpu_x, _sc_grand_fmt)
ws1.write(_sc_r, 3, f"{_build_vms_x} VMs (Azure, no GPU)", _sc_grand_sub_fmt)
ws1.write(_sc_r, 4, f"{_ni_gpu_x} physical (unique GPU)", _sc_grand_sub_fmt)
ws1.write(_sc_r, 5, f"{_build_vms_x} Azure build VMs  +  {_ni_gpu_x} unique GPU machines  =  {_build_vms_x + _ni_gpu_x}   (each GPU machine counted once regardless of how many tiers use it)", _sc_grand_sub_fmt)
ws1.write(_sc_r, 6, "", _sc_grand_sub_fmt)
ws1.set_row(_sc_r, 28)

# ─── Sheet 2: CI Tiers ────────────────────────────────────────────────────────
TIER_HEADERS = ["CI Tier","Trigger","Schedule","Test Type",
                "Linux GPU Families","Windows GPU Families",
                "Frameworks Built","Distro","Windows Distro"]
TIER_COL_W   = auto_col_w(TIER_HEADERS, [list(r) for r in TIER_DATA])

ws2 = wb.add_worksheet("CI Tiers")
ws2.set_zoom(85)
ws2.freeze_panes(1, 0)
ws2.set_row(0, 30)

for ci, w in enumerate(TIER_COL_W):
    ws2.set_column(ci, ci, w)
for ci, h in enumerate(TIER_HEADERS):
    ws2.write(0, ci, h, hdr_base)

tier_colors = ["#E3F2FD","#E8F5E9","#FFF8E1","#FCE4EC","#F3E5F5"]
row = 1
for i, rec in enumerate(TIER_DATA):
    bg = tier_colors[i % len(tier_colors)]
    f  = _f(bg_color=bg)
    ws2.set_row(row, auto_row_h(list(rec)))
    for ci2, v in enumerate(rec):
        ws2.write(row, ci2, v, f)
    row += 1

# ─── Sheet 3: Framework Detail ────────────────────────────────────────────────
FW_HEADERS = [
    "Framework","Version","Python Versions","Distro",
    "Linux Packages","Windows Packages","Branch / Ref",
    "Nightly GPU",
    "CI Test Suite","Nightly Full Test",
    "Build Runner","Test Runner","Notes"
]
FW_COL_W = auto_col_w(FW_HEADERS, [list(r) for r in FW_DATA])

ws3 = wb.add_worksheet("Framework Detail")
ws3.set_zoom(85)
ws3.freeze_panes(1, 2)
ws3.set_row(0, 30)

for ci, w in enumerate(FW_COL_W):
    ws3.set_column(ci, ci, w)
for ci, h in enumerate(FW_HEADERS):
    ws3.write(0, ci, h, hdr_base)

_fw_colors = {"PyTorch":"#E3F2FD","JAX":"#E8F5E9"}
row = 1
for i, rec in enumerate(FW_DATA):
    bg = _fw_colors.get(rec[0], "#F5F5F5")
    f  = _f(bg_color=bg)
    ws3.set_row(row, auto_row_h(list(rec)))
    for ci2, v in enumerate(rec):
        ws3.write(row, ci2, v, f)
    row += 1

ws3.autofilter(0, 0, row-1, len(FW_HEADERS)-1)

# ─── Sheet 4: Runner Inventory ────────────────────────────────────────────────
RUNNER_HEADERS = ["#","Runner Label","Platform","OS / Distro","Location",
                  "Physical Machines","GPU Family","GPU ISA","GPU Count","Used At","Notes"]
R_COL_W = [4] + auto_col_w(RUNNER_HEADERS[1:], [list(r) for r in RUNNER_DATA])

ws4 = wb.add_worksheet("Runner Inventory")
ws4.set_zoom(85)
ws4.freeze_panes(1, 0)
ws4.set_row(0, 30)

for ci, w in enumerate(R_COL_W):
    ws4.set_column(ci, ci, w)
for ci, h in enumerate(RUNNER_HEADERS):
    ws4.write(0, ci, h, hdr_base)

# ── Location summary (Physical GPU Machines by Location) ─────────────────────
from collections import defaultdict as _ddict
_loc_sum = _ddict(lambda: {"count": 0, "linux": 0, "windows": 0, "runners": []})
for _rec in RUNNER_DATA:
    # RUNNER_DATA has 11 fields in generate_rocm_html.py but only 10 in rocm_ci_data.py
    if len(_rec) == 11:
        _lbl, _plat, _os, _loc, _phys, _gpu_fam, _isa, _cnt, _used, _notes, _cls = _rec
    else:
        _lbl, _plat, _os, _loc, _phys, _gpu_fam, _isa, _cnt, _used, _notes = _rec
        _cls = "runner-linux" if _plat == "Linux" else "runner-windows" if _plat == "Windows" else "runner-build"
    if _cls in ("runner-linux", "runner-windows"):
        _n = _psc(_phys)
        if _n > 0:
            _lk = "On-Prem" if _loc.startswith("On-Prem") else _loc
            _loc_sum[_lk]["count"] += _n
            _loc_sum[_lk]["runners"].append(_lbl)
            if _cls == "runner-linux":
                _loc_sum[_lk]["linux"] += _n
            else:
                _loc_sum[_lk]["windows"] += _n
_loc_tot = sum(v["count"] for v in _loc_sum.values())

_loc_hdr_labels = ["Location", "Physical Machines", "Linux", "Windows", "Share %"]
_loc_hdr_fmt    = _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=10)
_loc_colors     = {"OSSCI": "#1565C0", "On-Prem": "#2E7D32", "GitHub-hosted": "#555555"}
_loc_col_w      = [14, 18, 10, 10, 10]
for ci, w in enumerate(_loc_col_w):
    ws4.set_column(ci, ci, max(R_COL_W[ci] if ci < len(R_COL_W) else w, w))

# Title
ws4.merge_range(0, 0, 0, len(RUNNER_HEADERS)-1,
                "Physical GPU Machines by Location", _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=11))
ws4.set_row(0, 26)

# Location summary header
_ls_r = 1
for ci, h in enumerate(_loc_hdr_labels):
    ws4.write(_ls_r, ci, h, _loc_hdr_fmt)
ws4.set_row(_ls_r, 22)
_ls_r += 1

for _lk, _data in sorted(_loc_sum.items()):
    _pct = round(_data["count"] / _loc_tot * 100) if _loc_tot else 0
    _lc  = _loc_colors.get(_lk, "#555555")
    _num_fmt = _f(bg_color="#EBF3FB" if _lk == "OSSCI" else "#EBF5EB", align="center", font_size=10)
    ws4.write(_ls_r, 0, _lk, _f(bg_color=_lc, bold=True, font_color=WHITE, align="center", font_size=10))
    ws4.write(_ls_r, 1, _data["count"], _num_fmt)
    ws4.write(_ls_r, 2, _data["linux"] if _data["linux"] else "—", _num_fmt)
    ws4.write(_ls_r, 3, _data["windows"] if _data["windows"] else "—", _num_fmt)
    ws4.write(_ls_r, 4, f"{_pct}%", _num_fmt)
    ws4.set_row(_ls_r, 18)
    _ls_r += 1

# Total row
_tot_fmt = _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=10)
ws4.write(_ls_r, 0, "Total", _tot_fmt)
ws4.write(_ls_r, 1, _loc_tot, _tot_fmt)
ws4.write(_ls_r, 2, sum(v["linux"] for v in _loc_sum.values()), _tot_fmt)
ws4.write(_ls_r, 3, sum(v["windows"] for v in _loc_sum.values()), _tot_fmt)
ws4.write(_ls_r, 4, "100%", _tot_fmt)
ws4.set_row(_ls_r, 22)
_ls_r += 1

# Blank separator row
_ls_r += 1

# Runner inventory header
_inv_hdr_row = _ls_r
for ci, h in enumerate(RUNNER_HEADERS):
    ws4.write(_inv_hdr_row, ci, h, _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=10))
ws4.set_row(_inv_hdr_row, 22)
_ls_r += 1

plat_colors = {"Linux": "#EBF3FB", "Windows": "#EBF5EB"}
row = _ls_r
for _ri, rec in enumerate(RUNNER_DATA, 1):
    bg = plat_colors.get(rec[1], WHITE)
    f  = _f(bg_color=bg)
    ws4.set_row(row, auto_row_h(list(rec)))
    ws4.write(row, 0, _ri, f)
    for ci2, v in enumerate(rec):
        ws4.write(row, ci2+1, v, f)
    row += 1

ws4.autofilter(_inv_hdr_row, 0, row-1, len(RUNNER_HEADERS)-1)

# ── Framework Runner & Server Count Details ───────────────────────────────────
_fw_sc_r = row + 2   # blank gap after runner inventory

# Section banner
ws4.merge_range(_fw_sc_r, 0, _fw_sc_r, len(RUNNER_HEADERS)-1,
                "Framework Runner & Server Count Details",
                _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=11))
ws4.set_row(_fw_sc_r, 26)
_fw_sc_r += 1

# Column headers
_fw_sc_cols = ["Framework", "Pool", "Count", "Build (VMs)", "GPU Test (Physical)",
               "Runner Labels & Counts", "Coverage"]
_fw_sc_col_w = [12, 28, 10, 22, 22, 55, 35]
for ci, w in enumerate(_fw_sc_col_w):
    ws4.set_column(ci, ci, max(R_COL_W[ci] if ci < len(R_COL_W) else w, w))
for ci, h in enumerate(_fw_sc_cols):
    ws4.write(_fw_sc_r, ci, h, _f(bold=True, font_color=WHITE, bg_color="#37474F", font_size=10))
ws4.set_row(_fw_sc_r, 22)
_fw_sc_r += 1

# Re-use counts already derived for Sheet 1
_pt_build_lin  = _rc.get("azure-linux-scale-rocm", 0)
_pt_build_win  = _rc.get("azure-windows-scale-rocm", 0)
_pt_build_tot  = _pt_build_lin + _pt_build_win
_pt_gpu_total  = _ni_gpu_x   # same unique set
_pt_total      = _pt_build_tot + _pt_gpu_total
_jax_gpu       = _rc.get("linux-gfx942-1gpu-ossci-rocm", 0)

_pt_bg   = "#E3F2FD"
_pt_sub  = "#D0E8F8"
_jax_bg  = "#E8F5E9"
_jax_sub = "#C8E6C9"
_grand_row_fmt = _f(bold=True, font_color=WHITE, bg_color=BASE_BG, font_size=10)

def _fsc(bg, bold=False, color="#1A1A1A"):
    return _f(bg_color=bg, bold=bold, font_color=color, align="left", font_size=10)
def _fsc_c(bg, bold=False, color="#1A1A1A"):
    return _f(bg_color=bg, bold=bold, font_color=color, align="center", font_size=10)

# PyTorch — Build Pool
ws4.merge_range(_fw_sc_r, 0, _fw_sc_r+2, 0, "PyTorch",
                _f(bold=True, font_color="#1F4E79", bg_color=_pt_bg, align="center", font_size=11))
ws4.write(_fw_sc_r, 1, "Build Pool (2 VM pools, no GPU)", _fsc(_pt_bg))
ws4.write(_fw_sc_r, 2, _pt_build_tot, _fsc_c(_pt_bg, bold=True))
ws4.write(_fw_sc_r, 3, f"Linux VMs: {_pt_build_lin}\nWindows VMs: {_pt_build_win}", _fsc(_pt_bg))
ws4.write(_fw_sc_r, 4, "— (no GPU)", _fsc(_pt_bg, color="#999"))
ws4.write(_fw_sc_r, 5, f"azure-linux-scale-rocm = {_pt_build_lin} VMs  •  azure-windows-scale-rocm = {_pt_build_win} VMs", _fsc(_pt_bg))
ws4.write(_fw_sc_r, 6, "Elastic; auto-scales under load; used for all compile/package jobs", _fsc(_pt_bg, color="#555"))
ws4.set_row(_fw_sc_r, 30)
_fw_sc_r += 1

# PyTorch — GPU Test Pool
_gpu_breakdown = "  •  ".join(f"{lbl} = {_rc.get(lbl,0)}" for lbl, _ in _ni_gpu_labels)
ws4.write(_fw_sc_r, 1, f"GPU Test Pool ({len(_ni_gpu_labels)} physical runner types)", _fsc(_pt_bg))
ws4.write(_fw_sc_r, 2, _pt_gpu_total, _fsc_c(_pt_bg, bold=True))
ws4.write(_fw_sc_r, 3, "— (no build VMs here)", _fsc(_pt_bg, color="#999"))
ws4.write(_fw_sc_r, 4, f"{_pt_gpu_total} unique physical machines", _fsc_c(_pt_bg))
ws4.write(_fw_sc_r, 5, _gpu_breakdown, _fsc(_pt_bg))
ws4.write(_fw_sc_r, 6, f"5 PyTorch versions × 5 Python vers × {len(_ni_gpu_labels)} GPU runner types", _fsc(_pt_bg, color="#555"))
ws4.set_row(_fw_sc_r, 30)
_fw_sc_r += 1

# PyTorch — Subtotal
ws4.write(_fw_sc_r, 1, "PyTorch Total", _fsc(_pt_sub, bold=True))
ws4.write(_fw_sc_r, 2, _pt_total, _fsc_c(_pt_sub, bold=True, color="#1F4E79"))
ws4.write(_fw_sc_r, 3, f"{_pt_build_tot} build VMs", _fsc(_pt_sub))
ws4.write(_fw_sc_r, 4, f"{_pt_gpu_total} physical GPU", _fsc(_pt_sub))
ws4.write(_fw_sc_r, 5, f"{_pt_build_tot} build VMs + {_pt_gpu_total} physical GPU machines = {_pt_total}", _fsc(_pt_sub))
ws4.write(_fw_sc_r, 6, "Mixed: VMs + physical", _fsc(_pt_sub, color="#555"))
ws4.set_row(_fw_sc_r, 22)
_fw_sc_r += 1

# JAX — Build + Test
ws4.merge_range(_fw_sc_r, 0, _fw_sc_r+1, 0, "JAX",
                _f(bold=True, font_color="#2E7D32", bg_color=_jax_bg, align="center", font_size=11))
ws4.write(_fw_sc_r, 1, "Build + Test (shared build VM pool)", _fsc(_jax_bg))
ws4.write(_fw_sc_r, 2, _jax_gpu, _fsc_c(_jax_bg, bold=True))
ws4.write(_fw_sc_r, 3, "Shared with PyTorch — azure-linux-scale-rocm (not counted separately)", _fsc(_jax_bg, color="#777"))
ws4.write(_fw_sc_r, 4, f"{_jax_gpu} physical (gfx94X only)", _fsc_c(_jax_bg))
ws4.write(_fw_sc_r, 5, f"linux-gfx942-1gpu-ossci-rocm = {_jax_gpu} physical  |  Build: shared azure-linux-scale-rocm VMs", _fsc(_jax_bg))
ws4.write(_fw_sc_r, 6, "4 JAX versions × 4 Python vers × 1 GPU runner type", _fsc(_jax_bg, color="#555"))
ws4.set_row(_fw_sc_r, 30)
_fw_sc_r += 1

# JAX — Subtotal
ws4.write(_fw_sc_r, 1, "JAX Total", _fsc(_jax_sub, bold=True))
ws4.write(_fw_sc_r, 2, _jax_gpu, _fsc_c(_jax_sub, bold=True, color="#2E7D32"))
ws4.write(_fw_sc_r, 3, "Build VMs shared with PyTorch — not counted separately", _fsc(_jax_sub, color="#555"))
ws4.write(_fw_sc_r, 4, f"{_jax_gpu} physical only", _fsc_c(_jax_sub))
ws4.write(_fw_sc_r, 5, f"{_jax_gpu} dedicated physical GPU machines + shared build VM pool (counted under PyTorch)", _fsc(_jax_sub, color="#555"))
ws4.write(_fw_sc_r, 6, "JAX reuses linux-gfx942-1gpu-ossci-rocm from PyTorch pool", _fsc(_jax_sub, color="#555"))
ws4.set_row(_fw_sc_r, 22)
_fw_sc_r += 1

# Grand Total
_grand_total = _pt_build_tot + _pt_gpu_total
ws4.merge_range(_fw_sc_r, 0, _fw_sc_r, 1, "Grand Total (PyTorch + JAX)", _grand_row_fmt)
ws4.write(_fw_sc_r, 2, _grand_total, _f(bold=True, font_color=WHITE, bg_color=BASE_BG, align="center", font_size=11))
ws4.write(_fw_sc_r, 3, f"{_pt_build_tot} VMs (shared build pool)", _f(font_color=WHITE, bg_color=BASE_BG, font_size=10))
ws4.write(_fw_sc_r, 4, f"{_pt_gpu_total} physical (unique GPU machines; JAX shares PyTorch pool)", _f(font_color=WHITE, bg_color=BASE_BG, font_size=10))
ws4.merge_range(_fw_sc_r, 5, _fw_sc_r, 6,
                f"{_pt_build_tot} shared build VMs + {_pt_gpu_total} unique physical GPU machines = {_grand_total}   |   GPU node counts per tier — each physical machine counted once",
                _f(font_color=WHITE, bg_color=BASE_BG, font_size=10))
ws4.set_row(_fw_sc_r, 26)

# ─── Sheet 5: Wheel Artifact Publishing ───────────────────────────────────────
WH_HEADERS = [
    "Framework","Version","Python Versions","Distro","Wheel Packages",
    "GPU Families — Wheel Published","GPU Families — Build-only (no upload)",
    "Build Trigger","Build Runner","Smoke Test Runner","Notes"
]
_WH_SMOKE_PT = "ubuntu-24.04 (GitHub-hosted)\nUBI10 container smoke install (Ubuntu 24.04 + UBI10)"
_WH_SMOKE_JAX = "—"

WH_DATA = [
    # fw, version, py_vers, distro, wheel_pkgs, gpu_published, gpu_build_only, trigger, build_runner, smoke_runner, notes
    ("PyTorch","2.8","3.10, 3.11, 3.12, 3.13",
     "Linux: Ubuntu 22.04 LTS",
     "torch, torchaudio, torchvision, triton, apex (Linux only)",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "CI pipeline (post-merge push to release/2.8)",
     "Linux: azure-linux-scale-rocm", _WH_SMOKE_PT,
     "py3.14 excluded; gfx1153 excluded entirely; Windows: no wheel upload for 2.8"),
    ("PyTorch","2.9","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex (Linux)\ntorch, torchaudio, torchvision (Windows)",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X\nWindows: gfx1151, gfx110X, gfx103X, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "CI pipeline (post-merge push to release/2.9)",
     "Linux: azure-linux-scale-rocm\nWindows: azure-windows-scale-rocm", _WH_SMOKE_PT,
     ""),
    ("PyTorch","2.10 (default CI pin)","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex (Linux)\ntorch, torchaudio, torchvision (Windows)",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X\nWindows: gfx1151, gfx110X, gfx103X, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "CI pipeline (post-merge push to release/2.10) + 02:00 UTC daily (ci_nightly.yml)",
     "Linux: azure-linux-scale-rocm\nWindows: azure-windows-scale-rocm", _WH_SMOKE_PT,
     "Default CI pin branch"),
    ("PyTorch","2.11","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex (Linux)\ntorch, torchaudio, torchvision (Windows)",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X\nWindows: gfx1151, gfx110X, gfx103X, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "CI pipeline (post-merge push to release/2.11)",
     "Linux: azure-linux-scale-rocm\nWindows: azure-windows-scale-rocm", _WH_SMOKE_PT,
     ""),
    ("PyTorch","nightly","3.10, 3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS\nWindows: Windows 11",
     "torch, torchaudio, torchvision, triton, apex (Linux)\ntorch, torchaudio, torchvision (Windows)",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X\nWindows: gfx1151, gfx110X, gfx103X, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "02:00 UTC daily (ci_nightly.yml) + on push to pytorch/pytorch main",
     "Linux: azure-linux-scale-rocm\nWindows: azure-windows-scale-rocm", _WH_SMOKE_PT,
     "Triton pin from pytorch/.ci/docker/ci_commit_pins/triton.txt"),
    ("JAX","0.8.0","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS",
     "jaxlib, jax_rocm7_plugin, jax_rocm7_pjrt",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "Release pipeline (externally triggered)",
     "azure-linux-scale-rocm", _WH_SMOKE_JAX,
     "Full jaxlib built from source"),
    ("JAX","0.8.2","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS",
     "jaxlib, jax_rocm7_plugin, jax_rocm7_pjrt",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "Release pipeline (externally triggered)",
     "azure-linux-scale-rocm", _WH_SMOKE_JAX,
     "Full jaxlib built from source"),
    ("JAX","0.9.0","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS",
     "jaxlib, jax_rocm7_plugin, jax_rocm7_pjrt",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "Release pipeline (externally triggered)",
     "azure-linux-scale-rocm", _WH_SMOKE_JAX,
     "Full jaxlib built from source"),
    ("JAX","0.9.1","3.11, 3.12, 3.13, 3.14",
     "Linux: Ubuntu 22.04 LTS",
     "jax_rocm7_plugin, jax_rocm7_pjrt (jaxlib from PyPI)",
     "Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X",
     "Linux: gfx900, gfx906, gfx908, gfx101X",
     "Release pipeline (externally triggered)",
     "azure-linux-scale-rocm", _WH_SMOKE_JAX,
     "jaxlib from upstream PyPI; only plugin+pjrt built from source"),
]

ws5 = wb.add_worksheet("Wheel Artifact Publishing")
ws5.set_zoom(85)
ws5.freeze_panes(1, 0)
ws5.set_row(0, 30)

WH_COL_W = auto_col_w(WH_HEADERS, [list(r) for r in WH_DATA])
for ci, w in enumerate(WH_COL_W):
    ws5.set_column(ci, ci, w)
for ci, h in enumerate(WH_HEADERS):
    ws5.write(0, ci, h, hdr_base)

row = 1
for i, rec in enumerate(WH_DATA):
    bg = _fw_colors.get(rec[0], "#F5F5F5")
    f  = _f(bg_color=bg)
    ws5.set_row(row, auto_row_h(list(rec)))
    for ci2, v in enumerate(rec):
        ws5.write(row, ci2, v, f)
    row += 1

ws5.autofilter(0, 0, row-1, len(WH_HEADERS)-1)

# ─── Sheets 6–8: InferenceMAX Benchmark Data, Runners, and Workflows ────────
# Load inference data from rocm_ci_data.py (only present after fetch_rocm_data.py runs)
_inf_ns: dict = {}
_inf_data_file = _HERE / "rocm_ci_data.py"
if _inf_data_file.exists():
    exec(_inf_data_file.read_text(encoding="utf-8"), _inf_ns)  # noqa: S102
INFERENCEMAX_DATA    = _inf_ns.get("INFERENCEMAX_DATA",    [])
INFERENCE_RUNNERS    = _inf_ns.get("INFERENCE_RUNNERS",    {})
IMAX_SNAPSHOT_TS     = _inf_ns.get("IMAX_SNAPSHOT_TS",     None)
THEROCK_SNAPSHOT_TS  = _inf_ns.get("THEROCK_SNAPSHOT_TS",  None)

# Colour themes for inference sheets (distinct from TheRock palette)
IMAX_PURPLE       = "#4A148C"   # InferenceMAX AMD header
IMAX_PURPLE_LIGHT = "#CE93D8"   # InferenceMAX AMD sub
IMAX_ROW_AMD      = "#F3E5F5"   # InferenceMAX AMD data rows
INF_BROWN         = "#4E342E"   # Inference Runners header
INF_BROWN_LIGHT   = "#BCAAA4"   # Inference Runners sub

hdr_imax  = _f(bold=True, font_color=WHITE, bg_color=IMAX_PURPLE, font_size=10)
hdr_infr  = _f(bold=True, font_color=WHITE, bg_color=INF_BROWN,   font_size=10)
sub_infr  = _f(bold=True, font_color=WHITE, bg_color=INF_BROWN_LIGHT,   font_size=10)

_INF_HEADERS = [
    "Config Name", "Model", "Model Prefix", "GPU Runner", "Precision",
    "Framework", "Multi-Node", "Pinned Docker Image",
]

def _bool_str(v) -> str:
    return "Yes" if v else "No"

def _write_inference_sheet(ws, data: list[tuple], hdr_fmt, row_bg: str, section_label: str):
    """Write a single InferenceMAX/InferenceX benchmark sheet."""
    ws.set_zoom(85)
    ws.freeze_panes(2, 0)
    ws.set_row(0, 30)
    ws.set_row(1, 22)

    col_w = auto_col_w(_INF_HEADERS, [
        [r[0], r[1], r[2], r[3], r[4], r[5],
         _bool_str(r[6]), r[7]]
        for r in data
    ])
    for ci, w in enumerate(col_w):
        ws.set_column(ci, ci, max(w, 12))

    # Row 0: section banner spanning all columns
    ws.merge_range(0, 0, 0, len(_INF_HEADERS)-1, section_label, hdr_fmt)

    # Row 1: column headers
    for ci, h in enumerate(_INF_HEADERS):
        ws.write(1, ci, h, hdr_fmt)

    # Data rows
    row_fmt = _f(bg_color=row_bg)
    bool_yes_fmt = _f(bg_color=YES_GRN, bold=True)
    bool_no_fmt  = _f(bg_color="#F5F5F5")
    data_row = 2
    for rec in data:
        (name, model, model_prefix, runner, precision, framework,
         multinode, docker_image) = rec
        vals = [name, model, model_prefix, runner, precision, framework,
                _bool_str(multinode), docker_image or "—"]
        ws.set_row(data_row, auto_row_h(vals))
        for ci, v in enumerate(vals):
            if ci == 6:  # multinode boolean col
                f = bool_yes_fmt if v == "Yes" else bool_no_fmt
            else:
                f = row_fmt
            ws.write(data_row, ci, v, f)
        data_row += 1

    ws.autofilter(1, 0, max(data_row - 1, 2), len(_INF_HEADERS) - 1)


# ── Snapshot notice rows (written to Sheet 1 when cached data was used) ───────
if THEROCK_SNAPSHOT_TS or IMAX_SNAPSHOT_TS:
    _notice_fmt = fmt(wb, font_name="Arial", font_size=10, bold=True,
                      bg_color="#FFF8E1", font_color="#b26000",
                      border=1, text_wrap=True, valign="vcenter")
    if THEROCK_SNAPSHOT_TS:
        ws1.write(_sc_r + 2, 0,
                  f"⚠ TheRock CI data from cached snapshot ({THEROCK_SNAPSHOT_TS}) "
                  f"— GitHub was unreachable or hit rate limits at report generation time.",
                  _notice_fmt)
        ws1.merge_range(_sc_r + 2, 0, _sc_r + 2, 6, "")  # extend across columns
    if IMAX_SNAPSHOT_TS:
        _imax_notice_row = _sc_r + (3 if THEROCK_SNAPSHOT_TS else 2)
        ws1.write(_imax_notice_row, 0,
                  f"⚠ InferenceMAX data from cached snapshot ({IMAX_SNAPSHOT_TS}) "
                  f"— all live sources were unavailable at report generation time.",
                  _notice_fmt)
        ws1.merge_range(_imax_notice_row, 0, _imax_notice_row, 6, "")

# ── Sheet 6: InferenceMAX — AMD Benchmarks ───────────────────────────────────
ws6 = wb.add_worksheet("InferenceMAX — AMD Benchmarks")
_imax_sheet_title = "InferenceMAX CI — AMD GPU Inference Benchmarks (ROCm/InferenceMAX_rocm)"
if IMAX_SNAPSHOT_TS:
    _imax_sheet_title += f"  ⚠ Cached snapshot from {IMAX_SNAPSHOT_TS} (all live sources were unavailable)"
_write_inference_sheet(
    ws6, INFERENCEMAX_DATA, hdr_imax, IMAX_ROW_AMD,
    _imax_sheet_title,
)

# ── Sheet 7: Inference Runners ────────────────────────────────────────────────
INF_RUN_HEADERS = ["Ecosystem", "GPU Type", "Runner Label",
                   "Node Instances", "Node Count", "Cluster Type"]
ws7 = wb.add_worksheet("Inference Runners")
ws7.set_zoom(85)
ws7.freeze_panes(1, 0)
ws7.set_row(0, 30)

# Collect AMD runner rows — all node labels, no truncation
_inf_run_rows: list[tuple] = []
_amd_runners = INFERENCE_RUNNERS.get("amd") or {}
for _gpu_type, _nodes in sorted(_amd_runners.items()):
    _cluster = "SLURM" if "slurm" in " ".join(_nodes).lower() or "amds" in " ".join(_nodes).lower() else "Docker/Self-hosted"
    _inf_run_rows.append(("AMD", _gpu_type,
                          ", ".join(_nodes),          # all labels, no truncation
                          len(_nodes),                # node count as integer
                          _cluster))

# Updated headers — removed redundant "Node Instances" col, added cleaner layout
INF_RUN_HEADERS = ["Ecosystem", "GPU Type", "Runner Labels (all nodes)", "Node Count", "Cluster Type"]

_inf_run_col_w = [12, 16, 70, 12, 20]
for ci, w in enumerate(_inf_run_col_w):
    ws7.set_column(ci, ci, w)
for ci, h in enumerate(INF_RUN_HEADERS):
    ws7.write(0, ci, h, hdr_infr)
ws7.set_row(0, 26)

_amd_row_fmt  = _f(bg_color=IMAX_ROW_AMD, align="left", font_size=10)
_amd_num_fmt  = _f(bg_color=IMAX_ROW_AMD, align="center", font_size=12, bold=True)
_amd_ctr_fmt  = _f(bg_color=IMAX_ROW_AMD, align="center", font_size=10)
_run_row = 1
for rec in _inf_run_rows:
    eco, gpu_type, labels, count, cluster = rec
    ws7.set_row(_run_row, auto_row_h([labels]))
    ws7.write(_run_row, 0, eco,       _amd_ctr_fmt)
    ws7.write(_run_row, 1, gpu_type,  _amd_ctr_fmt)
    ws7.write(_run_row, 2, labels,    _amd_row_fmt)
    ws7.write(_run_row, 3, count,     _amd_num_fmt)
    ws7.write(_run_row, 4, cluster,   _amd_ctr_fmt)
    _run_row += 1

# Grand total row
_grand_node_total = sum(r[3] for r in _inf_run_rows)
_tot_imax_fmt = _f(bold=True, font_color=WHITE, bg_color=IMAX_PURPLE, font_size=11, align="center")
_tot_imax_sub = _f(bold=False, font_color=WHITE, bg_color=IMAX_PURPLE, font_size=10, align="left")
ws7.merge_range(_run_row, 0, _run_row, 1, "Total AMD Inference Nodes", _tot_imax_fmt)
ws7.write(_run_row, 2,
          "  •  ".join(f"{r[1]}: {r[3]}" for r in _inf_run_rows),
          _tot_imax_sub)
ws7.write(_run_row, 3, _grand_node_total, _tot_imax_fmt)
ws7.write(_run_row, 4, f"{len(_inf_run_rows)} GPU pool types", _tot_imax_fmt)
ws7.set_row(_run_row, 28)
_run_row += 1

ws7.autofilter(0, 0, max(_run_row - 2, 1), len(INF_RUN_HEADERS) - 1)

# ── Sheet 8: InferenceMAX Workflows ──────────────────────────────────────────
# Static data derived from .github/workflows/ in ROCm/InferenceMAX_rocm
IMAX_WF_HEADERS = [
    "Workflow File", "Display Name", "Trigger(s)", "Concurrency",
    "Key Jobs", "Config Keys / Scope", "Calls Template", "Notes",
]

# Tuple schema: (file, name, triggers, concurrency, key_jobs, config_scope, calls_tmpl, notes)
IMAX_WF_DATA = [
    (
        "run-sweep.yml",
        "Run Sweep",
        "workflow_dispatch\npull_request (with 'sweep-enabled' label, non-draft)\n[push to main on perf-changelog.yaml — commented out]",
        "sweep-${{ github.event.pull_request.number || github.sha }}\n(cancel-in-progress: true)",
        "check-newline\nsetup\nsweep-single-node-1k1k\nsweep-single-node-1k8k\nsweep-single-node-8k1k\nsweep-multi-node-1k1k\nsweep-multi-node-1k8k\nsweep-multi-node-8k1k\ncollect-results\ncollect-evals\nupload-changelog-metadata\ncalc-success-rate\ntrigger-ingest",
        "All configs in perf-changelog.yaml that changed between base and head refs (single-node and multi-node variants by ISL×OSL: 1k1k, 1k8k, 8k1k)",
        "benchmark-tmpl.yml (single-node)\nbenchmark-multinode-tmpl.yml (multi-node)\ncollect-results.yml\ncollect-evals.yml",
        "Main benchmark orchestrator. On push to main, triggers database ingest via SemiAnalysisAI/inferencemax-app dispatch event.",
    ),
    (
        "atom-docker-ci.yml",
        "Atom Docker CI",
        "workflow_dispatch",
        "—",
        "atom-ci (delegates to e2e-tests.yml)",
        "amd-master.yaml — config-keys: '*-atom-*docker-ci'",
        "e2e-tests.yml",
        "Runs all ATOM Docker-based CI configs from amd-master.yaml. Single job that calls e2e-tests with a wildcard key filter.",
    ),
    (
        "atom-slurm-ci.yml",
        "Atom Slurm CI",
        "workflow_dispatch",
        "—",
        "atom-ci (delegates to e2e-tests.yml)",
        "amd-master.yaml — config-keys: '*-atom-*slurm-ci'",
        "e2e-tests.yml",
        "Runs all ATOM SLURM-based CI configs from amd-master.yaml. Uses SLURM job scheduler on AMD GPU cluster.",
    ),
    (
        "e2e-tests.yml",
        "End-to-End Tests",
        "workflow_dispatch (interactive — choose config key from dropdown)\nworkflow_call (called by atom-docker-ci, atom-slurm-ci, pr-comment-sweep)",
        "—",
        "get-jobs\ntest-sweep-single-node\ntest-sweep-multi-node\ncollect-results\ncollect-evals\ncalc-success-rate",
        "amd-master.yaml — config key(s) passed via 'generate-cli-command' input\nrunners.yaml — runner config passed via same input\nDropdown options include specific named configs (e.g. glm5-fp8-mi355x-atom, kimik2.5-fp4-mi355x-vllm) and wildcard '*-atom*'",
        "benchmark-tmpl.yml (single-node)\nbenchmark-multinode-tmpl.yml (multi-node)\ncollect-results.yml\ncollect-evals.yml",
        "Core reusable E2E test runner. Accepts generate-cli-command string; matrix_logic/generate_sweep_configs.py splits output into single-node vs. multi-node jobs. Called by atom-docker-ci, atom-slurm-ci, and pr-comment-sweep.",
    ),
    (
        "pr-comment-sweep.yml",
        "Slash Command Sweep",
        "issue_comment (types: created)\nOnly fires when: comment is on a PR AND comment starts with '/sweep'",
        "sweep-PR#<number> at job level (cancel-in-progress: true)",
        "get-jobs\napproval (required for outside collaborators — environment gate)\nvalidate (calls e2e-tests.yml)",
        "Arguments passed inline in PR comment after /sweep command\n(e.g. /sweep test-config --config-keys glm5-fp8-mi355x-atom)",
        "e2e-tests.yml (via validate job)",
        "Allows PR authors to trigger benchmark sweeps via /sweep comment. Outside collaborators require approval via 'Outside Collaborator E2E Test' environment. Pins to immutable commit SHA to prevent TOCTOU attacks.",
    ),
    (
        "profile.yml",
        "Profile",
        "workflow_dispatch\nInputs: config-key, config-file, conc, moe-debug, ref",
        "—",
        "get-jobs\nprofile",
        "Default: nvidia-master.yaml (configurable via config-file input)\nSelects one config by exact key + concurrency value",
        "benchmark-tmpl.yml (single-node only; takes first matching job)",
        "Profiling run using nsys/rocprof. Uploads Perfetto trace to SemiAnalysisAI/InferenceX-trace-storage and prints relay URL for visualization. Supports both Docker (sglang/vllm) and SLURM runners. Optionally captures MoE debug logs.",
    ),
    (
        "docker-tag-monitor.yml",
        "Docker Tag Monitor",
        "schedule: cron '0 8 * * 6' (weekly, Saturdays 08:00 UTC)\nworkflow_dispatch (with dry_run option)",
        "—",
        "check-releases",
        "Reads amd-master.yaml and nvidia-master.yaml to compare current image tags vs. latest on Docker Hub",
        "Uses claude-code-action (Anthropic) to check Docker Hub API and create GitHub issues",
        "AI-powered monitoring: checks lmsysorg/sglang and vllm/vllm-openai-rocm for new ROCm tags. Creates a GitHub issue with update table and @claude mention to update configs automatically when newer tags are found.",
    ),
    (
        "benchmark-tmpl.yml",
        "Benchmark Template (single-node)",
        "workflow_call only (internal — called by run-sweep and e2e-tests)",
        "—",
        "Single benchmark job on GPU runner",
        "Receives all parameters from parent workflow (model, runner, isl, osl, tp, ep, framework, precision, conc, spec-decoding, disagg)",
        "—",
        "Reusable template for a single-node inference benchmark. Handles Docker + SLURM resource cleanup, runs benchmark script, uploads result JSON as artifact.",
    ),
    (
        "benchmark-multinode-tmpl.yml",
        "Benchmark Template (multi-node)",
        "workflow_call only (internal — called by run-sweep and e2e-tests)",
        "—",
        "Single multi-node benchmark job",
        "Receives all parameters including disaggregated prefill/decode worker config (prefill-num-worker, prefill-tp, decode-num-worker, decode-tp, etc.)",
        "—",
        "Reusable template for multi-node / disaggregated prefill+decode benchmarks (e.g. sglang-disagg). Passes prefill and decode worker configs separately.",
    ),
    (
        "collect-results.yml",
        "Collect Results",
        "workflow_call only (internal — called after sweep jobs complete)",
        "—",
        "Download + aggregate result artifacts",
        "All result_* artifacts from the sweep run",
        "—",
        "Downloads all benchmark result JSON artifacts, aggregates them, and uploads a single combined artifact. Used by run-sweep.yml and e2e-tests.yml.",
    ),
    (
        "collect-evals.yml",
        "Collect Evals",
        "workflow_call only (internal)",
        "—",
        "Download + aggregate eval artifacts",
        "All eval_* artifacts from the sweep run",
        "—",
        "Downloads evaluation artifacts (accuracy/quality metrics) produced during benchmark runs and consolidates them.",
    ),
]

IMAX_WF_COL_W = auto_col_w(IMAX_WF_HEADERS, [list(r) for r in IMAX_WF_DATA])
# Minimum widths per column for readability
_WF_MIN_W = [22, 22, 36, 28, 32, 40, 30, 44]

ws8 = wb.add_worksheet("InferenceMAX Workflows")
ws8.set_zoom(80)
ws8.freeze_panes(2, 0)
ws8.set_row(0, 30)
ws8.set_row(1, 22)

for ci, (w, mn) in enumerate(zip(IMAX_WF_COL_W, _WF_MIN_W)):
    ws8.set_column(ci, ci, max(w, mn))

# Row 0: banner
ws8.merge_range(0, 0, 0, len(IMAX_WF_HEADERS) - 1,
                "InferenceMAX CI Workflows — ROCm/InferenceMAX_rocm (.github/workflows/)",
                hdr_imax)

# Row 1: column headers
for ci, h in enumerate(IMAX_WF_HEADERS):
    ws8.write(1, ci, h, hdr_imax)

# Colour alternation: core orchestrators vs. reusable/internal templates
_wf_core_bg   = "#F3E5F5"   # purple-tint for user-facing workflows
_wf_tmpl_bg   = "#FAF5FF"   # lighter for internal reusable templates
_wf_tmpl_keys = {"benchmark-tmpl.yml", "benchmark-multinode-tmpl.yml",
                 "collect-results.yml", "collect-evals.yml"}
_wf_core_fmt  = _f(bg_color=_wf_core_bg)
_wf_tmpl_fmt  = _f(bg_color=_wf_tmpl_bg)

_wf_trigger_fmt = _f(bg_color="#EDE7F6", font_size=10)   # trigger col highlight
_wf_file_fmt    = _f(bg_color=_wf_core_bg, bold=True, font_size=10)
_wf_file_tmpl_fmt = _f(bg_color=_wf_tmpl_bg, bold=True, font_size=10)

_wf_row = 2
for rec in IMAX_WF_DATA:
    is_tmpl = rec[0] in _wf_tmpl_keys
    base_fmt = _wf_tmpl_fmt if is_tmpl else _wf_core_fmt
    file_fmt = _wf_file_tmpl_fmt if is_tmpl else _wf_file_fmt
    row_h = auto_row_h(list(rec))
    ws8.set_row(_wf_row, max(row_h, 20))
    for ci, v in enumerate(rec):
        if ci == 0:
            ws8.write(_wf_row, ci, v, file_fmt)
        elif ci == 2:   # Trigger column
            ws8.write(_wf_row, ci, v, _wf_trigger_fmt)
        else:
            ws8.write(_wf_row, ci, v, base_fmt)
    _wf_row += 1

ws8.autofilter(1, 0, max(_wf_row - 1, 2), len(IMAX_WF_HEADERS) - 1)

# ── Sheet 9: Data Sources ─────────────────────────────────────────────────────
ws9 = wb.add_worksheet("Data Sources")
ws9.set_zoom(90)
ws9.freeze_panes(2, 0)
_DS_HDR_GREY = "#78909C"   # medium blue-grey for Data Sources headers
ws9.set_tab_color(_DS_HDR_GREY)

_DS_BLUE   = "#1565C0"
_DS_GREEN  = "#2E7D32"
_DS_ORANGE = "#E65100"
_DS_PURPLE = "#4A148C"

_src_hdr_fmt  = _f(bold=True, font_color=WHITE, bg_color=_DS_HDR_GREY, font_size=11)
_src_title_fmt = lambda color: _f(bold=True, font_color=WHITE, bg_color=color, font_size=10)
_src_key_fmt  = _f(bold=True, bg_color="#F5F5F5", font_size=10)
_src_val_fmt  = _f(bg_color="#FFFFFF", font_size=10)
_src_note_fmt = _f(italic=True, font_color="#555555", bg_color="#FAFAFA", font_size=10)

ws9.set_column(0, 0, 28)   # Source / File
ws9.set_column(1, 1, 55)   # What it populates
ws9.set_column(2, 2, 40)   # GitHub URL

ws9.set_row(0, 28)
ws9.set_row(1, 18)
ws9.merge_range(0, 0, 0, 2,
    "How Data Is Fetched — fetch_rocm_data.py pulls from 4 GitHub repos "
    "(auth: 5 000 req/hr with GITHUB_TOKEN; unauth: 60 req/hr with local-clone fallback)",
    _src_hdr_fmt)

for ci, h in enumerate(["File / Endpoint", "What It Populates", "GitHub Link"]):
    ws9.write(1, ci, h, _src_hdr_fmt)

_DS_ROWS = [
    # (source_label, color, file, description, url)
    ("Source 1 — ROCm/TheRock", _DS_BLUE,
     "amdgpu_family_matrix.py",
     "Runner labels per GPU family, GPU ISA strings (gfx94X, gfx950, …), nightly-only flags",
     "https://github.com/ROCm/TheRock/blob/main/amdgpu_family_matrix.py"),
    ("", _DS_BLUE,
     "BUILD_TOPOLOGY.toml",
     "Component → super-repo mapping (rocm-libraries / rocm-systems / TheRock)",
     "https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml"),
    ("", _DS_BLUE,
     ".gitmodules",
     "Direct submodule list — identifies components tested inside TheRock itself",
     "https://github.com/ROCm/TheRock/blob/main/.gitmodules"),
    ("", _DS_BLUE,
     "ci_nightly.yml",
     "Nightly schedule time, GPU family test matrix for the nightly tier",
     "https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml"),
    ("", _DS_BLUE,
     "ci.yml",
     "Pre-commit tier — PR trigger, quick builds across core GPU families",
     "https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml"),
    ("", _DS_BLUE,
     "ci_postsubmit.yml",
     "Post-commit tier — triggered by submodule bump merges",
     "https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_postsubmit.yml"),
    ("", _DS_BLUE,
     "ci_asan.yml",
     "ASAN sanitizer builds",
     "https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_asan.yml"),
    ("", _DS_BLUE,
     "multi_arch_release.yml",
     "Release pipeline (workflow_dispatch)",
     "https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_release.yml"),
    ("Source 2 — ROCm/rocm-libraries", _DS_GREEN,
     "projects/ (directory listing)",
     "Discovers all library component names (rocBLAS, hipBLAS, MIOpen, rocFFT, …). Every subdirectory is treated as an active CI component.",
     "https://api.github.com/repos/ROCm/rocm-libraries/contents/projects"),
    ("Source 3 — ROCm/rocm-systems", _DS_ORANGE,
     "projects/ (directory listing)",
     "Discovers all system component names (RCCL, rocminfo, ROCm-SMI, …).",
     "https://api.github.com/repos/ROCm/rocm-systems/contents/projects"),
    ("Source 4 — ROCm/InferenceMAX_rocm", _DS_PURPLE,
     "amd-master.yaml",
     "All 34 AMD benchmark configs — model, GPU runner, precision, framework, pinned Docker image",
     "https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml"),
    ("", _DS_PURPLE,
     "runners.yaml",
     "AMD GPU runner pool definitions — maps mi300x/mi325x/mi355x to physical node labels",
     "https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml"),
    ("", _DS_PURPLE,
     "Data source priority",
     "(1) GitHub API when GITHUB_TOKEN set  →  (2) Local clone at InferenceMAX_rocm/  →  (3) Graceful skip with WARN",
     ""),
]

_ds_row = 2
_last_source = ""
for src_label, color, fname, desc, url in _DS_ROWS:
    ws9.set_row(_ds_row, auto_row_h([desc]))
    title_fmt = _src_title_fmt(color)
    label = src_label if src_label else _last_source
    if src_label:
        _last_source = src_label
    ws9.write(_ds_row, 0, fname, _src_key_fmt)
    ws9.write(_ds_row, 1, desc, _src_val_fmt)
    if url:
        ws9.write_url(_ds_row, 2, url, _src_val_fmt, url)
    else:
        ws9.write(_ds_row, 2, "—", _src_note_fmt)
    # Color the row left border by source group via set_row won't work, so we
    # write the source label in col 0 with color when it changes
    if src_label:
        ws9.write(_ds_row, 0, fname, _f(bold=True, bg_color=color + "22", font_size=10,
                                        font_color="#000000"))
        ws9.write(_ds_row, 1, desc, _f(bg_color=color + "11", font_size=10))
    _ds_row += 1

# Pipeline note row
ws9.set_row(_ds_row, 30)
ws9.merge_range(_ds_row, 0, _ds_row, 2,
    "Fetch pipeline:  GitHub APIs / Local clones  →  fetch_rocm_data.py  →  "
    "rocm_ci_data.py (intermediate snapshot)  →  generate_rocm_html.py + generate_rocm_cicd.py  →  "
    "ROCm_CICD_Comprehensive.html  +  ROCm_CICD_Comprehensive.xlsx",
    _src_note_fmt)

wb.close()

# ── Inject AMD "Internal Only" MIP sensitivity label ─────────────────────────
# Label XML extracted from an existing AMD-labelled workbook.
import zipfile as _zf, shutil as _sh, tempfile as _tmp, os as _os

_LABEL_XML = (
    '<?xml version="1.0" encoding="utf-8" standalone="yes"?>'
    '<clbl:labelList xmlns:clbl="http://schemas.microsoft.com/office/2020/mipLabelMetadata">'
    '<clbl:label id="{dce362fe-1558-4fb5-9f64-8a6240d76441}" enabled="1" method="Privileged" '
    'siteId="{3dd8961f-e488-4e60-8e11-a82d994e183d}" removed="0" /></clbl:labelList>'
)
_CONTENT_TYPE = (
    '<Override PartName="/docMetadata/LabelInfo.xml" '
    'ContentType="application/vnd.ms-office.classificationlabels+xml"/>'
)

_tmp_path = OUT + ".tmp"
with _zf.ZipFile(OUT, "r") as _zin, _zf.ZipFile(_tmp_path, "w", _zf.ZIP_DEFLATED) as _zout:
    for _item in _zin.infolist():
        _data = _zin.read(_item.filename)
        if _item.filename == "[Content_Types].xml":
            _text = _data.decode("utf-8")
            if "LabelInfo.xml" not in _text:
                _text = _text.replace("</Types>", _CONTENT_TYPE + "</Types>")
            _data = _text.encode("utf-8")
        _zout.writestr(_item, _data)
    if "docMetadata/LabelInfo.xml" not in _zin.namelist():
        _zout.writestr("docMetadata/LabelInfo.xml", _LABEL_XML)
_os.replace(_tmp_path, OUT)

total = len(COMPONENTS)
non_fw = sum(1 for r in COMPONENTS if r[0] != "Frameworks")
fw_rows = total - non_fw
ci_en = sum(1 for r in COMPONENTS if r[0] != "Frameworks" and r[4] in ("Yes","Partial"))
print(f"Excel written: {OUT}")
print(f"Components: {total} total ({non_fw} non-framework, {fw_rows} framework slots)")
print(f"CI-Enabled (non-FW): {ci_en}")
n_inf_sheets = (2 if INFERENCEMAX_DATA else 0) + 1  # +1 for Workflows sheet (always present)
print(f"Runners: {len(RUNNER_DATA)}  |  Framework rows: {len(FW_DATA)}  |  Sheets: {5 + n_inf_sheets}")
if INFERENCEMAX_DATA:
    print(f"InferenceMAX AMD configs: {len(INFERENCEMAX_DATA)}")
