# -*- coding: utf-8 -*-
"""Generate ROCm CI/CD HTML report — tier-grouped column layout"""
import sys, os, datetime, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

try:
    from zoneinfo import ZoneInfo
    _PT = ZoneInfo("America/Los_Angeles")
except ImportError:
    # Python < 3.9 fallback: use fixed UTC-7 (PDT)
    _PT = datetime.timezone(datetime.timedelta(hours=-7))

_now_pt   = datetime.datetime.now(_PT)
_tz_label = _now_pt.strftime("%Z")          # "PDT" or "PST"
_TIMESTAMP = _now_pt.strftime(f"%B %d, %Y %I:%M %p {_tz_label}")

def _utc_to_pt(utc_hour: int, utc_min: int = 0) -> str:
    """Convert a fixed UTC cron time to a California PT display string.
    Returns e.g. '6:00 PM PDT / 5:00 PM PST' so readers see both DST states."""
    import datetime as _dt
    try:
        from zoneinfo import ZoneInfo as _ZI
        _pt_tz = _ZI("America/Los_Angeles")
    except ImportError:
        _pt_tz = _dt.timezone(_dt.timedelta(hours=-7))
    # Use a fixed reference date in summer (PDT) and winter (PST)
    _pdt = _dt.datetime(2025, 7, 1, utc_hour, utc_min, tzinfo=_dt.timezone.utc).astimezone(_pt_tz)
    _pst = _dt.datetime(2025, 1, 1, utc_hour, utc_min, tzinfo=_dt.timezone.utc).astimezone(_pt_tz)
    def _fmt(t: "_dt.datetime") -> str:
        return t.strftime("%I:%M %p").lstrip("0")
    return f"{_fmt(_pdt)} PDT / {_fmt(_pst)} PST"

_HERE = Path(__file__).parent
OUT = str(_HERE / "ROCm_CICD_Comprehensive.html")

# ─── GPU family shorthands ────────────────────────────────────────────────────
# Pre-commit Linux: only gfx94X gets GPU tests; gfx110X/gfx1151/gfx120X = build only (nightly_check_only_for_family)
PC_L_TEST  = "gfx94X (Build + Test)\ngfx110X, gfx1151, gfx120X — Build-only (nightly_check_only)"
PC_L_94    = "gfx94X (Build + Test)"                    # components that only have Linux-gfx94X CI
PC_L_NONE  = "—"

# Pre-commit Windows: gfx1151 = Build-only (nightly_check_only_for_family on Windows side too)
PC_W_BUILD = "gfx1151 (Build-only)"
PC_W_NONE  = "—"

# Post-commit Linux: gfx94X (Build + Test) + gfx950 (Build + Test) — exact two families
PO_L_FULL  = "gfx94X, gfx950 (Both Build + Test)"
PO_L_NONE  = "—"

# Post-commit Windows: gfx1151 (Build-only per nightly_check_only)
PO_W_BUILD = "gfx1151 (Build-only)"
PO_W_NONE  = "—"

# Nightly Linux families (full list with Build + Test, plus Build-only)
NL_FULL = ("gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X\n"
           "(Build-only: gfx900, gfx906, gfx908, gfx101X)")
# JAX nightly Linux: only gfx94X is GPU-tested; all others are build-only
NL_JAX = ("gfx94X — Build + Test\n"
           "gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X — Build-only (no GPU test)\n"
           "(Build-only, no HW runners: gfx900, gfx906, gfx908, gfx101X)")
NL_NO115X = ("gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx120X\n"
             "(excl. gfx115X — no support; Build-only: gfx900, gfx906, gfx908, gfx101X)")
NL_94_950 = "gfx94X, gfx950"

# Nightly Windows families (all Build + Test)
NW_FULL  = "gfx1151, gfx110X, gfx103X, gfx120X"
NW_NONE  = "—"

# Pre-commit Linux runner (gfx94X Build + Test)
# alt = alternate runner pool (same MI300X/MI325X fleet, different CCS host)
# 35% = weighted random selection — 65% primary / 35% alternate per-job
PCR_L = "linux-gfx942-1gpu-ossci-rocm\n(alternate pool: linux-gfx942-1gpu-ccs-ossci-rocm)"
PCR_L_NONE = "—"

# Post-commit Linux runners
POR_L = "linux-gfx942-1gpu-ossci-rocm (gfx94X)\nlinux-gfx950-1gpu-ccs-ossci-rocm (gfx950)"
POR_L_NONE = "—"

# Pre/Post-commit Windows runner
PCR_W = "windows-gfx1151-gpu-rocm (Build-only)"
POR_W = "windows-gfx1151-gpu-rocm (Build-only)"

# Nightly Linux runners — gfx94X + gfx950 only (for components that exclude gfx115X and only support those two families)
NLR_94_950 = ("linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
              "linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)")

# Nightly Linux runners (full set)
NLR_FULL = ("linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
            "linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)\n"
            "linux-gfx90a-gpu-rocm (gfx90a)\n"
            "linux-gfx1030-gpu-rocm (gfx103X)\n"
            "linux-gfx110X-gpu-rocm (gfx110X)\n"
            "linux-gfx1150-gpu-rocm (gfx1150)\n"
            "linux-gfx1151-gpu-rocm (gfx1151)\n"
            "linux-gfx1153-gpu-rocm (gfx1153)\n"
            "linux-gfx120X-gpu-rocm (gfx120X)")
NWR_FULL = ("windows-gfx1151-gpu-rocm (gfx1151)\n"
            "windows-gfx110X-gpu-rocm (gfx110X)\n"
            "windows-gfx1030-gpu-rocm (gfx103X)\n"
            "windows-gfx120X-gpu-rocm (gfx120X)")

# ─── Component data ───────────────────────────────────────────────────────────
# Tuple fields (23):
#   cat, sub, comp, repo, ci_en,
#   pc_lgfx, pc_lr, pc_wgfx, pc_wr, pc_tt,       ← Pre-commit
#   po_lgfx, po_lr, po_wgfx, po_wr, po_tt,       ← Post-commit
#   ni_lgfx, ni_lr, ni_wgfx, ni_wr, ni_tt,       ← Nightly
#   plat, notes
COMPONENTS = [
    # ── Math ──────────────────────────────────────────────────────────────────
    ("Libraries","Math","rocBLAS","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only",
     "6 shards; smoke YAML only at pre-commit (full suite via 6-shard nightly)"),

    ("Libraries","Math","hipBLAS","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "1 Linux shard, 1 Windows shard; expand tracked #2616"),

    ("Libraries","Math","hipblas-common","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "Shared headers/utilities for hipBLAS family (hipBLAS, hipBLASLt, hipSPARSELt); new project added to rocm-libraries upstream"),

    ("Libraries","Math","hipBLASLt","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "6 Linux shards / 1 Windows shard"),

    ("Libraries","Math","rocFFT","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", ""),

    ("Libraries","Math","hipFFT","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "2 Linux / 2 Windows shards"),

    ("Libraries","Math","rocRAND","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", ""),

    ("Libraries","Math","hipRAND","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", ""),

    ("Libraries","Math","rocSOLVER","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Windows tracking #1770"),

    ("Libraries","Math","hipSOLVER","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", ""),

    ("Libraries","Math","rocSPARSE","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", ""),

    ("Libraries","Math","hipSPARSE","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", ""),

    ("Libraries","Math","hipSPARSELt","rocm-libraries","Yes",
     "gfx94X (excl. gfx115X)", PCR_L, PC_W_NONE, "—", "standard",
     "gfx94X, gfx950 (excl. gfx115X)", POR_L, PO_W_NONE, "—", "quick",
     "gfx94X, gfx950 (excl. gfx115X)", NLR_94_950, NW_NONE, "—", "comprehensive",
     "Linux only", "gfx115X excluded — no support planned; 6 Linux shards"),

    ("Libraries","Math","rocWMMA","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "4 Linux / 2 Windows shards"),

    ("Libraries","Math","Tensile","rocm-libraries","Partial",
     "gfx94X (via rocBLAS group)", PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "No standalone test — bundled with rocBLAS CTest"),

    ("Libraries","Math","origami","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "Part of BLAS group; 1 Linux shard + 1 Windows shard; 5 min timeout"),

    ("Libraries","Math","rocRoller","rocm-libraries","Yes",
     "gfx94X (excl. gfx115X)", PCR_L, PC_W_NONE, "—", "standard",
     "gfx94X, gfx950 (excl. gfx115X)", POR_L, PO_W_NONE, "—", "quick",
     "gfx94X, gfx950 (excl. gfx115X)", NLR_94_950, NW_NONE, "—", "comprehensive",
     "Linux only", "gfx115X excluded (no support); 5 Linux shards; Windows not planned"),

    ("Libraries","Math","hipTensor","rocm-libraries","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Both", "Not in subtree_to_project_map — NO CI"),

    ("Libraries","Math","Half","TheRock","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Direct TheRock submodule; header-only library, no test"),

    ("Libraries","Math","rocALUTION","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    # ── Communication ──────────────────────────────────────────────────────────
    ("Libraries","Communication","RCCL","rocm-systems","Yes",
     "—","—","—","—","—",
     "—","—","—","—","—",
     "gfx94X-dcgpu (multi-node, 8-GPU)\ngfx950-dcgpu (single-node)", "Build: azure-linux-scale-rocm\nSingle-node test: linux-gfx942-1gpu-ossci-rocm\nMulti-node test: nova-linux-slurm-scale-runner", NW_NONE, "—", "comprehensive",
     "Linux only",
     "Nightly only at TheRock level; also triggers at PR/post-commit when RCCL paths change (rocm-systems therock-rccl-ci-linux.yml); both gfx94X-dcgpu (multi-node) and gfx950-dcgpu (single-node) tested; single generic artifact (not per-GPU-family); requires 8-GPU runner + Slurm for multi-node"),

    ("Libraries","Communication","rocSHMEM","rocm-systems","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only", "Test infra exists in CMakeLists.txt (functional + unit tests, require MPI) but no CI tests triggered in TheRock workflows; build-only in practice"),

    ("Libraries","Communication","kpack","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "Own CI (kpack-ci.yml); Ubuntu + Windows; Python pytest + CMake C++ tests; matrix: Ubuntu/Windows × Python 3.10/3.12"),

    # ── Primitives ─────────────────────────────────────────────────────────────
    ("Libraries","Primitives","rocPRIM","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "2 Linux / 2 Windows shards"),

    ("Libraries","Primitives","hipCUB","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "1 Linux / 1 Windows shard"),

    ("Libraries","Primitives","rocThrust","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "1 Linux / 1 Windows shard"),

    # ── ML & CV ────────────────────────────────────────────────────────────────
    ("Libraries","ML & CV","MIOpen","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "4 Linux / 4 Windows shards; nightly adds miopendriver_conv functional test (30 min)"),

    ("Libraries","ML & CV","Composable Kernels","rocm-libraries","Partial",
     "gfx94X (via MIOpen group)", PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only",
     "No standalone test; bundled with MIOpen CTest; RDNA3 (gfx110X) NOT supported by CK"),

    ("Libraries","ML & CV","MIGraphX","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    ("Libraries","ML & CV","MIVisionX","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    ("Libraries","ML & CV","RPP","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    # ── Media ──────────────────────────────────────────────────────────────────
    ("Libraries","Media","rocDecode","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Requires media container (FFmpeg dev libs); 1 shard"),

    ("Libraries","Media","rocJPEG","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "1 shard"),

    ("Libraries","Media","rocPyDecode","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    # ── DNN Providers ──────────────────────────────────────────────────────────
    ("Libraries","DNN Providers","hipBLASLt Provider","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "1 Linux / 1 Windows shard"),

    ("Libraries","DNN Providers","MIOpen Provider","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "1 Linux / 1 Windows shard"),

    ("Libraries","DNN Providers","Fusilli Provider","TheRock (iree-org/fusilli)","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "IREE-based DNN provider; submodule pinned from iree-org/fusilli. Pre-commit/post-commit CI tests TheRock's integration layer (build system + plugin registration) against the pinned Fusilli version — not Fusilli upstream code. Fusilli's own code changes are CI-tested in iree-org/fusilli independently. 1 shard"),

    ("Libraries","DNN Providers","hipDNN","rocm-libraries","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both", "3 test jobs: hipdnn + hipdnn_install + hipdnn_samples"),

    ("Libraries","DNN Providers","hip-kernel-provider","rocm-libraries","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Exists in rocm-libraries but DISABLED in CI test matrix (commented out pending rocm-libraries bump); no active CI"),

    # ── System Management ──────────────────────────────────────────────────────
    ("Tools","System Mgmt","AMD SMI","rocm-systems","Yes",
     "Self-hosted (own CI)", "self-hosted (GPU-enabled)", "—", "—", "build + test + ABI check",
     "Self-hosted (own CI)", "self-hosted (GPU-enabled)", "—", "—", "build + test + ABI check",
     "Self-hosted (own CI)", "self-hosted (GPU-enabled)", "—", "—", "build + test + ABI check",
     "Linux only", "Own CI: amdsmi-build.yml + abi-compliance-check.yml; GPU tests enabled (requires /dev/kfd + /dev/dri); multi-OS: Ubuntu 20/22, Debian 10, RHEL 8/9/10, AzureLinux 3, AlmaLinux 8, SLES; CLI + C++ unit + Python tests"),

    ("Tools","System Mgmt","ROCm SMI Lib","rocm-systems","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only", "Own CI: formatting/linting only (lstt-formatting.yml); no build or GPU test CI in TheRock pipeline; amdsmi is active successor"),

    ("Tools","System Mgmt","rocminfo","rocm-systems","Partial",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Part of 'core' CI group; test_sanity.py; 1 shard / 5 min"),

    ("Tools","System Mgmt","ROCm Data Center Tool","rocm-systems","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only", "dc_tools group exists but no CI tests wired in any stage; testing TBD"),

    ("Tools","System Mgmt","ROCm Validation Suite","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    # ── Performance ────────────────────────────────────────────────────────────
    ("Tools","Performance","ROCprofiler-SDK","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only",
     "Own CI (rocprofiler-sdk-continuous_integration.yml); runners: linux-gfx942-1gpu-ossci-rocm (primary) + linux-mi325-8gpu-ossci-rocm-sandbox (sanitizers); multi-OS: Ubuntu 22.04, RHEL 8.8, RHEL 9.5, SLES 15.6; requires SYS_PTRACE cap; sanitizers (ASan/TSan/LSan/UBSan); TheRock also adds full GPU matrix at post-commit and nightly"),

    ("Tools","Performance","ROCm Compute Profiler","rocm-systems","Yes",
     "gfx950 (MI355), gfx94X (MI325), gfx1151 (Strix Halo) — own CI", "linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)\nlinux-gfx942-1gpu-ossci-rocm (gfx94X)\nlinux-strix-halo-gpu-rocm (gfx1151)", "—", "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Own CI (rocprofiler-compute-continuous-integration.yml); ci-matrix.yml: gfx950/gfx94X/gfx1151 × Ubuntu 22.04/24.04 (nightly); gfx950+gfx1151 × Ubuntu 22.04 (CI); ROCm 7.0.0; TheRock adds full GPU matrix at post-commit and nightly; 2 shards"),

    ("Tools","Performance","ROCm System Profiler","rocm-systems","Yes",
     "gfx950 (MI355), gfx94X (MI325) — own CI", "linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)\nlinux-gfx942-1gpu-ossci-rocm (gfx94X)", "—", "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Own CI (rocprofiler-systems-continuous-integration.yml); ci-matrix.yml: gfx950+gfx94X × Ubuntu 22.04/24.04 (nightly); gfx950 × Ubuntu 24.04 (CI); ROCm 7.2.0; multi-OS distro matrix (Ubuntu 22.04/24.04, Debian 12, RHEL 8.10/9.x); ROCm versions 6.3–7.2 tested; TheRock adds full GPU matrix at post-commit and nightly"),

    ("Tools","Performance","aqlprofile","rocm-systems","Yes",
     "gfx120X (Navi4), gfx110X (Navi3), gfx94X (MI325X) — own CI", "rocprofiler-navi4-dind (gfx120X)\nrocprofiler-navi3-dind (gfx110X)\nlinux-gfx942-1gpu-ossci-rocm (gfx94X)", "—", "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Own CI (aqlprofile-continuous_integration.yml): Navi4 → rocprofiler-navi4-dind; Navi3 → rocprofiler-navi3-dind; MI325X → linux-gfx942-1gpu-ossci-rocm; DEB tested on Ubuntu 22.04; RPM on RHEL 8.8/9.5 + SLES 15.6; 1 shard / 5 min"),

    ("Tools","Performance","ROCProfiler (v2)","rocm-systems","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only", "No active CI workflow found in any repo; official ROCm docs list as v2.0.0 (current supported HIP profiler); being superseded by rocprofiler-sdk"),

    ("Tools","Performance","ROCTracer","rocm-systems","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only", "No active CI workflow found in any repo; official ROCm docs list as v4.1.0; being superseded by rocprofiler-sdk"),

    ("Tools","Performance","rocprofiler-register","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Own CI (rocprofiler-register-continuous-integration.yml); runner: linux-mi325-1gpu-ossci-rocm; standalone run-ci.py test suite; clang-13/14/15 + gcc-11/12; TSan/ASan/LSan tested; CPack + modulefiles validation"),

    ("Tools","Performance","ROCm Bandwidth Test","—","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Not in TheRock CI"),

    # ── Development ────────────────────────────────────────────────────────────
    ("Tools","Development","ROCgdb","TheRock","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only",
     "Direct TheRock submodule (debug-tools/rocgdb/source); requires SYS_PTRACE + no_rocm_image_ubuntu24_04_rocgdb container; 1 shard / 45 min"),

    ("Tools","Development","ROCdbgapi","rocm-systems","Partial",
     "gfx94X (debug_tools group)", PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "No standalone test binary; bundled in debug_tools group"),

    ("Tools","Development","ROCr Debug Agent","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_NONE, "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "1 shard / 10 min"),

    ("Tools","Development","HIPIFY","TheRock","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Direct TheRock submodule; no standalone CI test (tested via clang)"),

    ("Tools","Development","ROCm CMake","TheRock","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "—", "Direct TheRock submodule; CMake packaging helpers; no standalone CI test"),

    # ── Compilers ──────────────────────────────────────────────────────────────
    ("Compilers","—","LLVM / amdclang / amdflang","TheRock","Yes",
     PC_L_TEST, "azure-linux-scale-rocm (build)\nlinux-gfx942-1gpu-ossci-rocm (test: gfx94X)",
     PC_W_BUILD, "azure-windows-scale-rocm (Build-only)", "Build-only",
     "gfx94X, gfx950 + all presubmit (Build-only)", "azure-linux-scale-rocm",
     "gfx1151 + all (Build-only)", "azure-windows-scale-rocm", "Build-only",
     NL_FULL, "azure-linux-scale-rocm (build)\n" + NLR_FULL,
     NW_FULL, "azure-windows-scale-rocm (build)\n" + NWR_FULL, "Build-only",
     "Both",
     "Foundation stage; no standalone test — all downstream tests implicitly verify it"),

    ("Compilers","—","SPIRV-LLVM-Translator","TheRock","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only",
     "Direct TheRock submodule (compiler/spirv-llvm-translator); built inside LLVM stage; no standalone CI test"),

    ("Compilers","—","hipCC","TheRock","Partial",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "4 Linux / 4 Windows shards; Windows runs twice: PAL (pass/fail) + ROCR (informational)"),

    # ── Runtime ────────────────────────────────────────────────────────────────
    ("Runtime","—","HIP Runtime (CLR)","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "4 Linux shards (hip-tests); 4 Windows shards (PAL+ROCR); WSL2 CI via rocr-runtime-wsl.yml"),

    ("Runtime","—","ROCr Runtime (HSA)","rocm-systems","Yes",
     PC_L_94, PCR_L, "WSL2 Build-only", "rocr-runtime-libhsakmt-wsl", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux (WSL2 build)", "TheRock CI: test_rocrtst.py via therock-test-component (1 shard / 15 min); rocm-systems own CI: libhsakmt WSL build only (rocr-runtime-wsl.yml); std::filesystem banned in rocr-runtime code (ABI constraint)"),

    ("Runtime","—","libhipCXX","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "Tested as part of HIP/CLR CI (no standalone workflow); libhipcxx_hipcc: Linux + Windows (1 shard each, 30 min); libhipcxx_hiprtc: Linux only (1 shard, 20 min); hiprtc Linux only"),

    ("Runtime","—","ROCm Core","rocm-systems","Yes",
     PC_L_94, PCR_L, PC_W_BUILD, PCR_W, "standard",
     PO_L_FULL, POR_L, PO_W_BUILD, POR_W, "quick",
     NL_FULL, NLR_FULL, NW_FULL, NWR_FULL, "comprehensive",
     "Both",
     "Provides ROCm version metadata + install path API (getROCmVersion, Lmod modules); base package all of ROCm depends on for clean uninstall; rocm-systems/projects/rocm-core"),

    # ── iree-libs ──────────────────────────────────────────────────────────────
    ("iree-libs","—","IREE Compiler & Runtime","TheRock (iree-org/iree)","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only",
     "Direct TheRock submodule from iree-org/iree; tested indirectly via Fusilli Provider; no standalone CI test or dedicated runners"),

    # ── Sysdeps ────────────────────────────────────────────────────────────────
    ("Sysdeps","—","amd-mesa (Display Driver)","TheRock","No",
     "—","—","—","—","—","—","—","—","—","—","—","—","—","—","—",
     "Linux only",
     "Direct TheRock submodule (third-party/sysdeps/linux/amd-mesa/mesa-fork); GPU display driver userspace; no CI test"),

    # ── Frameworks ─────────────────────────────────────────────────────────────
    ("Frameworks","—","PyTorch 2.8","TheRock","Yes",
     "gfx94X (torch only)", "azure-linux-scale-rocm (build)", PC_W_NONE, "—", "quick",
     "gfx94X, gfx950", "azure-linux-scale-rocm (build)", PO_W_NONE, "—", "quick",
     "gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx120X\n(Build-only: gfx900,906,908,101X; gfx1153 excluded)",
     "azure-linux-scale-rocm (build)\n" + NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only",
     "torch+torchaudio+torchvision+triton+apex; py 3.10–3.13; aotriton incompatible with gfx90X/101X/103X/1152/1153; 11 nightly test jobs"),

    ("Frameworks","—","PyTorch 2.9","TheRock","Yes",
     "gfx94X (torch only)", "azure-linux-scale-rocm (build)", PC_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     "gfx94X, gfx950", "azure-linux-scale-rocm (build)", PO_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     NL_FULL, "azure-linux-scale-rocm (build)\n" + NLR_FULL,
     NW_FULL, "azure-windows-scale-rocm (build)\n" + NWR_FULL, "comprehensive",
     "Both", "py 3.10, 3.11, 3.12, 3.13, 3.14; 11 nightly test jobs"),

    ("Frameworks","—","PyTorch 2.10","TheRock","Yes",
     "gfx94X (torch only)", "azure-linux-scale-rocm (build)", PC_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     "gfx94X, gfx950", "azure-linux-scale-rocm (build)", PO_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     NL_FULL, "azure-linux-scale-rocm (build)\n" + NLR_FULL,
     NW_FULL, "azure-windows-scale-rocm (build)\n" + NWR_FULL, "comprehensive",
     "Both", "Default CI branch pin; py 3.10, 3.11, 3.12, 3.13, 3.14; 11 nightly test jobs"),

    ("Frameworks","—","PyTorch 2.11","TheRock","Yes",
     "gfx94X (torch only)", "azure-linux-scale-rocm (build)", PC_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     "gfx94X, gfx950", "azure-linux-scale-rocm (build)", PO_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     NL_FULL, "azure-linux-scale-rocm (build)\n" + NLR_FULL,
     NW_FULL, "azure-windows-scale-rocm (build)\n" + NWR_FULL, "comprehensive",
     "Both", "py 3.10, 3.11, 3.12, 3.13, 3.14; 11 nightly test jobs"),

    ("Frameworks","—","PyTorch nightly","TheRock","Yes",
     "gfx94X (torch only)", "azure-linux-scale-rocm (build)", PC_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     "gfx94X, gfx950", "azure-linux-scale-rocm (build)", PO_W_BUILD, "azure-windows-scale-rocm (build)", "quick",
     NL_FULL, "azure-linux-scale-rocm (build)\n" + NLR_FULL,
     NW_FULL, "azure-windows-scale-rocm (build)\n" + NWR_FULL, "comprehensive",
     "Both", "From pytorch/pytorch main; py 3.10–3.14; 11 nightly test jobs"),

    ("Frameworks","—","JAX 0.8.0","TheRock","Yes (release)",
     "—","—","—","—","—","—","—","—","—","—",
     NL_JAX, "azure-linux-scale-rocm (build)\nlinux-gfx942-1gpu-ossci-rocm (test: gfx94X only)", NW_NONE, "—", "full (4 pytest files)",
     "Linux only", "jaxlib+plugin+pjrt; py 3.11–3.14; release pipeline only"),

    ("Frameworks","—","JAX 0.8.2","TheRock","Yes (release)",
     "—","—","—","—","—","—","—","—","—","—",
     NL_JAX, "azure-linux-scale-rocm (build)\nlinux-gfx942-1gpu-ossci-rocm (test: gfx94X only)", NW_NONE, "—", "full (4 pytest files)",
     "Linux only", "jaxlib+plugin+pjrt; py 3.11–3.14; release pipeline only"),

    ("Frameworks","—","JAX 0.9.0","TheRock","Yes (release)",
     "—","—","—","—","—","—","—","—","—","—",
     NL_JAX, "azure-linux-scale-rocm (build)\nlinux-gfx942-1gpu-ossci-rocm (test: gfx94X only)", NW_NONE, "—", "full (4 pytest files)",
     "Linux only", "jaxlib+plugin+pjrt; py 3.11–3.14; release pipeline only"),

    ("Frameworks","—","JAX 0.9.1","TheRock","Yes (release)",
     "—","—","—","—","—","—","—","—","—","—",
     NL_JAX, "azure-linux-scale-rocm (build)\nlinux-gfx942-1gpu-ossci-rocm (test: gfx94X only)", NW_NONE, "—", "full (4 pytest files)",
     "Linux only", "jaxlib from PyPI; only plugin+pjrt built from source; py 3.11–3.14; release pipeline only"),
]

# ── Live data override (written by fetch_rocm_data.py) ───────────────────────
_data_file = _HERE / "rocm_ci_data.py"
INFERENCEMAX_DATA: list = []
INFERENCE_RUNNERS: dict = {}
_imax_snapshot_ts: str | None = None     # set when JSON fallback was used
_therock_snapshot_ts: str | None = None  # set when JSON fallback was used
if _data_file.exists():
    _data_ns: dict = {}
    exec(_data_file.read_text(encoding="utf-8"), _data_ns)
    COMPONENTS        = _data_ns.get("COMPONENTS",        COMPONENTS)
    INFERENCEMAX_DATA = _data_ns.get("INFERENCEMAX_DATA", [])
    INFERENCE_RUNNERS = _data_ns.get("INFERENCE_RUNNERS",  {})
    _imax_snapshot_ts    = _data_ns.get("IMAX_SNAPSHOT_TS",    None)
    _therock_snapshot_ts = _data_ns.get("THEROCK_SNAPSHOT_TS", None)

# ─── Summary counts ───────────────────────────────────────────────────────────
total      = len(COMPONENTS)
fw_rows    = sum(1 for c in COMPONENTS if c[0] == "Frameworks")
non_fw     = total - fw_rows
ci_enabled = sum(1 for c in COMPONENTS if c[0] != "Frameworks" and c[4] not in ("No","—"))


# ─── HTML generation ─────────────────────────────────────────────────────────
cat_bg = {
    "Libraries":   "#EBF3FB",
    "Tools":       "#EBF5EB",
    "Compilers":   "#FFF9E6",
    "Runtime":     "#FFF0E6",
    "iree-libs":   "#F3E5F5",
    "Sysdeps":     "#FCE4EC",
    "Frameworks":  "#E8F5E9",
}
sub_bg = {
    "Math":           "#D6E4F7",
    "Communication":  "#D5E8D4",
    "Primitives":     "#FFF2CC",
    "ML & CV":        "#F8CECC",
    "Media":          "#FCE4EC",
    "DNN Providers":  "#E8EAF6",
    "System Mgmt":    "#E1D5E7",
    "Performance":    "#E0F7FA",
    "Development":    "#F3E5F5",
}

def cell(v):
    if v in ("—","","None"):
        return '<span class="dash">&mdash;</span>'
    return str(v).replace("\n","<br>")

def ci_badge(v):
    if v == "Yes":   return '<span class="yes">Yes</span>'
    if v == "No":    return '<span class="no">No</span>'
    return f'<span class="part">{v}</span>'

rows_html = ""
for rec in COMPONENTS:
    (cat,sub,comp,repo,ci_en,
     pc_lgfx,pc_lr,pc_wgfx,pc_wr,pc_tt,
     po_lgfx,po_lr,po_wgfx,po_wr,po_tt,
     ni_lgfx,ni_lr,ni_wgfx,ni_wr,ni_tt,
     plat,notes) = rec
    bg = sub_bg.get(sub, cat_bg.get(cat,"#fff"))
    rows_html += f"""<tr style="background:{bg}" data-cat="{cat}" data-ci="{ci_en}">
      <td>{cell(cat)}</td><td>{cell(sub)}</td>
      <td><b>{cell(comp)}</b></td><td style="font-size:13px">{cell(repo)}</td>
      <td>{ci_badge(ci_en)}</td>
      <td class="sep-pc">{cell(pc_lgfx)}</td>
      <td style="font-size:12px">{cell(pc_lr)}</td>
      <td>{cell(pc_wgfx)}</td>
      <td style="font-size:12px">{cell(pc_wr)}</td>
      <td><em>{cell(pc_tt)}</em></td>
      <td class="sep-po">{cell(po_lgfx)}</td>
      <td style="font-size:12px">{cell(po_lr)}</td>
      <td>{cell(po_wgfx)}</td>
      <td style="font-size:12px">{cell(po_wr)}</td>
      <td><em>{cell(po_tt)}</em></td>
      <td class="sep-ni">{cell(ni_lgfx)}</td>
      <td style="font-size:12px">{cell(ni_lr)}</td>
      <td>{cell(ni_wgfx)}</td>
      <td style="font-size:12px">{cell(ni_wr)}</td>
      <td><em>{cell(ni_tt)}</em></td>
      <td class="sep-misc">{cell(plat)}</td>
      <td style="font-size:12px;color:#555">{cell(notes)}</td>
    </tr>\n"""

# ─── Runner data ──────────────────────────────────────────────────────────────
# label, platform, os_distro, location, phys_machines, gpu_family, isa, count, used_at, notes, css_class
RUNNER_DATA = [
    ("linux-gfx942-1gpu-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","84 (vth9c-*: 83 online + 1 offline)","MI300X / MI325X","gfx942 / gfx94X","1","PR · postsubmit · nightly","Primary Linux GPU runner (65% weight); gfx94X Build + Test","runner-linux"),
    ("linux-gfx942-1gpu-ccs-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","4 (cirrascale)","MI300X / MI325X","gfx942 / gfx94X","1","PR · postsubmit · nightly","Pre-commit alternate pool, weighted random selection (weight 0.14)","runner-linux"),
    ("linux-gfx942-1gpu-core42-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","22 (core42 ARC autoscale; was 8 base at 2026-04-22 launch — expanded since)","MI300X / MI325X","gfx942 / gfx94X","1","PR · postsubmit · nightly","Added in PR #4718 (2026-04-22); pre-commit alternate pool (weight 0.27); 1-GPU distribution: 17N (vultr) + 4N (ccs) + 22N (core42); ARC autoscaling — count is point-in-time; live count fluctuates with queue pressure","runner-linux"),
    ("linux-gfx942-8gpu-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","11 (cirrascale)","MI300X / MI325X","gfx942 / gfx94X","8","Nightly · distributed tests · RCCL","PyTorch distributed (3 shards); RCCL multi-GPU; 8-GPU distribution: 11N (cirrascale, weight 0.61) + 7N (core42)","runner-linux"),
    ("linux-gfx942-8gpu-core42-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","7 (core42)","MI300X / MI325X","gfx942 / gfx94X","8","Nightly · distributed tests · RCCL","Added in PR #4718 (2026-04-22); 8-GPU pool alternate (weight 0.39)","runner-linux"),
    ("linux-gfx950-1gpu-ccs-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","3 (j5v9z-* pool)","MI355X","gfx950","1","Postsubmit · nightly","gfx950 single-GPU (CCS host); replaced linux-mi355-1gpu-ossci-rocm in PR #4784 (2026-04-28); postsubmit matrix only","runner-linux"),
    ("linux-gfx950-8gpu-ccs-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","1 (initial onboarding)","MI355X","gfx950","8","Postsubmit · nightly (multi-GPU)","Added in PR #4784 (2026-04-28); MI355 8-GPU lane for multi-GPU postsubmit/nightly tests","runner-linux"),
    ("linux-gfx90a-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem (AUS)","12 GPU slots (3 nodes × 4)","MI200","gfx90a","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","Supermicro nodes in Australia datacenter; nightly_check_only_for_family in nightly matrix","runner-linux"),
    ("linux-gfx1030-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","2","RX 6000 (RDNA2)","gfx1030 / gfx103X","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","Consumer GPU (RX 6950 XT); nightly_check_only_for_family","runner-linux"),
    ("linux-gfx110X-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","8 (gfx110X-gpu-rocm-1/2/3/5/6 + labctr-gfx1103 + labxsj-gfx1103 + 1 OrchestrAI Managed: CS-RORDMZ-DT77)","Navi3 / RX 7900","gfx1100/1101","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","nightly_check_only_for_family; builds at PR/postsubmit, tests only at nightly; -3 registers as 2 GHA runners (one per GPU); -5/-6 added since 2026-04-20 snapshot","runner-linux"),
    ("linux-gfx1150-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","2 (labblr-linux-u2404-gfx1150-runner + linux-strix-gpu-rocm-2; both also carry linux-gfx115X-gpu-rocm)","Strix Point","gfx1150","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","APU — Strix Point; nightly_check_only_for_family","runner-linux"),
    ("linux-gfx1151-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","7 (strix-halo-3/5/6/7/8/9 + 1 OrchestrAI Managed: CS-RORDMZ-DT222)","Strix Halo","gfx1151","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","nightly_check_only_for_family on Linux; strix-halo-3 was previously mis-labelled (now properly registered); shark-strixhalo-17/18 offline; -5/-8/-9 added since 2026-04-20 snapshot; all also carry linux-strix-halo-gpu-rocm-oem + linux-gfx115X-gpu-rocm","runner-linux"),
    ("linux-strix-halo-gpu-rocm-oem","Linux","Ubuntu 22.04 LTS","On-Prem","6 (strix-halo-3/5/6/7/8/9; same physical hardware as linux-gfx1151-gpu-rocm)","Strix Halo (OEM)","gfx1151","1","PR (Build) · postsubmit (Build) · nightly (Build + Test on test_runner:oem PR label)","OEM kernel variant of gfx1151 lane; selected via test_runner:oem PR label; inherits nightly_check_only_for_family; same physical machines as linux-gfx1151-gpu-rocm — counted ONCE per family in live aggregates","runner-linux"),
    ("linux-gfx1153-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","3","Krackan Point (Radeon 820M)","gfx1153","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","APU — Krackan Point; nightly_check_only_for_family; disabled since 7.12.0a20260214 (CK instability); gfx1152 (Krackan 840M) is a separate ISA target","runner-linux"),
    ("linux-gfx120X-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","8 (rx9070-1 [registers as gfx120X-gpu-rocm-1, 2 GHA per machine] + rx9070-4 + rx9700-1 + 4 OrchestrAI Managed: CS-RORDMZ-DT72/81/83/87)","Navi4 / RX 9070","gfx1200/1201","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","nightly_check_only_for_family; rx9070-2 lacks gfx120X label (offline); rx9070-3 currently offline; OrchestrAI shared dev pool added since 2026-04-20","runner-linux"),
    ("windows-gfx1151-gpu-rocm","Windows","Windows 11","On-Prem","11 (strix-halo-1/4/6/8/10-16; -7 DO-NOT-ENABLE)","Strix Halo","gfx1151","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","Primary Windows GPU runner; nightly_check_only_for_family on Windows too; strix-halo-7 excluded (DO-NOT-ENABLE flag)","runner-windows"),
    ("windows-gfx110X-gpu-rocm","Windows","Windows 11","On-Prem","23 (22 online + 1 offline; azure-windows-11-gfx1101-*)","Navi3 / RX 7900 (gfx1101)","gfx1100/1101","1","PR · postsubmit · nightly","Tests at all 3 tiers; Windows gfx110X cfg has NO nightly_check_only_for_family flag (unlike Linux side)","runner-windows"),
    ("windows-gfx1030-gpu-rocm","Windows","Windows 11","On-Prem","2","RX 6000 (RDNA2)","gfx1030","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","nightly_check_only_for_family","runner-windows"),
    ("windows-gfx120X-gpu-rocm","Windows","Windows 11","On-Prem","5 (label now active; 5 machines registered as windows-gfx120X-gpu-rocm; also accept the windows-gfx1201-gpu-rocm alias)","Navi4 / RX 9070","gfx1200/1201","1","PR (Build) · postsubmit (Build) · nightly (Build + Test)","nightly_check_only_for_family; label was missing in 2026-04-20 snapshot but is now active in fleet (alongside windows-gfx1201-gpu-rocm)","runner-windows"),
    ("azure-linux-scale-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","~113 VMs (112 ccqkb-* online + 1 heavy runner)","None (build only)","—","—","All tiers (build jobs)","Elastic Azure build pool; no GPU; used for all compile/package jobs","runner-build"),
    ("azure-windows-scale-rocm","Windows","Windows Server 2022","OSSCI","69 VMs (ckv2f-*: 67 online + 2 offline)","None (build only)","—","—","All tiers (build jobs)","Elastic Windows build pool; no GPU","runner-build"),
    ("nova-linux-slurm-scale-runner","Linux","Ubuntu 22.04 LTS","On-Prem","1 (currently offline)","MI355X multi-node","gfx950","N","RCCL multi-node only","RCCL CI in rocm-systems; Slurm job scheduler; offline as of Apr 20 snapshot","runner-linux"),
    ("rocm-asan-mi325-sandbox","Linux","Ubuntu 22.04 LTS","On-Prem","1 (rocm-banff-asan-mi325-sandbox; offline)","MI325X (sandbox)","gfx942","1","ASAN nightly","GPU-contamination-safe sandbox; offline as of Apr 20 snapshot","runner-linux"),
    ("self-hosted (amdsmi/aqlprofile)","Linux","Ubuntu 22.04 LTS","On-Prem","Varies","Various","—","—","Per-component own CI","amdsmi, aqlprofile own CI runners","runner-build"),
    ("ubuntu-24.04","Linux","Ubuntu 24.04 LTS","GitHub-hosted","Unlimited (cloud)","None (no GPU)","—","—","Setup / matrix jobs","GitHub-managed cloud runners","runner-build"),
    ("windows-2022","Windows","Windows Server 2022","GitHub-hosted","Unlimited (cloud)","None (no GPU)","—","—","Fallback / fork CI","GitHub-managed cloud runners","runner-build"),
]

# ─── Per-framework server counts (parsed from RUNNER_DATA phys_machines field) ──
def _parse_server_count(phys_str: str) -> int:
    m = re.match(r"\s*~?\s*(\d+)", str(phys_str))
    return int(m.group(1)) if m else 0

_runner_counts: dict = {rec[0]: _parse_server_count(rec[4]) for rec in RUNNER_DATA}

# ── Optional: load runner-health dashboard data ──────────────────────────────
# Three-tier source chain (handled by runner_health_parser.load_runner_health_any):
#   1. local TheRock Runner Health.mhtml   (saved manually from the dashboard;
#                                           NOT committed to the repo)
#   2. live HTTPS GET of therock-runner-health.com  (works only when the host
#                                           is reachable AND the request isn't
#                                           bounced to GitHub OAuth)
#   3. runner_health_snapshot.json         (committed fallback so the report
#                                           always renders something current)
_RUNNER_HEALTH = None
_RUNNER_HEALTH_SOURCE = None  # "mhtml" / "live" / "snapshot" / None
try:
    from runner_health_parser import load_runner_health_any
    from pathlib import Path as _P
    _here = _P(__file__).parent
    _mhtml_candidates = [
        _here / "TheRock Runner Health.mhtml",
        _here / "runner_health.mhtml",
        _here / "runner-health.mhtml",
        _here / "TheRockRunnerHealth.mhtml",
    ]
    _RUNNER_HEALTH, _RUNNER_HEALTH_SOURCE = load_runner_health_any(
        mhtml_candidates=_mhtml_candidates,
        live_url="https://therock-runner-health.com/",
        snapshot_path=_here / "runner_health_snapshot.json",
        refresh_snapshot=True,
        try_live=True,
    )
    if _RUNNER_HEALTH:
        print(f"  [runner-health] Loaded via {_RUNNER_HEALTH_SOURCE}: "
              f"{len(_RUNNER_HEALTH.per_machine)} machines, "
              f"{len(_RUNNER_HEALTH.per_label)} labelled metrics")
    else:
        print("  [runner-health] No source available (no mhtml, live unreachable, no snapshot).")
except Exception as _e:
    print(f"  [runner-health] WARN: {_e}")

# ── Helper: group a list of runner labels by gfx family for "Runner Labels & Counts" cells ──
_runner_meta = {rec[0]: {"isa": rec[6], "gpu": rec[5], "platform": rec[1]} for rec in RUNNER_DATA}

# ── Pool-type classification ─────────────────────────────────────────────────
# Distinguishes:
#   bare-metal — fixed physical GPU/build hardware (counts are stable)
#   ARC-GPU    — elastic GHA Actions Runner Controller pool with GPU passthrough
#                (Build + Test capable; counts are point-in-time, can autoscale)
#   ARC-VM     — elastic ARC pool with NO GPU (Build-only)
#   Slurm      — multi-node Slurm-managed cluster
#   Sandbox    — quarantined ASAN/dev sandbox
#   GitHub     — GitHub-hosted cloud runners (Build-only fallback)
_POOL_TYPE = {
    "linux-gfx942-1gpu-ossci-rocm":          "ARC-GPU",   # vth9c-* Vultr cloud
    "linux-gfx942-1gpu-ccs-ossci-rocm":      "bare-metal",
    "linux-gfx942-1gpu-core42-ossci-rocm":   "ARC-GPU",   # core42 ARC autoscale
    "linux-gfx942-8gpu-ossci-rocm":          "bare-metal",
    "linux-gfx942-8gpu-core42-ossci-rocm":   "bare-metal",
    "linux-gfx950-1gpu-ccs-ossci-rocm":      "ARC-GPU",   # j5v9z-* pool
    "linux-gfx950-8gpu-ccs-ossci-rocm":      "bare-metal",
    "linux-gfx90a-gpu-rocm":                 "bare-metal",
    "linux-gfx1030-gpu-rocm":                "bare-metal",
    "linux-gfx110X-gpu-rocm":                "bare-metal",
    "linux-gfx1150-gpu-rocm":                "bare-metal",
    "linux-gfx1151-gpu-rocm":                "bare-metal",
    "linux-strix-halo-gpu-rocm-oem":         "bare-metal",
    "linux-gfx1153-gpu-rocm":                "bare-metal",
    "linux-gfx120X-gpu-rocm":                "bare-metal",
    "windows-gfx1151-gpu-rocm":              "bare-metal",
    "windows-gfx110X-gpu-rocm":              "bare-metal",
    "windows-gfx1030-gpu-rocm":              "bare-metal",
    "windows-gfx120X-gpu-rocm":              "bare-metal",
    "azure-linux-scale-rocm":                "ARC-VM",
    "azure-windows-scale-rocm":              "ARC-VM",
    "nova-linux-slurm-scale-runner":         "Slurm",
    "rocm-asan-mi325-sandbox":               "Sandbox",
    "self-hosted (amdsmi/aqlprofile)":       "bare-metal",
    "ubuntu-24.04":                          "GitHub",
    "windows-2022":                          "GitHub",
}

# Visual style per pool type — short tag + tooltip + colour
_POOL_TAG = {
    "bare-metal": ('<span title="Fixed bare-metal hardware — count is stable" '
                   'style="display:inline-block;padding:0 4px;border-radius:3px;'
                   'background:#1B5E20;color:#fff;font-size:9px;font-weight:700;'
                   'margin-left:4px;vertical-align:middle">BM</span>'),
    "ARC-GPU":   ('<span title="ARC ephemeral pool with GPU passthrough — Build + Test capable; '
                   'count is point-in-time and autoscales with queue pressure" '
                   'style="display:inline-block;padding:0 4px;border-radius:3px;'
                   'background:#F9A825;color:#000;font-size:9px;font-weight:700;'
                   'margin-left:4px;vertical-align:middle">ARC-GPU</span>'),
    "ARC-VM":    ('<span title="ARC elastic VM pool — no GPU, Build-only" '
                   'style="display:inline-block;padding:0 4px;border-radius:3px;'
                   'background:#90A4AE;color:#fff;font-size:9px;font-weight:700;'
                   'margin-left:4px;vertical-align:middle">VM</span>'),
    "Slurm":     ('<span title="Slurm-scheduled multi-node cluster" '
                   'style="display:inline-block;padding:0 4px;border-radius:3px;'
                   'background:#4527A0;color:#fff;font-size:9px;font-weight:700;'
                   'margin-left:4px;vertical-align:middle">Slurm</span>'),
    "Sandbox":   ('<span title="Quarantined sandbox runner" '
                   'style="display:inline-block;padding:0 4px;border-radius:3px;'
                   'background:#6D4C41;color:#fff;font-size:9px;font-weight:700;'
                   'margin-left:4px;vertical-align:middle">Sandbox</span>'),
    "GitHub":    ('<span title="GitHub-hosted cloud runner (no GPU)" '
                   'style="display:inline-block;padding:0 4px;border-radius:3px;'
                   'background:#37474F;color:#fff;font-size:9px;font-weight:700;'
                   'margin-left:4px;vertical-align:middle">GitHub</span>'),
}

def _pool_tag(label: str) -> str:
    """Return small inline pool-type badge for a runner label."""
    pt = _POOL_TYPE.get(label, "bare-metal")
    return _POOL_TAG.get(pt, "")

# Map detailed ISA strings (col 6 of RUNNER_DATA) to a canonical short family + GPU description.
_GFX_GROUP_NAMES = {
    "gfx942 / gfx94X":   ("gfx94X",  "MI300X / MI325X"),
    "gfx950":            ("gfx950",  "MI355X"),
    "gfx90a":            ("gfx90a",  "MI200"),
    "gfx1030 / gfx103X": ("gfx103X", "RX 6000 (RDNA2)"),
    "gfx1030":           ("gfx103X", "RX 6000 (RDNA2)"),
    "gfx1100/1101":      ("gfx110X", "Navi3 / RX 7900"),
    "gfx1150":           ("gfx1150", "Strix Point APU"),
    "gfx1151":           ("gfx1151", "Strix Halo"),
    "gfx1153":           ("gfx1153", "Krackan Point APU"),
    "gfx1200/1201":      ("gfx120X", "Navi4 / RX 9070"),
}

def _normalize_isa(isa: str) -> tuple:
    if isa in _GFX_GROUP_NAMES:
        return _GFX_GROUP_NAMES[isa]
    short = isa.split("/")[0].strip().split(" ")[0]
    return (short, "")

def _live_status_chip(label: str) -> str:
    """Render the inline live online/busy/idle/offline split for a runner
    label, or '' if no live data exists. Plain numeric breakdown — no
    badges, no status pills (kept executive-friendly)."""
    if not _RUNNER_HEALTH:
        return ""
    busy, idle = _RUNNER_HEALTH.label_busy_idle(label)
    online = busy + idle
    if online == 0:
        return ""
    snap_total = _runner_counts.get(label, 0)
    offline = max(0, snap_total - online) if snap_total else 0
    off_part = f" &middot; <b>{offline}</b> offline" if offline else ""
    return (f' <span style="color:#1B5E20" '
            f'title="Snapshot: {snap_total} declared nodes for this label. '
            f'Dashboard enumerates {online} online runners ({busy} busy + {idle} idle). '
            f'The remaining {offline} are offline or unreachable.">'
            f'&#x25CF; live: <b>{online}</b> online ({busy} busy / {idle} idle){off_part}</span>')


def _runner_labels_by_gfx_html(labels: list) -> str:
    """Render the given runner labels grouped by gfx family.
    Each row shows: family / GPU description / subtotal / per-label count.
    When runner-health data is loaded, also shows the live
    online / busy / idle / offline split per label. Pool-type badges and
    queue-health pills are intentionally omitted to keep the column
    executive-readable; pool composition lives in the Comments column."""
    from collections import OrderedDict
    groups = OrderedDict()
    for label in labels:
        meta = _runner_meta.get(label)
        if not meta:
            continue
        short, desc = _normalize_isa(meta["isa"])
        if not desc and meta["gpu"]:
            desc = meta["gpu"]
        if short not in groups:
            groups[short] = {"desc": desc, "items": []}
        groups[short]["items"].append((label, _runner_counts.get(label, 0), meta["platform"]))

    parts = ['<div style="font-size:12px;line-height:1.6">']
    for short, info in groups.items():
        total = sum(c for _, c, _ in info["items"])
        # Live family-level totals — DEDUPLICATED across labels by physical
        # machine identity, so multi-label / multi-GPU machines are not
        # double-counted. (See runner_health_parser.physical_id.)
        live_online = live_busy = 0
        if _RUNNER_HEALTH:
            family_labels = [label for label, _, _ in info["items"]]
            live_busy, live_idle_tmp = _RUNNER_HEALTH.family_busy_idle(family_labels)
            live_online = live_busy + live_idle_tmp
        live_idle    = live_online - live_busy
        live_offline = max(0, total - live_online)  # offline = declared - currently-online
        plats = sorted(set(p for _, _, p in info["items"]))
        plat_tag = (' <span style="color:#888;font-size:11px">(L+W)</span>' if len(plats) > 1
                    else f' <span style="color:#888;font-size:11px">({plats[0][0]})</span>')
        family_live = ""
        if _RUNNER_HEALTH and (live_online > 0 or live_offline > 0):
            family_live = (
                f' <span style="color:#1B5E20;font-weight:400;font-size:11px"'
                f' title="Snapshot: {total} declared physical nodes &#10;'
                f'Online now: {live_online} ({live_busy} busy + {live_idle} idle) &#10;'
                f'Offline / unenumerated: {live_offline}">'
                f'(live: <b>{live_online}</b> online = {live_busy} busy + {live_idle} idle'
                f'{f" &middot; {live_offline} offline" if live_offline else ""})'
                f'</span>'
            )
        parts.append(
            f'<div style="margin-bottom:5px"><b style="color:#000;font-size:12.5px">{short}</b>{plat_tag} '
            f'<span style="color:#666">{info["desc"]}</span> &mdash; <b>{total}</b> nodes{family_live}'
        )
        for label, count, _plat in info["items"]:
            chip = _live_status_chip(label)
            parts.append(
                f'<div style="margin-left:14px;color:#333">&bull; '
                f'<code style="font-size:12px;color:#1565C0">{label}</code> = <b>{count}</b>{chip}</div>'
            )
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)

# ── Snapshot caveats per runner label (DO-NOT-ENABLE, mis-labelled, offline) ──
# Pulled from RUNNER_DATA phys_machines (idx 4) + notes (idx 9) — these are the
# operationally interesting facts to surface in the per-tier "Comments" column.
_runner_phys_note = {rec[0]: rec[4]  for rec in RUNNER_DATA}  # e.g. "11 (strix-halo-1/...; -7 DO-NOT-ENABLE)"
_runner_op_notes  = {rec[0]: rec[9]  for rec in RUNNER_DATA}

def _caveats_for_label(label: str) -> list:
    """Return a short list of human-readable caveats for a runner label
    (e.g. 'strix-halo-7 DO-NOT-ENABLE', 'rx9070-2 mis-labelled', 'offline')."""
    caveats = []
    phys = _runner_phys_note.get(label, "")
    note = _runner_op_notes.get(label, "")
    text = f"{phys} | {note}"
    low  = text.lower()
    # Curated patterns we care about — keep the raw fragment around
    if "do-not-enable" in low:
        caveats.append("DO-NOT-ENABLE flag on a node (e.g. strix-halo-7)" if "strix-halo" in low else "DO-NOT-ENABLE flag")
    if "mis-labelled" in low:
        # Pull the offending node name when present (e.g. "strix-halo-3 mis-labelled")
        m = re.search(r'([A-Za-z0-9\-]+)\s+mis-labelled', text)
        caveats.append(f"{m.group(1)} mis-labelled" if m else "mis-labelled node")
    # Honest "offline" mentions ONLY if not the generic "online + N offline" formula
    if "currently offline" in low or "offline as of" in low:
        caveats.append("entire pool offline at last snapshot")
    return caveats

def _gfx_os_breakdown_html(labels: list, include_caveats: bool = True) -> str:
    """Compact summary table: per-gfx total, broken down by Linux/Windows
    online vs offline. When runner-health is loaded, "online" comes from the
    live dashboard; "offline" = declared (snapshot) - online. When absent,
    everything falls back to the snapshot count.
    Also lists per-label caveats (DO-NOT-ENABLE, mis-labelled, offline)."""
    from collections import OrderedDict
    fams = OrderedDict()
    for label in labels:
        meta = _runner_meta.get(label)
        if not meta:
            continue
        short, desc = _normalize_isa(meta["isa"])
        if not desc and meta["gpu"]:
            desc = meta["gpu"]
        fam = fams.setdefault(short, {"desc": desc, "Linux": [], "Windows": []})
        fam[meta["platform"]].append(label)

    if not fams:
        return ""

    # Helpers to compute (declared, online, offline) for a list of labels.
    # Live count is deduplicated by physical-machine identity so a multi-GPU
    # or multi-label runner is counted once.
    def _stats(label_list):
        decl = sum(_runner_counts.get(l, 0) for l in label_list)
        if _RUNNER_HEALTH:
            b, i = _RUNNER_HEALTH.family_busy_idle(label_list)
            online = b + i
        else:
            online = decl  # no live data → assume all online
        offline = max(0, decl - online)
        return decl, online, offline

    parts = ['<div style="font-size:11px;line-height:1.45;margin-top:6px">'
             '<div style="font-weight:700;color:#37474F;margin-bottom:3px;font-size:11.5px">'
             '&#x1F4CA; Online / Offline by gfx (Linux + Windows)</div>'
             '<table style="border-collapse:collapse;font-size:11px;width:100%;margin-bottom:4px">'
             '<thead><tr style="color:#fff;font-weight:700">'
             '<th style="padding:3px 6px;text-align:left;border:1px solid #CFD8DC;background:#37474F">gfx</th>'
             '<th style="padding:3px 6px;text-align:center;border:1px solid #CFD8DC;background:#546E7A" title="Total = declared physical nodes per RUNNER_DATA snapshot. Online + Offline.">Total</th>'
             '<th style="padding:3px 6px;text-align:center;border:1px solid #2E7D32;background:#2E7D32">Online</th>'
             '<th style="padding:3px 6px;text-align:center;border:1px solid #C62828;background:#C62828">Offline</th>'
             '<th style="padding:3px 6px;text-align:left;border:1px solid #CFD8DC;background:#37474F">Per-OS</th>'
             '</tr></thead><tbody>']
    all_caveats = []
    for short, info in fams.items():
        all_lbls = info["Linux"] + info["Windows"]
        decl, online, offline = _stats(all_lbls)
        os_parts = []
        for ostag in ("Linux", "Windows"):
            if info[ostag]:
                d, o, off = _stats(info[ostag])
                color = "#1B5E20" if off == 0 else "#B71C1C"
                os_parts.append(
                    f'<b>{ostag[0]}</b>: '
                    f'<span style="color:#1B5E20">{o}</span>/{d} on'
                    f'{f", <span style=\"color:{color}\"><b>{off}</b> off</span>" if off else ""}'
                )
        parts.append(
            f'<tr>'
            f'<td style="padding:2px 5px;border:1px solid #CFD8DC;white-space:nowrap"><b style="color:#000">{short}</b>'
            f' <span style="color:#888;font-size:10px">{info["desc"]}</span></td>'
            f'<td style="padding:2px 5px;text-align:center;border:1px solid #CFD8DC">{decl}</td>'
            f'<td style="padding:2px 5px;text-align:center;border:1px solid #CFD8DC;color:#1B5E20"><b>{online}</b></td>'
            f'<td style="padding:2px 5px;text-align:center;border:1px solid #CFD8DC;'
            f'color:{"#B71C1C" if offline else "#999"}"><b>{offline}</b></td>'
            f'<td style="padding:2px 5px;border:1px solid #CFD8DC;font-size:10.5px;line-height:1.4">'
            f'{" &nbsp;|&nbsp; ".join(os_parts)}</td>'
            f'</tr>'
        )
        if include_caveats:
            for lbl in all_lbls:
                for c in _caveats_for_label(lbl):
                    all_caveats.append((short, lbl, c))
    parts.append('</tbody></table>')
    # Pool-type breakdown for the labels in scope
    pool_counts: dict = {}
    for short, info in fams.items():
        for ostag in ("Linux", "Windows"):
            for lbl in info[ostag]:
                pt = _POOL_TYPE.get(lbl, "bare-metal")
                pool_counts[pt] = pool_counts.get(pt, 0) + _runner_counts.get(lbl, 0)
    if pool_counts:
        legend_parts = []
        for pt in ("bare-metal", "ARC-GPU", "ARC-VM", "Slurm", "Sandbox", "GitHub"):
            if pt in pool_counts:
                tag = _POOL_TAG.get(pt, "")
                legend_parts.append(f'{tag} = <b>{pool_counts[pt]}</b>')
        parts.append('<div style="font-size:10px;color:#37474F;margin-top:3px;line-height:1.7">'
                     '<b>Pool types:</b> ' + " &nbsp; ".join(legend_parts) + '</div>')

    if all_caveats and include_caveats:
        parts.append('<div style="font-size:10.5px;color:#5D4037;margin-top:4px;line-height:1.4">'
                     '<b>Caveats:</b><br>')
        cav_html = "<br>".join(
            f'&bull; <code style="font-size:10px">{lbl}</code>: <span style="color:#B71C1C">{c}</span>'
            for short, lbl, c in all_caveats
        )
        parts.append(cav_html + '</div>')
    parts.append('</div>')
    return "".join(parts)

# Curated runner sets per CI tier (used by Component CI Matrix summary table)
# Pre-commit: gfx94X test pool (all 3 1-GPU lanes + 2 8-GPU lanes + ASAN sandbox) + Windows build-only
_PC_GPU_LABELS = [
    "linux-gfx942-1gpu-ossci-rocm", "linux-gfx942-1gpu-ccs-ossci-rocm", "linux-gfx942-1gpu-core42-ossci-rocm",
    "linux-gfx942-8gpu-ossci-rocm", "linux-gfx942-8gpu-core42-ossci-rocm",
    "rocm-asan-mi325-sandbox",
    "windows-gfx1151-gpu-rocm",
]
# Post-commit: pre-commit pool + gfx950 (1-GPU + 8-GPU)
_PO_GPU_LABELS = _PC_GPU_LABELS + [
    "linux-gfx950-1gpu-ccs-ossci-rocm", "linux-gfx950-8gpu-ccs-ossci-rocm",
]
# Nightly: everything (all GPU runners)
_NI_GPU_LABELS = [r[0] for r in RUNNER_DATA if r[10] in ("runner-linux", "runner-windows")]

_pt_build_servers = _runner_counts.get("azure-linux-scale-rocm", 0) + _runner_counts.get("azure-windows-scale-rocm", 0)
_pt_gpu_runners = [
    ("linux-gfx942-1gpu-ossci-rocm", "gfx94X (MI300X/MI325X)"),
    ("linux-gfx942-8gpu-ossci-rocm", "gfx94X 8-GPU distributed"),
    ("linux-gfx950-1gpu-ccs-ossci-rocm",  "gfx950 (MI355X)"),
    ("linux-gfx90a-gpu-rocm",        "gfx90a (MI200)"),
    ("linux-gfx1030-gpu-rocm",       "gfx103X (RDNA2)"),
    ("linux-gfx110X-gpu-rocm",       "gfx110X (Navi3)"),
    ("linux-gfx1150-gpu-rocm",       "gfx1150 (Strix Point)"),
    ("linux-gfx1151-gpu-rocm",       "gfx1151 (Strix Halo)"),
    ("linux-gfx1153-gpu-rocm",       "gfx1153 (Krackan)"),
    ("linux-gfx120X-gpu-rocm",       "gfx120X (Navi4)"),
    ("windows-gfx1151-gpu-rocm",     "gfx1151 Windows"),
    ("windows-gfx110X-gpu-rocm",     "gfx110X Windows"),
    ("windows-gfx1030-gpu-rocm",     "gfx103X Windows"),
]
_pt_gpu_total     = sum(_runner_counts.get(lbl, 0) for lbl, _ in _pt_gpu_runners)
_pt_total_servers = _pt_build_servers + _pt_gpu_total
_pt_combinations  = f"5 versions × 5 Python vers × {len(_pt_gpu_runners)} GPU runner types"

# Per-runner breakdown strings for the server table
_pt_gpu_runner_breakdown = " &bull; ".join(
    f"{lbl} ({desc}) = <b>{_runner_counts.get(lbl, 0)}</b>"
    for lbl, desc in _pt_gpu_runners
)

# Pre-computed gfx-grouped HTML for "Runner Labels & Counts" cells
_pc_runner_grouped_html = _runner_labels_by_gfx_html(_PC_GPU_LABELS)
_po_runner_grouped_html = _runner_labels_by_gfx_html(_PO_GPU_LABELS)
_ni_runner_grouped_html = _runner_labels_by_gfx_html(_NI_GPU_LABELS)
# Framework PyTorch uses the full set (all gfx tested by PyTorch nightly)
_pt_runner_grouped_html = _runner_labels_by_gfx_html(_NI_GPU_LABELS)

# Pre-computed gfx × OS online/offline breakdown for "Comments" column
_pc_breakdown_html = _gfx_os_breakdown_html(_PC_GPU_LABELS)
_po_breakdown_html = _gfx_os_breakdown_html(_PO_GPU_LABELS)
_ni_breakdown_html = _gfx_os_breakdown_html(_NI_GPU_LABELS)
_pt_breakdown_html = _gfx_os_breakdown_html(_NI_GPU_LABELS)
_jax_breakdown_html = _gfx_os_breakdown_html(["linux-gfx942-1gpu-ossci-rocm"])

# Optional live-status banner — populated from runner-health dashboard if available.
if _RUNNER_HEALTH:
    _s = _RUNNER_HEALTH.summary
    _gpu = _s.get("resource", {}).get("GPU", {})
    _cpu = _s.get("resource", {}).get("CPU", {})
    _src = _RUNNER_HEALTH_SOURCE or "?"
    _src_chip = {
        "mhtml":    ('#2E7D32', '#E8F5E9', 'fresh — local <code>TheRock Runner Health.mhtml</code>'),
        "live":     ('#1565C0', '#E3F2FD', 'fresh — live HTTPS fetch of therock-runner-health.com'),
        "snapshot": ('#EF6C00', '#FFF3E0', 'cached snapshot — <code>runner_health_snapshot.json</code> '
                                            '(live dashboard unreachable, no local .mhtml)'),
    }.get(_src, ('#555', '#EEE', _src))
    _live_status_banner = (
        f'<div style="margin:0 0 14px 0;padding:10px 14px;background:{_src_chip[1]};'
        f'border-left:4px solid {_src_chip[0]};border-radius:4px;font-size:12px;color:#1B1B1B">'
        f'&#x1F4E1; <b>Runner-health snapshot</b> &mdash; source: '
        f'<span style="background:{_src_chip[0]};color:#fff;padding:1px 8px;border-radius:10px;'
        f'font-weight:600;font-size:11px">{_src}</span> &nbsp;'
        f'<span style="color:#555">{_src_chip[2]}</span><br>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;refreshed '
        f'<b>{_RUNNER_HEALTH.refresh_time or "(time unknown)"}</b> '
        f'(<a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="color:{_src_chip[0]};font-weight:600">therock-runner-health.com</a>):'
        f'<br>&nbsp;&nbsp;&nbsp;&nbsp;'
        f'<b>{_s.get("online", "?")}</b> online &middot; '
        f'<b>{_s.get("offline", "?")}</b> offline &middot; '
        f'<b>{_s.get("busy", "?")}</b> busy &middot; '
        f'<b>{_s.get("idle", "?")}</b> idle '
        f'&nbsp;|&nbsp; '
        f'<b>GPU pool:</b> {_gpu.get("online","?")}/{_gpu.get("total","?")} online '
        f'({_gpu.get("busy","?")} busy, {_gpu.get("idle","?")} idle, {_gpu.get("offline","?")} offline) '
        f'&nbsp;|&nbsp; '
        f'<b>CPU pool:</b> {_cpu.get("online","?")}/{_cpu.get("total","?")} online '
        f'({_cpu.get("busy","?")} busy, {_cpu.get("idle","?")} idle)'
        f'<br><span style="font-size:11px;color:#555">Each gfx group below shows the declared count plus live online / busy / idle / offline split per runner label.</span>'
        f'</div>'
    )
else:
    _live_status_banner = (
        f'<div style="margin:0 0 14px 0;padding:10px 14px;background:#FFF3E0;border-left:4px solid #F57C00;'
        f'border-radius:4px;font-size:12px;color:#777">'
        f'&#x1F4E1; <b>Runner-health data not available.</b> Resolution order: '
        f'(1) drop a saved page from <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="color:#1565C0">therock-runner-health.com</a> '
        f'as <code>TheRock Runner Health.mhtml</code> in this folder, or '
        f'(2) be on the AMD network so the live dashboard is reachable, or '
        f'(3) ensure <code>runner_health_snapshot.json</code> is present in this folder.'
        f'</div>'
    )
# Recomputed total counts based on new comprehensive sets
_pc_gpu_nodes_full = sum(_runner_counts.get(l, 0) for l in _PC_GPU_LABELS)
_po_gpu_nodes_full = sum(_runner_counts.get(l, 0) for l in _PO_GPU_LABELS)
_ni_gpu_nodes_full = sum(_runner_counts.get(l, 0) for l in _NI_GPU_LABELS)

_jax_build_servers = _runner_counts.get("azure-linux-scale-rocm", 0)
_jax_gpu_servers   = _runner_counts.get("linux-gfx942-1gpu-ossci-rocm", 0)
_jax_total_servers = _jax_build_servers + _jax_gpu_servers
_jax_combinations  = "4 versions × 4 Python vers × 1 GPU runner type (gfx94X test-only)"
_grand_physical    = _ni_gpu_nodes_full   # unique physical GPU machines used by frameworks (JAX shares PyTorch's pool — no double-count)
_grand_total       = _pt_build_servers + _grand_physical # shared build VMs + unique physical GPU machines

# ── Per-tier server counts for Component CI Matrix summary bar ──────────────
_build_vms        = _pt_build_servers   # 182 shared Azure VMs (Linux 113 + Windows 69)
_pc_gpu_nodes     = (_runner_counts.get("linux-gfx942-1gpu-ossci-rocm", 0) +
                     _runner_counts.get("windows-gfx1151-gpu-rocm", 0))          # 84 + 11 = 95
_po_gpu_nodes     = (_pc_gpu_nodes +
                     _runner_counts.get("linux-gfx950-1gpu-ccs-ossci-rocm", 0))        # +3 = 98
_ni_gpu_nodes     = _pt_gpu_total                                                 # 159 (all unique)
_ni_runner_types  = len(_pt_gpu_runners)                                          # 13

_imax_server_total = sum(
    len(nodes) for nodes in INFERENCE_RUNNERS.get("amd", {}).values()
) if INFERENCE_RUNNERS else 0

plat_bg  = {"runner-linux":"#EBF3FB","runner-windows":"#EBF5EB","runner-build":"#FFF9E6"}
loc_badge = {"OSSCI":"#1565C0","On-Prem":"#2E7D32","On-Prem (AUS)":"#2E7D32","GitHub-hosted":"#555"}

# ── Location summary for physical GPU runners (runner-linux / runner-windows, non-build) ──
from collections import defaultdict as _dd
_loc_summary: dict = _dd(lambda: {"count": 0, "runners": [], "linux": 0, "windows": 0})
for _rec in RUNNER_DATA:
    _lbl, _plat, _os, _loc, _phys, _gpu_fam, _isa, _cnt, _used, _notes, _cls = _rec
    if _cls in ("runner-linux", "runner-windows"):
        _n = _parse_server_count(_phys)
        if _n > 0:
            _loc_key = "On-Prem" if _loc.startswith("On-Prem") else _loc
            _loc_summary[_loc_key]["count"] += _n
            _loc_summary[_loc_key]["runners"].append(_lbl)
            if _cls == "runner-linux":
                _loc_summary[_loc_key]["linux"] += _n
            else:
                _loc_summary[_loc_key]["windows"] += _n
_loc_total = sum(v["count"] for v in _loc_summary.values())

_loc_summary_rows = ""
_loc_colors = {"OSSCI": "#1565C0", "On-Prem": "#2E7D32", "GitHub-hosted": "#555"}
for _loc_key, _data in sorted(_loc_summary.items()):
    _color = _loc_colors.get(_loc_key, "#555")
    _pct = round(_data["count"] / _loc_total * 100) if _loc_total else 0
    _linux_str = str(_data["linux"]) if _data["linux"] else "—"
    _win_str   = str(_data["windows"]) if _data["windows"] else "—"
    _loc_summary_rows += f"""<tr>
  <td><span style="background:{_color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12.5px;white-space:nowrap">{_loc_key}</span></td>
  <td style="text-align:center;font-weight:700;font-size:14px">{_data["count"]}</td>
  <td style="text-align:center">{_linux_str}</td>
  <td style="text-align:center">{_win_str}</td>
  <td style="text-align:center;color:#555;font-size:12.5px">{_pct}%</td>
</tr>\n"""
_loc_summary_rows += f"""<tr style="background:#37474F;color:#fff;font-weight:700">
  <td>Total</td>
  <td style="text-align:center;font-size:14px">{_loc_total}</td>
  <td style="text-align:center">{sum(v["linux"] for v in _loc_summary.values())}</td>
  <td style="text-align:center">{sum(v["windows"] for v in _loc_summary.values())}</td>
  <td style="text-align:center">100%</td>
</tr>\n"""

_loc_sort_order = {"OSSCI": 0, "On-Prem": 1, "GitHub-hosted": 2}
_runner_data_sorted = sorted(
    RUNNER_DATA,
    key=lambda r: (_loc_sort_order.get(r[3].split(" ")[0] if r[3].split(" ")[0] in _loc_sort_order else r[3], 9), r[3], r[0]),
)
runner_rows_html = ""
for _ri, rec in enumerate(_runner_data_sorted, 1):
    label,plat,os_distro,location,phys,gpu_fam,isa,cnt,used,notes,cls = rec
    bg = plat_bg.get(cls,"#fff")
    loc_key = location if location in loc_badge else location.split(" ")[0]
    loc_color = loc_badge.get(loc_key,"#555")
    runner_rows_html += f"""<tr class="{cls}" style="background:{bg}">
      <td style="text-align:center;color:#888;font-size:12.5px">{_ri}</td>
      <td>{label}</td>
      <td>{plat}</td><td style="font-size:12px;color:#333">{os_distro}</td>
      <td><span style="background:{loc_color};color:#fff;padding:2px 6px;border-radius:4px;font-size:11.5px;white-space:nowrap">{location}</span></td>
      <td style="font-size:12.5px;color:#333">{phys}</td>
      <td>{gpu_fam}</td><td>{isa}</td>
      <td style="text-align:center">{cnt}</td>
      <td>{used}</td><td style="color:#555;font-size:12.5px">{notes}</td>
    </tr>\n"""

# ── Build InferenceMAX / InferenceX HTML sections ────────────────────────────
def _inf_bool(v) -> str:
    if v:
        return '<td class="bool-yes" style="vertical-align:middle;white-space:nowrap">Yes</td>'
    return '<td class="bool-no" style="vertical-align:middle;white-space:nowrap">—</td>'

def _inf_rows_html(data: list, row_cls: str) -> str:
    # Assign a stable alternating index to each distinct model_prefix (in order of first appearance)
    _prefix_order: list = []
    for rec in data:
        if rec[2] not in _prefix_order:
            _prefix_order.append(rec[2])
    # Distinct subtle tint per model group (up to 10 groups)
    _group_palette = [
        "#EDE7F6",  # pale violet
        "#E3F2FD",  # pale blue
        "#E8F5E9",  # pale green
        "#FFF8E1",  # pale amber
        "#FCE4EC",  # pale pink
        "#E0F7FA",  # pale cyan
        "#FBE9E7",  # pale deep-orange
        "#F1F8E9",  # pale light-green
        "#EEF2FF",  # pale indigo
        "#FFF3E0",  # pale orange
    ]
    _prefix_bg = {p: _group_palette[i % len(_group_palette)] for i, p in enumerate(_prefix_order)}
    rows = ""
    for rec in data:
        (name, model, model_prefix, runner, precision, framework,
         multinode, docker_image) = rec
        bg = _prefix_bg[model_prefix]
        rows += f"""<tr class="{row_cls}" style="background:{bg}">
          <td style="vertical-align:middle">{name}</td>
          <td style="font-size:12.5px;vertical-align:middle">{model}</td>
          <td style="vertical-align:middle"><b>{model_prefix}</b></td>
          <td style="vertical-align:middle"><span style="background:#EDE7F6;color:#4A148C;padding:2px 6px;border-radius:3px;font-size:12.5px">{runner}</span></td>
          <td style="text-align:center;vertical-align:middle;white-space:nowrap">{precision}</td>
          <td style="text-align:center;vertical-align:middle;white-space:nowrap">{framework}</td>
          {_inf_bool(multinode)}
          <td style="font-size:12.5px;color:#555;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle" title="{docker_image}">{docker_image if docker_image else "—"}</td>
        </tr>\n"""
    return rows

def _inf_runner_comment(gpu_type: str, nodes: list, cluster: str) -> str:
    """Build the per-row Comments cell for the Inference Runner Inventory table.
    InferenceMAX runners are NOT tracked by therock-runner-health.com (separate
    pool managed by the InferenceMAX_rocm repo / AMD-S Slurm cluster), so we
    emit a clear note plus any pool-specific quirks we can derive from names."""
    # Classify each node into amds (Slurm) vs amd (Docker) sub-pools
    n_amds   = sum(1 for n in nodes if "amds" in n)
    n_part   = sum(1 for n in nodes if re.search(r'_p\d+_g\d+', n))   # explicit partition slot
    sub = []
    if n_amds:
        sub.append(f'<span style="color:#4A148C"><b>{n_amds}</b> AMD-S Slurm</span> '
                   f'<span style="color:#888;font-size:10px">(amds_*)</span>')
    n_docker = max(0, len(nodes) - n_amds)
    if n_docker:
        sub.append(f'<span style="color:#1B5E20"><b>{n_docker}</b> Docker / self-hosted</span> '
                   f'<span style="color:#888;font-size:10px">(amd_*)</span>')
    if n_part:
        sub.append(f'<span style="color:#37474F">incl. {n_part} explicit partition slot(s) '
                   f'<span style="color:#888;font-size:10px">(p&lt;part&gt;_g&lt;gpu&gt;)</span></span>')
    # Pool-specific notes
    extras = []
    if "disagg" in gpu_type:
        extras.append("disaggregated serving (prefill+decode split)")
    if "spec" in gpu_type or "tw-sctrl" in gpu_type:
        extras.append("speculative-decoding / single-controller test pool")
    if cluster == "SLURM":
        tracking = ("Managed by AMD internal Slurm scheduler &mdash; live online/offline "
                    "<b>not</b> reported by <code>therock-runner-health.com</code>; "
                    "presumed available unless explicitly drained.")
    else:
        tracking = ("Self-hosted Docker pool managed by InferenceMAX_rocm &mdash; live online/offline "
                    "<b>not</b> reported by <code>therock-runner-health.com</code>.")
    parts = [f'<div style="font-size:11.5px">{tracking}</div>']
    if sub:
        parts.append(f'<div style="font-size:10.5px;margin-top:2px">Sub-pools: '
                     + " &nbsp;&middot;&nbsp; ".join(sub) + '</div>')
    if extras:
        parts.append(f'<div style="font-size:10.5px;color:#5D4037;margin-top:2px">'
                     f'Quirks: {"; ".join(extras)}</div>')
    return "".join(parts)

def _inf_runner_rows_html(runners_dict: dict, ecosystem: str, badge_color: str) -> str:
    rows = ""
    grand_total = 0
    slurm_total = 0
    docker_total = 0
    family_totals: dict = {}   # base family → node count
    for gpu_type, nodes in sorted(runners_dict.items()):
        cluster = "SLURM" if any("amds" in n or "slurm" in n.lower() or "dgxc" in n.lower() for n in nodes) else "Docker/Self-hosted"
        grand_total += len(nodes)
        if cluster == "SLURM":
            slurm_total += len(nodes)
        else:
            docker_total += len(nodes)
        # Group by base family: first token before "-" that starts with "mi"
        base = gpu_type.split("-")[0] if gpu_type.startswith("mi") else gpu_type
        family_totals[base] = family_totals.get(base, 0) + len(nodes)
        node_list = ", ".join(nodes)
        comment_cell = _inf_runner_comment(gpu_type, nodes, cluster)
        rows += f"""<tr>
          <td style="vertical-align:middle"><span style="background:{badge_color};color:#fff;padding:2px 6px;border-radius:3px;font-size:12.5px">{ecosystem}</span></td>
          <td style="vertical-align:middle"><b>{gpu_type}</b></td>
          <td style="font-size:12.5px;vertical-align:middle">{node_list}</td>
          <td style="text-align:center;font-weight:700;font-size:13px;vertical-align:middle">{len(nodes)}</td>
          <td style="font-size:12.5px;vertical-align:middle">{cluster}</td>
          <td style="font-size:12px;vertical-align:middle;color:#37474F;min-width:720px;word-wrap:break-word">{comment_cell}</td>
        </tr>\n"""
    if rows:
        family_parts = " &nbsp;&bull;&nbsp; ".join(
            f"{fam}: <b>{cnt}</b>" for fam, cnt in sorted(family_totals.items())
        )
        cluster_parts = " &nbsp;&bull;&nbsp; ".join(filter(None, [
            f"SLURM: <b>{slurm_total}</b>" if slurm_total else "",
            f"Docker/Self-hosted: <b>{docker_total}</b>" if docker_total else "",
        ]))
        rows += f"""<tr style="background:#37474F;color:#fff;font-weight:700">
          <td colspan="3" style="text-align:right;font-size:12px;padding-right:12px;vertical-align:middle">Total Nodes</td>
          <td style="text-align:center;font-size:14px;vertical-align:middle">{grand_total}</td>
          <td style="font-size:12.5px;opacity:0.9;vertical-align:middle;line-height:1.8">
            {family_parts}<br>
            <span style="font-weight:400;opacity:0.85">{cluster_parts}</span>
          </td>
          <td style="font-size:11px;color:#fff;opacity:0.85;vertical-align:middle">
            Live online/offline <b>not tracked</b> by <code>therock-runner-health.com</code> &mdash; this dashboard only covers TheRock GitHub Actions runners.
            InferenceMAX uses AMD-S Slurm + self-hosted Docker pools managed in <code>ROCm/InferenceMAX_rocm</code>.
          </td>
        </tr>\n"""
    return rows

_imax_rows  = _inf_rows_html(INFERENCEMAX_DATA, "imax-row") if INFERENCEMAX_DATA else "<tr><td colspan='8' style='color:#999;text-align:center'>No InferenceMAX data available — run fetch_rocm_data.py (needs an SSH key registered with GitHub, or a local InferenceMAX_rocm/ clone)</td></tr>"
_amd_run_rows = _inf_runner_rows_html(INFERENCE_RUNNERS.get("amd", {}), "AMD", "#CC0000")
_inf_run_rows_html = _amd_run_rows if _amd_run_rows else "<tr><td colspan='6' style='color:#999;text-align:center'>No AMD runner data available</td></tr>"

_imax_count = len(INFERENCEMAX_DATA)
_imax_gpus  = len({r[3] for r in INFERENCEMAX_DATA}) if INFERENCEMAX_DATA else 0
_imax_fws   = len({r[5] for r in INFERENCEMAX_DATA}) if INFERENCEMAX_DATA else 0
_imax_multi = sum(1 for r in INFERENCEMAX_DATA if r[6]) if INFERENCEMAX_DATA else 0

# Snapshot warning banners — shown in header when data came from the JSON
# fallback rather than a live source (GitHub API, local folder, or SSH).
_snapshot_notes_html = []
_footer_snapshot_notes = []

if _therock_snapshot_ts:
    _snapshot_notes_html.append(
        f'<p style="margin-top:6px;font-size:12.5px;color:#b26000;background:#FFF8E1;'
        f'border:1px solid #ffe082;border-radius:4px;padding:4px 10px;display:inline-block">'
        f'&#9888; TheRock CI data from cached snapshot ({_therock_snapshot_ts}) '
        f'— GitHub was unreachable or hit rate limits at report generation time.</p>'
    )
    _footer_snapshot_notes.append(f"TheRock CI: snapshot from {_therock_snapshot_ts}")

if _imax_snapshot_ts:
    _snapshot_notes_html.append(
        f'<p style="margin-top:6px;font-size:12.5px;color:#b26000;background:#FFF8E1;'
        f'border:1px solid #ffe082;border-radius:4px;padding:4px 10px;display:inline-block">'
        f'&#9888; InferenceMAX data from cached snapshot ({_imax_snapshot_ts}) '
        f'— all live sources unavailable at report generation time.</p>'
    )
    _footer_snapshot_notes.append(f"InferenceMAX: snapshot from {_imax_snapshot_ts}")

_imax_data_note = "\n  ".join(_snapshot_notes_html)
_imax_timestamp_note = (" · " + " · ".join(_footer_snapshot_notes)) if _footer_snapshot_notes else ""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROCm CI/CD Matrix v2 — TheRock Ecosystem</title>
<style>
:root{{
  --amd-red:#CC0000;--amd-dark:#1A1A1A;
  --blue-dark:#1F4E79;--blue-mid:#2E75B6;
  --pc-color:#1565C0;--po-color:#2E7D32;--ni-color:#E65100;
  --yes:#C6EFCE;--no:#FFCCCC;--part:#FFEB9C;
  --bg:#F5F7FA;--card:#fff;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:#222;font-size:13px}}
nav{{background:var(--amd-dark);display:flex;align-items:center;padding:10px 24px;position:sticky;top:0;z-index:100;gap:8px;flex-wrap:wrap}}
nav .logo{{color:var(--amd-red);font-weight:900;font-size:18px;letter-spacing:1px;margin-right:16px}}
nav a{{color:#ccc;text-decoration:none;padding:6px 14px;border-radius:4px;font-size:12px;transition:.2s}}
nav a:hover,nav a.active{{background:var(--amd-red);color:#fff}}
.nav-divider{{width:1px;background:#555;height:22px;margin:0 6px;flex-shrink:0}}
.nav-section-label{{font-size:11.5px;color:#888;letter-spacing:.5px;text-transform:uppercase;padding:0 4px;white-space:nowrap}}
.page-header{{background:linear-gradient(135deg,var(--amd-dark) 0%,#2c3e50 100%);color:#fff;padding:32px 36px 24px}}
.page-header h1{{font-size:24px;font-weight:700;margin-bottom:6px}}
.page-header p{{opacity:.75;font-size:13px}}
.summary{{display:flex;flex-wrap:wrap;gap:14px;padding:20px 36px}}
.card{{background:var(--card);border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);padding:16px 22px;min-width:160px;flex:1}}
.card h3{{font-size:12.5px;text-transform:uppercase;letter-spacing:.5px;color:#888;margin-bottom:6px}}
.card .num{{font-size:28px;font-weight:700;color:var(--blue-dark)}}
.card .sub{{font-size:12.5px;color:#aaa;margin-top:4px}}
.section{{padding:0 36px 32px}}
.section h2{{font-size:16px;font-weight:700;color:var(--blue-dark);border-left:4px solid var(--amd-red);padding-left:10px;margin:24px 0 12px}}
.tbl-wrap{{overflow-x:auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
table{{border-collapse:collapse;width:100%;background:#fff;font-size:13px}}
thead tr th{{background:#37474F;color:#fff;padding:9px 10px;text-align:left;white-space:nowrap;position:sticky;top:0;z-index:3}}
thead tr.tier1 th.th-pc{{background:var(--pc-color);border-left:3px solid #fff}}
thead tr.tier1 th.th-po{{background:var(--po-color);border-left:3px solid #fff}}
thead tr.tier1 th.th-ni{{background:var(--ni-color);border-left:3px solid #fff}}
thead tr.tier1 th.th-misc{{background:#558B2F;border-left:3px solid #fff}}
thead tr.tier1 th{{position:sticky;top:0;z-index:4}}
thead tr.tier2 th{{position:sticky;top:38px;z-index:3;font-size:12px;font-weight:500}}
thead tr.tier2 th.sub-pc{{background:#1976D2}}
thead tr.tier2 th.sub-po{{background:#388E3C}}
thead tr.tier2 th.sub-ni{{background:#F57C00}}
td{{padding:7px 10px;border-bottom:1px solid #eee;vertical-align:top;line-height:1.45}}
tbody tr:nth-child(even){{background:#f7faff}}
tbody tr:hover{{background:#eef4ff}}
.sep-pc{{border-left:3px solid var(--pc-color) !important}}
.sep-po{{border-left:3px solid var(--po-color) !important}}
.sep-ni{{border-left:3px solid var(--ni-color) !important}}
.sep-misc{{border-left:3px solid #558B2F !important}}
.yes{{background:var(--yes);font-weight:600;color:#276527;border-radius:3px;padding:1px 6px;display:inline-block}}
.no{{background:var(--no);font-weight:600;color:#922;border-radius:3px;padding:1px 6px;display:inline-block}}
.part{{background:var(--part);font-weight:600;color:#7a5c00;border-radius:3px;padding:1px 6px;display:inline-block}}
.dash{{color:#bbb}}
.filter-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;align-items:center}}
.filter-bar label{{font-size:12.5px;font-weight:600;color:#555}}
.filter-bar select,.filter-bar input{{border:1px solid #ccc;border-radius:4px;padding:5px 10px;font-size:12px}}
.filter-bar button{{background:var(--amd-red);color:#fff;border:none;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:12px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;align-items:center;font-size:12.5px}}
.legend-dot{{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:4px;vertical-align:middle}}
.callout{{background:#FFF3CD;border:1px solid #FFC107;border-radius:6px;padding:10px 16px;margin-bottom:14px;font-size:12px;color:#555}}
.tag{{display:inline-block;background:#E3F2FD;color:#1565C0;border-radius:3px;padding:1px 6px;margin:1px;font-size:12px}}
.tag-win{{background:#E8F5E9;color:#2E7D32}}
.tier-row td:first-child{{font-weight:700;color:var(--blue-dark);white-space:nowrap}}
.runner-linux td:first-child{{border-left:3px solid var(--blue-mid)}}
.runner-windows td:first-child{{border-left:3px solid #2E7D32}}
.runner-build td:first-child{{border-left:3px solid #F57C00}}
.fw-pytorch{{background:#EBF3FB !important}}
.fw-jax{{background:#E8F5E9 !important}}
footer{{background:var(--amd-dark);color:#888;text-align:center;padding:16px;font-size:12.5px;margin-top:32px}}
.section-imax{{}}
.hdr-imax{{background:#4A148C;color:#fff}}
.hdr-infr{{background:#4E342E;color:#fff}}
.imax-row{{background:#F8F0FC}}
.imax-row td{{vertical-align:middle}}
.bool-yes{{background:#C6EFCE;font-weight:700;text-align:center;vertical-align:middle}}
.bool-no{{color:#999;text-align:center;vertical-align:middle}}
.inf-source{{font-size:12.5px;color:#777;margin-bottom:10px}}
.ecosystem-banner{{display:flex;align-items:center;gap:14px;padding:12px 36px;margin:0}}
.ecosystem-banner.therock{{background:linear-gradient(90deg,#1A1A1A 0%,#2c3e50 100%);border-bottom:3px solid #CC0000}}
.ecosystem-banner.inferencemax{{background:linear-gradient(90deg,#1a0030 0%,#4A148C 100%);border-bottom:3px solid #CE93D8}}
.ecosystem-banner .eco-title{{color:#fff;font-size:14px;font-weight:700;letter-spacing:.5px}}
.ecosystem-banner .eco-subtitle{{color:rgba(255,255,255,.6);font-size:12.5px}}
.ecosystem-banner .eco-badge{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);color:#fff;border-radius:4px;padding:3px 10px;font-size:12.5px;white-space:nowrap}}
.fw-table td,.fw-table th{{border:1px solid #d0d7de}}
.fw-table thead tr th{{border-bottom:2px solid #b0bec5}}
.fw-server-table th{{background:#37474F;color:#fff;font-size:11.5px;white-space:nowrap}}
.fw-server-table td{{font-size:11.5px;vertical-align:middle}}
.fw-server-table .fw-pytorch td{{background:#EBF3FB}}
.fw-server-table .fw-jax td{{background:#E8F5E9}}
</style>
</head>
<body>
<nav>
  <span class="logo">AMD ROCm</span>
  <span class="nav-section-label">TheRock CI</span>
  <a href="#overview" class="active">Overview</a>
  <a href="#tiers">CI Tiers</a>
  <a href="#components">Components</a>
  <a href="#frameworks">Frameworks</a>
  <a href="#wheels">Wheels</a>
  <a href="#server-counts">Server Counts</a>
  <a href="#runners">Runners</a>
  <span class="nav-divider"></span>
  <span class="nav-section-label" style="color:#CE93D8">InferenceMAX CI</span>
  <a href="#inferencemax" style="color:#CE93D8">Benchmarks</a>
  <a href="#inference-runner-inventory" style="color:#CE93D8">Inf Runners</a>
  <span class="nav-divider"></span>
  <a href="#data-sources">Data Sources</a>
  <a href="#appendix-gfx">Appendix</a>
  <a href="https://therock-hud-dev.amd.com/" target="_blank" rel="noopener" style="margin-left:auto;background:#CC0000;color:#fff;border-radius:4px;padding:3px 12px;font-weight:600;text-decoration:none">&#128202; TheRock HUD</a>
</nav>
<div class="page-header">
  <h1>ROCm CI/CD Matrix &mdash; TheRock &amp; InferenceMAX Ecosystems</h1>
  <p>Two distinct CI ecosystems in one view: <b>TheRock CI</b> (component builds, frameworks, runners) and <b>InferenceMAX CI</b> (AMD GPU inference benchmarking).</p>
  <p style="margin-top:6px;opacity:.6;font-size:12px">&#128337; Last updated: {_TIMESTAMP}</p>
  {_imax_data_note}
</div>
<div class="ecosystem-banner therock">
  <span class="eco-title">&#9654; TheRock CI</span>
  <span class="eco-subtitle">ROCm/TheRock &bull; ROCm/rocm-libraries &bull; ROCm/rocm-systems &bull; ROCm/pytorch &bull; ROCm/rocm-jax</span>
  <span class="eco-badge">Components &bull; Frameworks &bull; Runners &bull; Wheel Artifacts</span>
</div>

<div class="summary">
  <div class="card"><h3>Total Rows</h3><div class="num">{total}</div><div class="sub">{non_fw} ROCm components + {fw_rows} Framework version slots</div></div>
  <div class="card"><h3>CI-Enabled (non-FW)</h3><div class="num">{ci_enabled}</div><div class="sub">Yes or Partial coverage</div></div>
  <div class="card"><h3>GPU Families</h3><div class="num">13</div><div class="sub">Linux; 4 Windows; gfx900–gfx120X</div></div>
  <div class="card"><h3>Test Runners</h3><div class="num">23</div><div class="sub">Linux + Windows + build pools</div></div>
  <div class="card"><h3>PyTorch Versions</h3><div class="num">5</div><div class="sub">2.8, 2.9, 2.10, 2.11, nightly</div></div>
  <div class="card"><h3>JAX Versions</h3><div class="num">4</div><div class="sub">0.8.0, 0.8.2, 0.9.0, 0.9.1</div></div>
  <div class="card"><h3>CI Tiers</h3><div class="num">5</div><div class="sub">PR &rarr; Postsubmit &rarr; Nightly &rarr; ASAN/TSAN &rarr; Release</div></div>
  <div class="card"><h3>Direct Submodules</h3><div class="num">12</div><div class="sub">2 super-repos + 10 direct deps</div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     CI TIER OVERVIEW
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="tiers">
<h2>CI Tier Overview</h2>
<div class="tbl-wrap"><table>
<thead><tr>
  <th>Tier</th><th>Trigger</th><th>Schedule</th><th>Test Type</th>
  <th>Linux GPU Families</th><th>Windows GPU Families</th>
  <th>Frameworks Built</th><th>Linux Distro</th><th>Windows Distro</th>
</tr></thead>
<tbody>
<tr class="tier-row">
  <td>Pre-commit (PR)</td>
  <td><code>ci.yml</code><br>pull_request: opened / synchronized / labeled<br><small>(no <code>push:</code> trigger &mdash; PR only)</small></td>
  <td>Every PR</td>
  <td>
    <b>standard</b> = full unit suite<br>
    <small>&#x2192; rocm-libraries / rocm-systems component PRs</small><br><br>
    <b>quick</b> = smoke/sanity only<br>
    <small>&#x2192; TheRock infra/build PRs &bull; default when no <code>test:*</code> label</small>
  </td>
  <td>
    <b>Default (no label):</b> <span class="tag">gfx94X-dcgpu</span> <span class="tag">gfx110X</span><br>
    &nbsp;&bull; <span class="tag">gfx94X-dcgpu</span> <b>Build + Test</b> (MI300X/MI325X)<br>
    &nbsp;&bull; <span class="tag">gfx110X</span> <b>Build-only</b> (<code>nightly_check_only_for_family</code>)<br>
    <b>Opt-in via labels (<code>gfx1151-linux</code>, <code>gfx120X-linux</code>):</b><br>
    &nbsp;&bull; <span class="tag">gfx1151</span> <span class="tag">gfx120X</span> <b>Build-only</b> (<code>nightly_check_only</code>)
  </td>
  <td>
    <b>Default (no label):</b> <span class="tag tag-win">gfx110X</span> <b>Build + Test</b> (no <code>nightly_check_only</code> on Windows)<br>
    <b>Opt-in via labels:</b><br>
    &nbsp;&bull; <span class="tag tag-win">gfx1151</span> <b>Build-only</b> (<code>nightly_check_only</code>)<br>
    &nbsp;&bull; <span class="tag tag-win">gfx120X</span> <b>Build-only</b> (<code>nightly_check_only</code>)
  </td>
  <td>PyTorch torch package only (no wheel upload)<br><b>No JAX in PR CI</b></td>
  <td>Ubuntu 22.04 LTS<br><small>(azure-linux-scale-rocm)</small></td>
  <td>Windows Server 2022<br><small>(azure-windows-scale-rocm)</small></td>
</tr>
<tr class="tier-row" style="background:#f7faff">
  <td>Post-commit</td>
  <td><code>multi_arch_ci.yml</code><br>push to <code>main</code> / <code>multi_arch/**</code> / <code>release/therock-*</code><br><small>Fires on every merged commit (incl. submodule-bump merges via <code>bump_submodules.yml</code> which runs every 12 hrs)</small></td>
  <td>Every merged commit</td>
  <td><b>quick</b> = smoke/sanity only</td>
  <td>
    <b>Build + Test</b>:<br>
    &nbsp;&bull; <span class="tag">gfx94X-dcgpu</span> (MI300X/MI325X)<br>
    &nbsp;&bull; <span class="tag">gfx950-dcgpu</span> (MI355X &mdash; postsubmit matrix only)<br>
    <b>Build-only</b> (<code>nightly_check_only_for_family</code>):<br>
    &nbsp;&bull; <span class="tag">gfx110X</span> <span class="tag">gfx1151</span> <span class="tag">gfx120X</span>
  </td>
  <td>
    <b>Build + Test</b>: <span class="tag tag-win">gfx110X</span><br>
    <b>Build-only</b> (<code>nightly_check_only</code>):<br>
    &nbsp;&bull; <span class="tag tag-win">gfx1151</span> <span class="tag tag-win">gfx120X</span>
  </td>
  <td>PyTorch torch package only<br>ROCm Python wheels (Ubuntu 24.04 + UBI10 smoke)<br><b>No JAX</b></td>
  <td>Ubuntu 22.04 LTS</td>
  <td>Windows Server 2022</td>
</tr>
<tr class="tier-row">
  <td>CI Nightly</td>
  <td><code>ci_nightly.yml</code> + <code>ci_nightly_pytorch_full_test.yml</code><br><small>(schedule + workflow_dispatch)</small></td>
  <td>02:00 UTC ({_utc_to_pt(2)}) daily (ROCm) &mdash; <code>0 02 * * *</code><br>12:00 UTC ({_utc_to_pt(12)}) daily (PyTorch full) &mdash; <code>0 12 * * *</code></td>
  <td><b>comprehensive</b> = full + integration (ROCm)<br><b>full</b> = complete suite (PyTorch)</td>
  <td>
    <b>Build + Test</b> (HW runners available):<br>
    <span class="tag">gfx94X</span> <span class="tag">gfx950</span> <span class="tag">gfx90a</span>
    <span class="tag">gfx103X</span> <span class="tag">gfx110X</span> <span class="tag">gfx1150</span>
    <span class="tag">gfx1151</span> <span class="tag">gfx1153</span> <span class="tag">gfx120X</span><br>
    <b>Build-only</b> (no HW runners &mdash; <code>test-runs-on: ""</code> in matrix):<br>
    <small><i>gfx900, gfx906, gfx908, gfx101X, gfx1152</i></small>
  </td>
  <td>
    <b>Build + Test</b>:<br>
    <span class="tag tag-win">gfx110X</span> <span class="tag tag-win">gfx103X</span>
    <span class="tag tag-win">gfx1151</span> <span class="tag tag-win">gfx120X</span>
  </td>
  <td>PyTorch: all 5 versions &times; 5 Python vers &times; all families<br>JAX: all 4 versions &times; 4 Python vers<br>Triton + Apex (Linux)</td>
  <td>Ubuntu 22.04 LTS</td>
  <td>Windows Server 2022</td>
</tr>
<tr class="tier-row" style="background:#f7faff">
  <td>ASAN / TSAN</td>
  <td>
    <b>ASAN</b>: <code>ci_asan.yml</code> &mdash; <b>workflow_dispatch only</b><br>
    <small><i>(legacy workflow; no schedule. Header notes "will be removed after legacy TheRock CI is retired")</i></small><br>
    <b>TSAN</b>: <code>ci_tsan.yml</code> &mdash; schedule + workflow_dispatch
  </td>
  <td>
    <b>ASAN</b>: on-demand only<br>
    <b>TSAN</b>: 02:00 UTC ({_utc_to_pt(2)}) daily &mdash; <code>0 02 * * *</code>
  </td>
  <td><b>quick</b> = smoke/sanity only<br><small>Same suite as Post-commit but with sanitizer build (asan / tsan variants of <code>ci_linux.yml</code>)</small></td>
  <td>
    <b>Build + Test</b>:<br>
    <span class="tag">gfx94X-dcgpu</span> (presubmit matrix; <code>build_variants: ["release", "asan", "tsan"]</code>)<br>
    <span class="tag">gfx950-dcgpu</span> (postsubmit matrix; <code>build_variants: ["release", "asan", "tsan"]</code>)<br>
    <small><i>ASAN tests use <code>rocm-asan-mi325-sandbox</code> via <code>test-runs-on-sandbox</code></i></small>
  </td>
  <td>&mdash;</td>
  <td>None (sanitizer build validation only)</td>
  <td>Ubuntu 22.04 LTS<br><small>(rocm-asan-mi325-sandbox + ramdisk build pool)</small></td>
  <td>&mdash;</td>
</tr>
<tr class="tier-row">
  <td>Release</td>
  <td>
    <b>Scheduled (nightly portable releases)</b>:<br>
    &nbsp;&bull; <code>release_portable_linux_packages.yml</code><br>
    &nbsp;&bull; <code>release_windows_packages.yml</code><br>
    <b>On-demand</b>: <code>multi_arch_release.yml</code>, <code>release_native_*</code>, JAX/PyTorch wheel releases (rockrel or manual)
  </td>
  <td>
    02:00 UTC ({_utc_to_pt(2)}) daily for portable packages &mdash; <code>0 02 * * *</code><br>
    On-demand for dev / prerelease / native / wheels
  </td>
  <td>quick / none<br><small>(tests not yet fully wired in <code>multi_arch_release</code>; <code>bypass_tests_for_releases: True</code> on most opt-in families)</small></td>
  <td>
    <b>Build + Test</b> (quick):<br>
    <span class="tag">gfx94X</span> <span class="tag">gfx950</span> <span class="tag">gfx90a</span>
    <span class="tag">gfx103X</span> <span class="tag">gfx110X</span> <span class="tag">gfx1150</span>
    <span class="tag">gfx1151</span> <span class="tag">gfx1153</span> <span class="tag">gfx120X</span><br>
    <b>Build-only</b>:<br>
    <small><i>gfx900, gfx906, gfx908, gfx101X, gfx1152 (no HW runners)</i></small>
  </td>
  <td>
    <b>Build + Test</b> (quick):<br>
    <span class="tag tag-win">gfx110X</span> <span class="tag tag-win">gfx103X</span>
    <span class="tag tag-win">gfx1151</span> <span class="tag tag-win">gfx120X</span>
  </td>
  <td>PyTorch all 5 versions &times; all Pythons<br>JAX all 4 versions<br>ROCm tarballs to S3</td>
  <td>Ubuntu 22.04 LTS + RHEL 8.8/9.5 + SLES 15.6</td>
  <td>Windows Server 2022</td>
</tr>
</tbody>
</table></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     COMPONENT CI MATRIX
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="components">
<h2>Component CI Matrix <a href="https://therock-hud-dev.amd.com/" target="_blank" rel="noopener" style="font-size:13px;font-weight:400;vertical-align:middle;margin-left:10px;color:#CC0000;text-decoration:none;border:1px solid #CC0000;padding:2px 8px;border-radius:4px">&#128202; TheRock HUD — Live Build Status</a></h2>
<div class="filter-bar">
  <label>Category:</label>
  <select id="catFilter" onchange="filterTable()">
    <option value="">All</option>
    <option>Libraries</option><option>Tools</option>
    <option>Compilers</option><option>Runtime</option>
    <option>iree-libs</option><option>Sysdeps</option><option>Frameworks</option>
  </select>
  <label>CI Status:</label>
  <select id="ciFilter" onchange="filterTable()">
    <option value="">All</option>
    <option>Yes</option><option>Partial</option><option>No</option>
  </select>
  <input id="searchInput" type="text" placeholder="Search component..." oninput="filterTable()" style="min-width:180px">
  <button onclick="resetFilter()">Reset</button>
</div>
<div class="legend">
  <span><span class="legend-dot" style="background:#1565C0"></span>Pre-commit (PR)</span>
  <span><span class="legend-dot" style="background:#2E7D32"></span>Post-commit (Sub Bump)</span>
  <span><span class="legend-dot" style="background:#E65100"></span>CI Nightly</span>
  <span style="margin-left:12px;color:#888">Within each tier: Linux gfx &rarr; Linux Runners &rarr; Windows gfx &rarr; Windows Runners &rarr; Test Type</span>
</div>

<div class="tbl-wrap" style="max-height:80vh;overflow-y:auto"><table id="compTable">
<thead>
<tr class="tier1">
  <th rowspan="2" style="background:#37474F">Category</th>
  <th rowspan="2" style="background:#37474F">Sub-Category</th>
  <th rowspan="2" style="background:#37474F">Component</th>
  <th rowspan="2" style="background:#37474F">Super Repo</th>
  <th rowspan="2" style="background:#37474F">CI Enabled</th>
  <th colspan="5" class="th-pc" style="text-align:center">&#128196; Pre-commit (PR)</th>
  <th colspan="5" class="th-po" style="text-align:center">&#10003; Post-commit (Sub Bump)</th>
  <th colspan="5" class="th-ni" style="text-align:center">&#127769; CI Nightly</th>
  <th colspan="2" class="th-misc" style="text-align:center">Comments</th>
</tr>
<tr class="tier2">
  <th class="sub-pc">Linux gfx</th>
  <th class="sub-pc">Linux Runners</th>
  <th class="sub-pc">Windows gfx</th>
  <th class="sub-pc">Windows Runners</th>
  <th class="sub-pc">Test Type</th>
  <th class="sub-po">Linux gfx</th>
  <th class="sub-po">Linux Runners</th>
  <th class="sub-po">Windows gfx</th>
  <th class="sub-po">Windows Runners</th>
  <th class="sub-po">Test Type</th>
  <th class="sub-ni">Linux gfx</th>
  <th class="sub-ni">Linux Runners</th>
  <th class="sub-ni">Windows gfx</th>
  <th class="sub-ni">Windows Runners</th>
  <th class="sub-ni">Test Type</th>
  <th style="background:#558B2F">Platform</th>
  <th style="background:#558B2F">Notes</th>
</tr>
</thead>
<tbody id="compTbody">
{rows_html}
</tbody>
</table></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     FRAMEWORK DETAIL
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="frameworks">
<h2>Framework Build &amp; Test Detail</h2>
<div class="tbl-wrap"><table class="fw-table">
<thead><tr>
  <th>Framework</th><th>Version</th><th>Python Vers</th>
  <th>Distro</th>
  <th>Linux Packages</th><th>Windows Packages</th>
  <th>Branch / Ref</th>
  <th>Nightly GPU</th>
  <th>CI Test Suite</th><th>Nightly Full Test</th>
  <th>Build Runner</th><th>Test Runner</th>
  <th>Notes</th>
</tr></thead>
<tbody>
<tr class="fw-pytorch">
  <td rowspan="5" style="font-weight:700;color:#1F4E79;vertical-align:middle">PyTorch</td>
  <td>2.8</td><td>3.10, 3.11, 3.12, 3.13</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>torch, torchaudio, torchvision, triton, apex</td><td>&mdash;</td>
  <td>ROCm/pytorch release/2.8</td>
  <td>gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx120X &mdash; <b>Build + Test</b><br>
    <small>Build-only: gfx900, gfx906, gfx908, gfx101X; gfx1153 excluded</small></td>
  <td>sanity + smoke (quick)</td>
  <td>11 parallel jobs: Default suite (6) + Distributed training (3, 8-GPU runner) + Compiler/Inductor (2)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td><small>linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br><i>gfx1153: excluded entirely</i></small></td>
  <td>py3.14 excluded; aotriton incompatible with gfx90X/101X/103X/1152/1153</td>
</tr>
<tr class="fw-pytorch">
  <td>2.9</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex</td><td>torch, torchaudio, torchvision</td>
  <td>ROCm/pytorch release/2.9</td>
  <td>gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build + Test</b> (Linux)<br>
    gfx1151, gfx110X, gfx103X, gfx120X &mdash; <b>Build + Test</b> (Windows)<br>
    <small>Build-only: gfx900/906/908/101X</small></td>
  <td>sanity + smoke (quick)</td>
  <td>11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
  <td>gfx1153 excluded Linux-only</td>
</tr>
<tr class="fw-pytorch">
  <td><b>2.10</b> (default CI pin)</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex</td><td>torch, torchaudio, torchvision</td>
  <td>ROCm/pytorch release/2.10</td>
  <td>gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build + Test</b> (Linux)<br>
    gfx1151, gfx110X, gfx103X, gfx120X &mdash; <b>Build + Test</b> (Windows)<br>
    <small>Build-only: gfx900/906/908/101X</small></td>
  <td>sanity + smoke (quick)</td>
  <td>11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
  <td>Default CI pin</td>
</tr>
<tr class="fw-pytorch">
  <td>2.11</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex</td><td>torch, torchaudio, torchvision</td>
  <td>ROCm/pytorch release/2.11</td>
  <td>gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build + Test</b> (Linux)<br>
    gfx1151, gfx110X, gfx103X, gfx120X &mdash; <b>Build + Test</b> (Windows)<br>
    <small>Build-only: gfx900/906/908/101X</small></td>
  <td>sanity + smoke (quick)</td>
  <td>11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
  <td></td>
</tr>
<tr class="fw-pytorch">
  <td>nightly</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex</td><td>torch, torchaudio, torchvision</td>
  <td>pytorch/pytorch main</td>
  <td>gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build + Test</b> (Linux)<br>
    gfx1151, gfx110X, gfx103X, gfx120X &mdash; <b>Build + Test</b> (Windows)<br>
    <small>Build-only: gfx900/906/908/101X</small></td>
  <td>sanity + smoke (quick)</td>
  <td>11 parallel jobs: Default suite (6) + Distributed training (3) + Compiler/Inductor (2)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-gfx950-1gpu-ccs-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
  <td>Triton pin from pytorch/.ci/docker/ci_commit_pins/triton.txt</td>
</tr>
<tr class="fw-jax">
  <td rowspan="4" style="font-weight:700;color:#2E7D32;vertical-align:middle">JAX</td>
  <td>0.8.0</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jaxlib + jax_rocm7_plugin + jax_rocm7_pjrt</td><td>&mdash;</td>
  <td>ROCm/rocm-jax rocm-jaxlib-v0.8.0</td>
  <td>gfx94X &mdash; <b>Build + Test</b><br>
    gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build-only</b> (no GPU test)<br>
    <small>Build-only (no HW runners): gfx900, gfx906, gfx908, gfx101X</small></td>
  <td>&mdash;</td>
  <td>pytest: multi_device_test, core_test, util_test, scipy_stats_test (JAX_PLATFORMS=rocm)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td><small>linux-gfx942-1gpu-ossci-rocm<br>(gfx94X only &mdash; other families built but not GPU-tested)</small></td>
  <td>Full jaxlib built from source</td>
</tr>
<tr class="fw-jax">
  <td>0.8.2</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jaxlib + jax_rocm7_plugin + jax_rocm7_pjrt</td><td>&mdash;</td>
  <td>ROCm/rocm-jax rocm-jaxlib-v0.8.2</td>
  <td>gfx94X &mdash; <b>Build + Test</b><br>
    gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build-only</b> (no GPU test)<br>
    <small>Build-only (no HW runners): gfx900, gfx906, gfx908, gfx101X</small></td>
  <td>&mdash;</td>
  <td>pytest: multi_device_test, core_test, util_test, scipy_stats_test</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td><small>linux-gfx942-1gpu-ossci-rocm<br>(gfx94X only &mdash; other families built but not GPU-tested)</small></td>
  <td>Full jaxlib from source</td>
</tr>
<tr class="fw-jax">
  <td>0.9.0</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jaxlib + jax_rocm7_plugin + jax_rocm7_pjrt</td><td>&mdash;</td>
  <td>ROCm/rocm-jax rocm-jaxlib-v0.9.0</td>
  <td>gfx94X &mdash; <b>Build + Test</b><br>
    gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build-only</b> (no GPU test)<br>
    <small>Build-only (no HW runners): gfx900, gfx906, gfx908, gfx101X</small></td>
  <td>&mdash;</td>
  <td>pytest: multi_device_test, core_test, util_test, scipy_stats_test</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td><small>linux-gfx942-1gpu-ossci-rocm<br>(gfx94X only &mdash; other families built but not GPU-tested)</small></td>
  <td>Full jaxlib from source</td>
</tr>
<tr class="fw-jax">
  <td>0.9.1</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jax_rocm7_plugin + jax_rocm7_pjrt</td><td>&mdash;</td>
  <td>ROCm/rocm-jax rocm-jaxlib-v0.9.1</td>
  <td>gfx94X &mdash; <b>Build + Test</b><br>
    gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X &mdash; <b>Build-only</b> (no GPU test)<br>
    <small>Build-only (no HW runners): gfx900, gfx906, gfx908, gfx101X</small></td>
  <td>&mdash;</td>
  <td>pytest: multi_device_test, core_test, util_test, scipy_stats_test</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td><small>linux-gfx942-1gpu-ossci-rocm<br>(gfx94X only &mdash; other families built but not GPU-tested)</small></td>
  <td>jaxlib from upstream PyPI; only plugin+pjrt built from source</td>
</tr>
</tbody></table></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     WHEEL ARTIFACT PUBLISHING
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="wheels">
<h2>Wheel Artifact Publishing</h2>
<div class="tbl-wrap"><table class="fw-table">
<thead><tr>
  <th>Framework</th><th>Version</th><th>Python Vers</th>
  <th>Distro</th>
  <th>Wheel Packages</th>
  <th>GPU Families &mdash; Wheel Published</th>
  <th>GPU Families &mdash; Build-only (no upload)</th>
  <th>Build Trigger</th>
  <th>Build Runner</th>
  <th>Smoke Test Runner</th>
  <th>Notes</th>
</tr></thead>
<tbody>
<tr class="fw-pytorch">
  <td rowspan="5" style="font-weight:700;color:#1F4E79;vertical-align:middle">PyTorch</td>
  <td>2.8</td><td>3.10, 3.11, 3.12, 3.13</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>torch, torchaudio, torchvision, triton, apex (Linux only)</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>CI pipeline (post-merge push to release/2.8)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td><small>ubuntu-24.04 (GitHub-hosted)<br>UBI10 container smoke install</small></td>
  <td>py3.14 excluded; gfx1153 excluded entirely; Windows: no wheel upload for 2.8</td>
</tr>
<tr class="fw-pytorch">
  <td>2.9</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex (Linux); torch, torchaudio, torchvision (Windows)</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X<br>Windows: gfx1151, gfx110X, gfx103X, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>CI pipeline (post-merge push to release/2.9)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>ubuntu-24.04 (GitHub-hosted)<br>UBI10 container smoke install</small></td>
  <td></td>
</tr>
<tr class="fw-pytorch">
  <td><b>2.10</b> (default CI pin)</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex (Linux); torch, torchaudio, torchvision (Windows)</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X<br>Windows: gfx1151, gfx110X, gfx103X, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>CI pipeline (post-merge push to release/2.10) + 02:00 UTC ({_utc_to_pt(2)}) daily (ci_nightly.yml)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>ubuntu-24.04 (GitHub-hosted)<br>UBI10 container smoke install</small></td>
  <td>Default CI pin branch</td>
</tr>
<tr class="fw-pytorch">
  <td>2.11</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex (Linux); torch, torchaudio, torchvision (Windows)</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X<br>Windows: gfx1151, gfx110X, gfx103X, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>CI pipeline (post-merge push to release/2.11)</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>ubuntu-24.04 (GitHub-hosted)<br>UBI10 container smoke install</small></td>
  <td></td>
</tr>
<tr class="fw-pytorch">
  <td>nightly</td><td>3.10, 3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS<br>Windows: Windows 11</td>
  <td>torch, torchaudio, torchvision, triton, apex (Linux); torch, torchaudio, torchvision (Windows)</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X<br>Windows: gfx1151, gfx110X, gfx103X, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>02:00 UTC ({_utc_to_pt(2)}) daily (ci_nightly.yml) + on push to pytorch/pytorch main</td>
  <td><code>azure-linux-scale-rocm</code> (Linux)<br><code>azure-windows-scale-rocm</code> (Windows)</td>
  <td><small>ubuntu-24.04 (GitHub-hosted)<br>UBI10 container smoke install</small></td>
  <td>Triton pin from pytorch/.ci/docker/ci_commit_pins/triton.txt</td>
</tr>
<tr class="fw-jax">
  <td rowspan="4" style="font-weight:700;color:#2E7D32;vertical-align:middle">JAX</td>
  <td>0.8.0</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jaxlib, jax_rocm7_plugin, jax_rocm7_pjrt</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>Release pipeline (externally triggered)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td>&mdash;</td>
  <td>Full jaxlib built from source</td>
</tr>
<tr class="fw-jax">
  <td>0.8.2</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jaxlib, jax_rocm7_plugin, jax_rocm7_pjrt</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>Release pipeline (externally triggered)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td>&mdash;</td>
  <td>Full jaxlib built from source</td>
</tr>
<tr class="fw-jax">
  <td>0.9.0</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jaxlib, jax_rocm7_plugin, jax_rocm7_pjrt</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>Release pipeline (externally triggered)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td>&mdash;</td>
  <td>Full jaxlib built from source</td>
</tr>
<tr class="fw-jax">
  <td>0.9.1</td><td>3.11, 3.12, 3.13, 3.14</td>
  <td>Linux: Ubuntu 22.04 LTS</td>
  <td>jax_rocm7_plugin, jax_rocm7_pjrt (jaxlib from PyPI)</td>
  <td>Linux: gfx94X, gfx950, gfx90a, gfx103X, gfx110X, gfx1150, gfx1151, gfx1153, gfx120X</td>
  <td>Linux: gfx900, gfx906, gfx908, gfx101X</td>
  <td>Release pipeline (externally triggered)</td>
  <td><code>azure-linux-scale-rocm</code></td>
  <td>&mdash;</td>
  <td>jaxlib from upstream PyPI; only plugin+pjrt built from source</td>
</tr>
</tbody></table></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     SERVER COUNTS — consolidated section with 3 sub-tables
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="server-counts">
<h2>&#128202; Server Counts <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="font-size:13px;font-weight:400;vertical-align:middle;margin-left:10px;color:#1565C0;text-decoration:none;border:1px solid #1565C0;padding:2px 8px;border-radius:4px">&#128279; Runner Health Dashboard</a></h2>
<p style="margin:0 0 12px 0;font-size:12.5px;color:#555;background:#F5F5F5;padding:10px 14px;border-radius:4px;border-left:3px solid #1565C0">
  Three perspectives on the runner fleet, all in one place:
  <b>(1)</b> per CI tier (PR / postsubmit / nightly),
  <b>(2)</b> per framework (PyTorch + JAX),
  <b>(3)</b> per inference benchmark pool (InferenceMAX AMD).
  Live per-machine status &mdash; including online / offline and queue health &mdash; is published at
  <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="color:#1565C0;font-weight:600">therock-runner-health.com</a>.
</p>
{_live_status_banner}

<!-- ── 1/3: COMPONENT CI MATRIX SERVER COUNTS BY TIER ───────────────── -->
<h3 id="server-counts-component" style="margin:24px 0 8px 0;font-size:14px;color:#37474F;font-weight:700;border-bottom:2px solid #37474F;padding-bottom:4px">
  1 &mdash; Component CI Matrix &mdash; Unique Server Counts by Tier
  <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="font-size:11.5px;font-weight:400;margin-left:8px;color:#1565C0;text-decoration:none;border:1px solid #1565C0;padding:1px 6px;border-radius:3px">&#128279; Runner Health</a>
</h3>
<div class="tbl-wrap" style="margin-bottom:6px"><table class="fw-table fw-server-table">
<thead><tr>
  <th>CI Tier</th>
  <th>Pool Type</th>
  <th style="text-align:center">Count</th>
  <th>Azure Build Pool (no GPU)</th>
  <th>Physical GPU Machines</th>
  <th>Runner Labels &amp; Counts</th>
  <th style="width:800px;min-width:720px">Comments<br><span style="font-weight:400;font-size:10.5px;color:#FFE082">online/offline by gfx &middot; DO-NOT-ENABLE flags</span></th>
</tr></thead>
<tbody>

<!-- Shared Azure Build Pool row -->
<tr style="background:#FFF9E6">
  <td rowspan="2" style="font-weight:700;color:#555;vertical-align:middle;text-align:center;border-left:4px solid #F9A825">All Tiers</td>
  <td>Azure Build Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">cloud VMs, no GPU &mdash; compile &amp; package only</span></td>
  <td style="text-align:center"><b>{_build_vms}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">VMs (snapshot)</span></td>
  <td style="text-align:center"><b>{_runner_counts.get('azure-linux-scale-rocm',0)}</b> Linux VMs<br>+<br><b>{_runner_counts.get('azure-windows-scale-rocm',0)}</b> Windows VMs</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td><code>azure-linux-scale-rocm</code> = <b>{_runner_counts.get('azure-linux-scale-rocm',0)}</b> &bull; <code>azure-windows-scale-rocm</code> = <b>{_runner_counts.get('azure-windows-scale-rocm',0)}</b></td>
  <td style="font-size:12.5px;color:#555">Shared across all tiers; elastic &mdash; can scale beyond snapshot count under queue pressure</td>
</tr>
<tr style="font-weight:700;background:#F5F0D8">
  <td>Build Subtotal</td>
  <td style="text-align:center;font-size:13px"><b>{_build_vms}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} VMs total</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_runner_counts.get('azure-linux-scale-rocm',0)} Linux + {_runner_counts.get('azure-windows-scale-rocm',0)} Windows Azure VMs &mdash; no GPU hardware involved</td>
</tr>

<!-- Pre-commit rows -->
<tr style="background:#EBF3FB">
  <td rowspan="2" style="font-weight:700;color:#1565C0;vertical-align:middle;text-align:center;border-left:4px solid #1565C0">&#128196; Pre-commit<br>(PR)</td>
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">{len(_PC_GPU_LABELS)} physical runner labels</span></td>
  <td style="text-align:center"><b>{_pc_gpu_nodes_full}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">physical</span></td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_pc_gpu_nodes_full}</b> unique nodes</td>
  <td>{_pc_runner_grouped_html}</td>
  <td style="font-size:12px;color:#555;min-width:720px;word-wrap:break-word"><div style="font-size:11.5px">gfx94X: full Build + Test pool (1+8 GPU + ASAN sandbox + alt pools) &bull; gfx1151 Win: Build-only (nightly_check_only_for_family)</div>{_pc_breakdown_html}</td>
</tr>
<tr style="font-weight:700;background:#D0E8F8">
  <td>Pre-commit Subtotal</td>
  <td style="text-align:center;font-size:13px;color:#1565C0"><b>{_pc_gpu_nodes_full}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} shared build VMs</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_pc_gpu_nodes_full} physical GPU</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_build_vms} Azure build VMs + <b>{_pc_gpu_nodes_full}</b> physical GPU machines = <b>{_build_vms + _pc_gpu_nodes_full}</b> total</td>
</tr>

<!-- Post-commit rows -->
<tr style="background:#EBF5EB">
  <td rowspan="2" style="font-weight:700;color:#2E7D32;vertical-align:middle;text-align:center;border-left:4px solid #2E7D32">&#10003; Post-commit<br>(Sub Bump)</td>
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">{len(_PO_GPU_LABELS)} physical runner labels</span></td>
  <td style="text-align:center"><b>{_po_gpu_nodes_full}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">physical</span></td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_po_gpu_nodes_full}</b> unique nodes</td>
  <td>{_po_runner_grouped_html}</td>
  <td style="font-size:12px;color:#555;min-width:720px;word-wrap:break-word"><div style="font-size:11.5px">Adds gfx950 (MI355X) 1-GPU + 8-GPU lanes vs Pre-commit; gfx1151 Win remains Build-only</div>{_po_breakdown_html}</td>
</tr>
<tr style="font-weight:700;background:#C8E6C9">
  <td>Post-commit Subtotal</td>
  <td style="text-align:center;font-size:13px;color:#2E7D32"><b>{_po_gpu_nodes_full}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} shared build VMs</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_po_gpu_nodes_full} physical GPU</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_build_vms} Azure build VMs + <b>{_po_gpu_nodes_full}</b> physical GPU machines = <b>{_build_vms + _po_gpu_nodes_full}</b> total</td>
</tr>

<!-- Nightly rows -->
<tr style="background:#FFF3E0">
  <td rowspan="2" style="font-weight:700;color:#E65100;vertical-align:middle;text-align:center;border-left:4px solid #E65100">&#127769; CI Nightly</td>
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">{len(_NI_GPU_LABELS)} physical runner labels</span></td>
  <td style="text-align:center"><b>{_ni_gpu_nodes_full}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">physical</span></td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_ni_gpu_nodes_full}</b> unique nodes</td>
  <td>{_ni_runner_grouped_html}</td>
  <td style="font-size:12px;color:#555;min-width:720px;word-wrap:break-word"><div style="font-size:11.5px">Full GPU family coverage; all unique physical machines, each counted once</div>{_ni_breakdown_html}</td>
</tr>
<tr style="font-weight:700;background:#FFE0B2">
  <td>Nightly Subtotal</td>
  <td style="text-align:center;font-size:13px;color:#E65100"><b>{_ni_gpu_nodes_full}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} shared build VMs</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_ni_gpu_nodes_full} physical GPU</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_build_vms} Azure build VMs + <b>{_ni_gpu_nodes_full}</b> physical GPU machines = <b>{_build_vms + _ni_gpu_nodes_full}</b> total</td>
</tr>

<!-- Grand Total -->
<tr style="font-weight:700;background:#37474F;color:#fff">
  <td colspan="2" style="text-align:center;font-size:13px;letter-spacing:0.3px">Grand Total (all tiers, unique)</td>
  <td style="text-align:center;font-size:13px"><b>{_build_vms + _ni_gpu_nodes_full}</b></td>
  <td style="text-align:center;font-size:12px">{_build_vms} VMs<br><span style="font-weight:400;font-size:11.5px;opacity:0.85">(Azure, no GPU)</span></td>
  <td style="text-align:center;font-size:12px"><b>{_ni_gpu_nodes_full}</b> physical<br><span style="font-weight:400;font-size:11.5px;opacity:0.85">unique GPU machines</span></td>
  <td colspan="2" style="font-size:12.5px;opacity:0.9">{_build_vms} Azure build VMs (cloud, no GPU) + {_ni_gpu_nodes_full} unique physical GPU machines = <b>{_build_vms + _ni_gpu_nodes_full}</b> &nbsp;&bull;&nbsp; <span style="font-weight:400">GPU node counts cumulative across tiers &mdash; each physical machine counted once</span></td>
</tr>
</tbody></table></div>
<p style="font-size:10.5px;color:#777;margin:4px 0 22px 4px">
  <b>Azure Build Pool</b>: Cloud-managed VMs with no GPU &mdash; used exclusively for compile, package, and artifact jobs. VM counts are point-in-time snapshots; elastic pools can provision beyond this number under load.<br>
  <b>Physical GPU counts</b>: Unique machines counted once regardless of how many tiers use them. Pre-commit uses {_pc_gpu_nodes_full} (full gfx94X test pool incl. 1+8 GPU + alt pools + ASAN sandbox + Win build-only), Post-commit adds MI355X (gfx950 1+8 GPU) for {_po_gpu_nodes_full}, Nightly expands to all {_ni_gpu_nodes_full} GPU machines across {len(_NI_GPU_LABELS)} runner labels.
</p>

<!-- ── 2/3: FRAMEWORK RUNNER & SERVER COUNT DETAILS ─────────────────── -->
<h3 id="server-counts-framework" style="margin:24px 0 8px 0;font-size:14px;color:#37474F;font-weight:700;border-bottom:2px solid #37474F;padding-bottom:4px">
  2 &mdash; Framework Runner &amp; Server Count Details
  <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="font-size:11.5px;font-weight:400;margin-left:8px;color:#1565C0;text-decoration:none;border:1px solid #1565C0;padding:1px 6px;border-radius:3px">&#128279; Runner Health</a>
</h3>
<div class="tbl-wrap" style="margin-bottom:18px"><table class="fw-table fw-server-table">
<thead><tr>
  <th>Framework</th>
  <th>Pool</th>
  <th>Count</th>
  <th>Build (VMs)</th>
  <th>GPU Test (Physical)</th>
  <th>Runner Labels &amp; Counts</th>
  <th style="width:800px;min-width:720px">Comments<br><span style="font-weight:400;font-size:10.5px;color:#FFE082">coverage &middot; online/offline by gfx &middot; DO-NOT-ENABLE</span></th>
</tr></thead>
<tbody>
<tr class="fw-pytorch">
  <td rowspan="3" style="font-weight:700;color:#1F4E79;vertical-align:middle;text-align:center">PyTorch</td>
  <td>Build Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">2 VM pools, no GPU</span></td>
  <td style="text-align:center"><b>{_pt_build_servers}</b> VMs<br><span style="font-weight:400;font-size:11.5px;color:#777">(snapshot)</span></td>
  <td style="text-align:center"><b>{_runner_counts.get("azure-linux-scale-rocm", 0)}</b> Linux VMs<br>+<br><b>{_runner_counts.get("azure-windows-scale-rocm", 0)}</b> Windows VMs</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td>azure-linux-scale-rocm = <b>{_runner_counts.get("azure-linux-scale-rocm", 0)}</b> VMs &bull; azure-windows-scale-rocm = <b>{_runner_counts.get("azure-windows-scale-rocm", 0)}</b> VMs</td>
  <td>2 elastic VM pools (no GPU); auto-scales beyond snapshot count when queue builds up</td>
</tr>
<tr class="fw-pytorch">
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">{len(_NI_GPU_LABELS)} physical runner labels (grouped by gfx)</span></td>
  <td style="text-align:center"><b>{_ni_gpu_nodes_full}</b> physical</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_ni_gpu_nodes_full}</b> across {len(_NI_GPU_LABELS)} runner labels</td>
  <td>{_pt_runner_grouped_html}</td>
  <td style="min-width:720px;word-wrap:break-word;font-size:12px"><div style="font-size:11.5px">{_pt_combinations}</div>{_pt_breakdown_html}</td>
</tr>
<tr class="fw-pytorch" style="font-weight:700;background:#D0E8F8">
  <td>Total</td>
  <td style="text-align:center;color:#1F4E79"><b>{_pt_build_servers + _ni_gpu_nodes_full}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_pt_build_servers} VMs (build)</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_ni_gpu_nodes_full} physical (GPU test)</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_pt_build_servers} build VMs + {_ni_gpu_nodes_full} physical GPU machines = <b>{_pt_build_servers + _ni_gpu_nodes_full}</b> &nbsp;(mixed: VMs + physical)</td>
</tr>
<tr class="fw-jax">
  <td rowspan="2" style="font-weight:700;color:#2E7D32;vertical-align:middle;text-align:center">JAX</td>
  <td>Build + Test<br><span style="font-weight:400;font-size:11.5px;color:#777">shared build VM pool</span></td>
  <td style="text-align:center"><b>{_jax_gpu_servers}</b> physical<br><span style="font-weight:400;font-size:11.5px;color:#777">(dedicated GPU)</span></td>
  <td style="color:#777;font-size:10.5px">Shared with PyTorch<br><span style="font-size:11.5px">azure-linux-scale-rocm</span><br><span style="font-size:11.5px">(VMs, not counted separately)</span></td>
  <td style="text-align:center"><b>{_jax_gpu_servers}</b> physical<br><span style="font-size:11.5px">(gfx94X only)</span></td>
  <td>linux-gfx942-1gpu-ossci-rocm = <b>{_jax_gpu_servers}</b> physical &nbsp;<span style="color:#888;font-size:10.5px">| Build: shared azure-linux-scale-rocm VMs</span></td>
  <td style="min-width:720px;word-wrap:break-word;font-size:12px"><div style="font-size:11.5px">{_jax_combinations}</div>{_jax_breakdown_html}</td>
</tr>
<tr class="fw-jax" style="font-weight:700;background:#C8E6C9">
  <td>Total</td>
  <td style="text-align:center;color:#2E7D32"><b>{_jax_gpu_servers}</b><br><span style="font-weight:400;font-size:11.5px">physical only</span></td>
  <td style="font-weight:400;font-size:10.5px;color:#555">Build VMs shared with PyTorch — not counted separately</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_jax_gpu_servers} physical</td>
  <td colspan="2" style="color:#555;font-size:12.5px"><b>{_jax_gpu_servers}</b> dedicated physical GPU machines + shared build VM pool (counted under PyTorch)</td>
</tr>
<tr style="font-weight:700;background:#37474F;color:#fff">
  <td colspan="2" style="text-align:center;font-size:13px;letter-spacing:0.3px">Grand Total (PyTorch + JAX)</td>
  <td style="text-align:center;font-size:13px"><b>{_grand_total}</b></td>
  <td style="text-align:center;font-size:12px">{_pt_build_servers} VMs<br><span style="font-weight:400;font-size:11.5px;opacity:0.85">(shared build pool)</span></td>
  <td style="text-align:center;font-size:12px"><b>{_grand_physical}</b> physical<br><span style="font-weight:400;font-size:11.5px;opacity:0.85">unique GPU machines<br>JAX shares PyTorch pool</span></td>
  <td colspan="2" style="font-size:12.5px;opacity:0.9">{_pt_build_servers} shared build VMs + {_grand_physical} unique physical GPU machines = <b>{_grand_total}</b> &nbsp;&bull;&nbsp; <span style="font-weight:400">JAX reuses <code>linux-gfx942-1gpu-ossci-rocm</code> from PyTorch&apos;s pool — not counted separately</span></td>
</tr>
</tbody>
</table>
<p style="font-size:10.5px;color:#777;margin:4px 0 22px 4px">
  <b>Count</b>: VM instance counts are point-in-time snapshots from the runner fleet; elastic pools can provision beyond this number under load.<br>
  <b>Build VMs</b>: Azure-managed virtual machines with no GPU &mdash; 2 pools total (<code>azure-linux-scale-rocm</code>, <code>azure-windows-scale-rocm</code>). Physical server count underneath is managed by Azure and not exposed.
</p>
</div>

<!-- (Inference Runner Inventory moved to its own section below the InferenceMAX CI table — that's where it logically belongs since these pools are NOT tracked by therock-runner-health.com.) -->
</div>
<!-- ═══════════════════════════════════════════════════════════════════
     RUNNER INVENTORY
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="runners">
<h2>Runner Inventory (All Known Runners) <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="font-size:13px;font-weight:400;vertical-align:middle;margin-left:10px;color:#1565C0;text-decoration:none;border:1px solid #1565C0;padding:2px 8px;border-radius:4px">&#128279; Runner Health Dashboard</a></h2>
<h3 style="margin:0 0 8px 0;font-size:13px;color:#444;font-weight:600">Physical GPU Machines by Location</h3>
<div class="tbl-wrap" style="margin-bottom:6px"><table class="fw-table">
<thead><tr>
  <th>Location</th>
  <th style="text-align:center">Physical Machines</th>
  <th style="text-align:center">Linux</th>
  <th style="text-align:center">Windows</th>
  <th style="text-align:center">Share</th>
</tr></thead>
<tbody>
{_loc_summary_rows}
</tbody>
</table></div>
<p style="font-size:10.5px;color:#777;margin:4px 0 18px 4px">
  <b>{_loc_total} unique physical GPU machines</b> across all runner pools — each machine counted once.
  The Framework section shows <b>{_grand_physical}</b> GPU machines (PyTorch&apos;s pool, which JAX also shares) + <b>{_pt_build_servers}</b> shared build VMs = <b>{_grand_total}</b>.
  The additional {_loc_total - _grand_physical} machines here (<code>linux-strix-halo-gpu-rocm-oem</code>, <code>nova-linux-slurm-scale-runner</code>, <code>rocm-asan-mi325-sandbox</code>) are not part of the PyTorch/JAX framework CI runner lists.
</p>
<div class="tbl-wrap"><table>
<thead><tr>
  <th style="text-align:center">#</th><th>Runner Label</th><th>Platform</th><th>OS / Distro</th>
  <th>Location</th><th>Physical Machines</th><th>GPU Family</th><th>GPU ISA</th>
  <th style="text-align:center">GPUs/job</th><th>Used At</th><th>Notes</th>
</tr></thead>
<tbody>
{runner_rows_html}
</tbody></table></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     INFERENCEMAX — AMD GPU INFERENCE BENCHMARKS
════════════════════════════════════════════════════════════════════ -->
<div class="ecosystem-banner inferencemax">
  <span class="eco-title">&#128640; InferenceMAX CI</span>
  <span class="eco-subtitle">ROCm/InferenceMAX_rocm &bull; AMD fork of SemiAnalysis InferenceX &bull; MI300X / MI325X / MI355X</span>
  <span class="eco-badge">Benchmark Configs &bull; Inference Runners &bull; Workflow Triggers</span>
</div>
<div class="section section-imax" id="inferencemax">
<h2>&#128640; InferenceMAX CI &mdash; AMD GPU Inference Benchmarks</h2>
<p class="inf-source">Source: <a href="https://github.com/ROCm/InferenceMAX_rocm" target="_blank" rel="noopener">ROCm/InferenceMAX_rocm</a> &bull; AMD fork of SemiAnalysis InferenceX for MI300X/MI325X/MI355X benchmarking</p>
<div class="summary" style="margin-bottom:16px">
  <div class="card"><h3>AMD Configs</h3><div class="num" style="color:#CC0000">{_imax_count}</div><div class="sub">benchmark configurations</div></div>
  <div class="card"><h3>GPU Runner Types</h3><div class="num" style="color:#CC0000">{_imax_gpus}</div><div class="sub">distinct GPU types (mi300x / mi325x / mi355x)</div></div>
  <div class="card"><h3>Total Servers</h3><div class="num" style="color:#CC0000">{_imax_server_total if _imax_server_total else "—"}</div><div class="sub">physical nodes across all AMD runner pools</div></div>
  <div class="card"><h3>Frameworks</h3><div class="num" style="color:#CC0000">{_imax_fws}</div><div class="sub">inference frameworks (atom / sglang / sglang-disagg / vllm)</div></div>
  <div class="card"><h3>Multi-Node</h3><div class="num" style="color:#CC0000">{_imax_multi}</div><div class="sub">multi-node configs</div></div>
</div>
<div class="tbl-wrap"><table style="width:100%">
<thead><tr class="hdr-imax">
  <th>Config Name</th><th>Model</th><th>Model Prefix</th><th>GPU Runner</th>
  <th style="text-align:center">Precision</th><th style="text-align:center">Framework</th><th style="text-align:center">Multi-Node</th><th>Pinned Docker Image</th>
</tr></thead>
<tbody>{_imax_rows}</tbody>
</table></div>

<!-- ─── INFERENCE RUNNER INVENTORY (placed here, NOT in the Server Counts section,
     because these pools are NOT tracked by therock-runner-health.com — they belong
     with the InferenceMAX CI data and use a separate AMD-S Slurm + self-hosted Docker
     management plane.) ────────────────────────────────────────────────────── -->
<h3 id="inference-runner-inventory" style="margin:28px 0 8px 0;font-size:15px;color:#4E342E;font-weight:700;border-bottom:2px solid #4E342E;padding-bottom:4px">
  Inference Runner Inventory &nbsp;<span style="font-weight:400;font-size:12px;color:#666">(InferenceMAX AMD GPU benchmarking pools)</span>
</h3>
<p style="font-size:12px;color:#5D4037;margin:6px 0 10px 0;background:#FFF8E1;border-left:4px solid #F9A825;padding:8px 12px;border-radius:3px">
  &#9432; Live online/offline status for these runners is <b>not</b> available from
  <code>therock-runner-health.com</code>. They are managed independently by the
  <code>ROCm/InferenceMAX_rocm</code> repo via AMD internal Slurm scheduler + self-hosted
  Docker pools. Snapshot counts below are from the InferenceMAX runner config.
</p>
<div class="tbl-wrap" id="inference-runners"><table>
<thead><tr class="hdr-infr">
  <th style="vertical-align:middle">Ecosystem</th><th style="vertical-align:middle">GPU Type</th><th style="vertical-align:middle">Runner Labels</th>
  <th style="vertical-align:middle;text-align:center">Node Count</th><th style="vertical-align:middle">Cluster Type</th>
  <th style="vertical-align:middle;width:800px;min-width:720px">Comments<br><span style="font-weight:400;font-size:10.5px;color:#FFE0B2">sub-pools &middot; quirks &middot; tracking source</span></th>
</tr></thead>
<tbody>{_inf_run_rows_html}</tbody>
</table></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     DATA SOURCES
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="data-sources">
<h2>&#128196; How Data Is Fetched</h2>
<p style="font-size:12px;color:#555;margin-bottom:16px">
  <code>fetch_rocm_data.py</code> pulls live data from four GitHub repositories using
  <b>anonymous sparse <code>git clone</code></b> for the public repos and an
  <b>SSH <code>git clone</code></b> for the private <code>ROCm/InferenceMAX_rocm</code>.
  No <code>GITHUB_TOKEN</code> is required &mdash; ROCm-org now blocks classic PATs, and
  fine-grained tokens typically need admin approval. Each clone is shallow
  (<code>--depth=1</code>) and blob-filtered (<code>--filter=blob:none</code>), so the live run
  finishes in &asymp;60&nbsp;seconds and only downloads the handful of files actually used.
  If any clone fails, the fetcher transparently falls back to the committed JSON snapshots
  (<code>therock_ci_snapshot.json</code>, <code>inferencemax_snapshot.json</code>).
</p>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:18px">

<div style="background:#E3F2FD;border-radius:8px;padding:16px 20px;border-left:4px solid #1565C0">
  <div style="font-weight:700;font-size:13px;color:#1565C0;margin-bottom:10px">
    &#128279; Source 1 &mdash; <a href="https://github.com/ROCm/TheRock" target="_blank" rel="noopener" style="color:#1565C0">ROCm/TheRock</a>
  </div>
  <table style="width:100%;font-size:12.5px;border-collapse:collapse">
    <thead><tr><th style="text-align:left;padding:4px 8px;background:#1565C0;color:#fff">File</th><th style="text-align:left;padding:4px 8px;background:#1565C0;color:#fff">What it populates</th></tr></thead>
    <tbody>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/TheRock/blob/main/build_tools/github_actions/amdgpu_family_matrix.py" target="_blank" rel="noopener">build_tools/github_actions/amdgpu_family_matrix.py</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">Runner labels per GPU family, GPU ISA strings (gfx94X, gfx950, &hellip;), nightly-only flags</td></tr>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml" target="_blank" rel="noopener">BUILD_TOPOLOGY.toml</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">Component &rarr; super-repo mapping (rocm-libraries / rocm-systems / TheRock)</td></tr>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/TheRock/blob/main/.gitmodules" target="_blank" rel="noopener">.gitmodules</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">Direct submodule list — identifies components tested inside TheRock itself</td></tr>
      <tr><td style="padding:4px 8px"><a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml" target="_blank" rel="noopener">ci_nightly.yml</a></td><td style="padding:4px 8px">Nightly schedule time, GPU family test matrix for the nightly tier</td></tr>
    </tbody>
  </table>
  <div style="font-size:12.5px;color:#555;margin-top:8px">
    <b>Workflow files also used (for CI Tiers section):</b>
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml" target="_blank" rel="noopener">ci.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_asan.yml" target="_blank" rel="noopener">ci_asan.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_tsan.yml" target="_blank" rel="noopener">ci_tsan.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_ci.yml" target="_blank" rel="noopener">multi_arch_ci.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_release.yml" target="_blank" rel="noopener">multi_arch_release.yml</a>
  </div>
</div>

<div style="background:#E8F5E9;border-radius:8px;padding:16px 20px;border-left:4px solid #2E7D32">
  <div style="font-weight:700;font-size:13px;color:#2E7D32;margin-bottom:10px">
    &#128279; Source 2 &mdash; <a href="https://github.com/ROCm/rocm-libraries" target="_blank" rel="noopener" style="color:#2E7D32">ROCm/rocm-libraries</a>
  </div>
  <p style="font-size:12.5px;margin:0">
    <b>Method:</b> Anonymous git clone (<code>--depth=1 --filter=blob:none --no-checkout</code>) +
    <code>git ls-tree -d projects/</code> &mdash; <b>no blobs are downloaded</b>.<br>
    <b>Populates:</b> All library component names (rocBLAS, hipBLAS, MIOpen, rocFFT, &hellip;).
    Every subdirectory in <code>projects/</code> is treated as an active CI component.
  </p>
</div>

<div style="background:#FFF8E1;border-radius:8px;padding:16px 20px;border-left:4px solid #F57C00">
  <div style="font-weight:700;font-size:13px;color:#E65100;margin-bottom:10px">
    &#128279; Source 3 &mdash; <a href="https://github.com/ROCm/rocm-systems" target="_blank" rel="noopener" style="color:#E65100">ROCm/rocm-systems</a>
  </div>
  <p style="font-size:12.5px;margin:0">
    <b>Method:</b> Anonymous git clone (<code>--depth=1 --filter=blob:none --no-checkout</code>) +
    <code>git ls-tree -d projects/</code> &mdash; <b>no blobs are downloaded</b>.<br>
    <b>Populates:</b> All system component names (RCCL, rocminfo, ROCm-SMI, &hellip;).
  </p>
</div>

<div style="background:#F3E5F5;border-radius:8px;padding:16px 20px;border-left:4px solid #4A148C">
  <div style="font-weight:700;font-size:13px;color:#4A148C;margin-bottom:10px">
    &#128279; Source 4 &mdash; <a href="https://github.com/ROCm/InferenceMAX_rocm" target="_blank" rel="noopener" style="color:#4A148C">ROCm/InferenceMAX_rocm</a>
    <span style="font-size:12.5px;font-weight:400"> (AMD fork of SemiAnalysis InferenceX)</span>
  </div>
  <table style="width:100%;font-size:12.5px;border-collapse:collapse">
    <thead><tr><th style="text-align:left;padding:4px 8px;background:#4A148C;color:#fff">File</th><th style="text-align:left;padding:4px 8px;background:#4A148C;color:#fff">What it populates</th></tr></thead>
    <tbody>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml" target="_blank" rel="noopener">amd-master.yaml</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">All 34 AMD benchmark configs — model, GPU, precision, framework, pinned Docker image</td></tr>
      <tr><td style="padding:4px 8px"><a href="https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml" target="_blank" rel="noopener">runners.yaml</a></td><td style="padding:4px 8px">AMD GPU runner pool definitions — maps mi300x/mi325x/mi355x to physical node labels</td></tr>
    </tbody>
  </table>
  <div style="font-size:12.5px;color:#555;margin-top:8px">
    <b>Data source priority:</b>
    (1) Local clone at <code>./InferenceMAX_rocm/</code> &rarr;
    (2) Sparse SSH clone (<code>git@github.com:ROCm/InferenceMAX_rocm.git</code>) &rarr;
    (3) <code>inferencemax_snapshot.json</code> (committed cache)
  </div>
</div>

<div style="background:#FFF3E0;border-radius:8px;padding:16px 20px;border-left:4px solid #EF6C00">
  <div style="font-weight:700;font-size:13px;color:#E65100;margin-bottom:10px">
    &#128279; Source 5 &mdash; <a href="https://therock-runner-health.com/" target="_blank" rel="noopener" style="color:#E65100">therock-runner-health.com</a>
    <span style="font-size:12.5px;font-weight:400"> (live runner fleet status, AMD-internal)</span>
  </div>
  <p style="font-size:12.5px;margin:0 0 6px 0">
    <b>Populates:</b> the live online/offline/busy/idle counts and queue-health badges
    shown next to every runner label in the &ldquo;Server count&rdquo; section, plus the
    physical-machine deduplication used to reconcile declared vs. live capacity.
  </p>
  <div style="font-size:12.5px;color:#555">
    <b>Data source priority</b> (handled by <code>runner_health_parser.load_runner_health_any</code>):<br>
    (1) Local <code>TheRock Runner Health.mhtml</code> in this folder &mdash;
        save the dashboard via <i>Save&nbsp;Page&nbsp;As&nbsp;&rarr;&nbsp;Webpage Single&nbsp;File</i>
        while signed in on the AMD network. <b>Not committed to git.</b><br>
    (2a) Anonymous HTTPS <code>GET</code> of the dashboard &mdash; 1-second probe;
        almost always falls through because the URL is gated by GitHub OAuth.<br>
    (2b) <b>Playwright</b> with persistent Chromium profile (opt-in dependency:
        <code>pip install playwright &amp;&amp; python -m playwright install chromium</code>) &mdash;
        first run pops a visible Chromium window for one-time GitHub sign-in,
        every subsequent run reuses the cached session silently and headlessly.
        Profile lives at <code>~/.rocm-cicd-report/playwright-profile</code> by default;
        set <code>RUNNER_HEALTH_NO_PLAYWRIGHT=1</code> to skip on CI.<br>
    (3) <code>runner_health_snapshot.json</code> &mdash; committed JSON cache of the last
        successful parse. Refreshed automatically every time path&nbsp;(1), (2a) or (2b)
        succeeds, so most users transparently see recent numbers.
  </div>
</div>

</div><!-- end grid -->

<div style="margin-top:18px;background:#f5f5f5;border-radius:6px;padding:12px 18px;font-size:12.5px;color:#555">
  <b>Fetch pipeline:</b>
  Sparse anonymous git clones (public repos) + Sparse SSH clone (InferenceMAX_rocm) &rarr;
  <code>fetch_rocm_data.py</code> &rarr;
  <code>rocm_ci_data.py</code> (intermediate snapshot) &rarr;
  <code>generate_rocm_html.py</code> + <code>generate_rocm_cicd.py</code> &rarr;
  <b>ROCm_CICD_Comprehensive.html</b> + <b>ROCm_CICD_Comprehensive.xlsx</b><br>
  <b>Resilience:</b> any clone failure transparently falls back to the committed
  <code>therock_ci_snapshot.json</code> / <code>inferencemax_snapshot.json</code>.
  Runner-health enrichment uses its own three-tier chain
  (local <code>.mhtml</code> &rarr; live HTTPS &rarr; committed
  <code>runner_health_snapshot.json</code>).
</div>

</div>

<!-- ═══════════════════════════════════════════════════════════════════
     APPENDIX — AMD GFX ISA → ASIC LOOKUP
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="appendix-gfx">
<h2>&#128218; Appendix &mdash; AMD GFX ISA &rarr; ASIC Full Lookup Table</h2>
<p style="font-size:12px;color:#555;margin-bottom:14px">
  Reference table mapping every AMD <code>gfxNNN</code> ISA target to its
  codename, chip family, retail products, and market segment. Use this to
  decode the GPU family abbreviations used throughout this report
  (<code>gfx94X</code>, <code>gfx1151</code>, etc.).
</p>

<style>
.gfx-tbl {{ border-collapse:collapse; width:100%; margin:8px 0 24px 0; font-size:12px }}
.gfx-tbl th {{ background:#37474F; color:#fff; padding:6px 10px; text-align:left;
               border:1px solid #263238; font-weight:700; font-size:11.5px }}
.gfx-tbl td {{ padding:5px 10px; border:1px solid #CFD8DC; vertical-align:top }}
.gfx-tbl tr:nth-child(even) td {{ background:#FAFAFA }}
.gfx-tbl code {{ font-size:11.5px; color:#1565C0; font-weight:700 }}
.gfx-grp-h {{ margin:18px 0 6px 0; font-size:14.5px; color:#CC0000;
              border-bottom:2px solid #CC0000; padding-bottom:3px; font-weight:700 }}
.gfx-grp-sub {{ font-weight:400; font-size:11.5px; color:#666; margin-left:8px }}
.gfx-seg-Consumer  {{ background:#E3F2FD }}
.gfx-seg-Pro       {{ background:#F3E5F5 }}
.gfx-seg-APU       {{ background:#FFF3E0 }}
.gfx-seg-DC        {{ background:#FFEBEE }}
.gfx-seg-Mobile    {{ background:#E8F5E9 }}
.gfx-seg-Embedded  {{ background:#ECEFF1 }}
</style>

<h3 class="gfx-grp-h">GFX8 &mdash; GCN 4 (Polaris / Fiji) <span class="gfx-grp-sub">Pre-ROCm era</span></h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx803</code></td><td>Fiji</td><td>Fiji XT/Pro</td><td>R9 Fury X, R9 Fury, R9 Nano</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx803</code></td><td>Ellesmere</td><td>Polaris 10/20</td><td>RX 480, RX 580, RX 470, RX 570</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx804</code></td><td>Baffin</td><td>Polaris 11/21</td><td>RX 460, RX 560, RX 560X</td><td class="gfx-seg-Consumer">Consumer</td></tr>
</tbody></table>

<h3 class="gfx-grp-h">GFX9 &mdash; Vega / CDNA</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx900</code></td><td>Vega 10</td><td>Vega 10 XT/XL</td><td>RX Vega 64, RX Vega 56, Instinct MI25</td><td class="gfx-seg-DC">Consumer + DC</td></tr>
<tr><td><code>gfx902</code></td><td>Raven / Raven2</td><td>Raven</td><td>Ryzen 2000/3000 APU &mdash; Radeon RX Vega 8/11</td><td class="gfx-seg-APU">APU</td></tr>
<tr><td><code>gfx904</code></td><td>Vega 12</td><td>Vega 12</td><td>Radeon Pro Vega 20, Radeon Pro Vega 16</td><td class="gfx-seg-Pro">Pro</td></tr>
<tr><td><code>gfx906</code></td><td>Vega 20</td><td>Vega 20</td><td>Radeon VII, Instinct MI50, Instinct MI60</td><td class="gfx-seg-DC">Consumer + DC</td></tr>
<tr><td><code>gfx908</code></td><td>Arcturus</td><td>Arcturus</td><td>Instinct MI100</td><td class="gfx-seg-DC">CDNA1 DC</td></tr>
<tr><td><code>gfx90a</code></td><td>Aldebaran</td><td>Aldebaran</td><td>Instinct MI210, MI250, MI250X</td><td class="gfx-seg-DC">CDNA2 DC</td></tr>
<tr><td><code>gfx90c</code></td><td>Renoir</td><td>Renoir</td><td>Ryzen 4000/5000 APU &mdash; Radeon RX Vega 6/7/8</td><td class="gfx-seg-APU">APU</td></tr>
<tr><td><code>gfx940</code></td><td>Aqua Vanjaram</td><td>CDNA3 (eng. step A)</td><td>Pre-production only</td><td class="gfx-seg-DC">CDNA3 DC</td></tr>
<tr><td><code>gfx941</code></td><td>Aqua Vanjaram</td><td>CDNA3 (eng. step B)</td><td>Pre-production only</td><td class="gfx-seg-DC">CDNA3 DC</td></tr>
<tr><td><code>gfx942</code></td><td>Aqua Vanjaram</td><td>CDNA3</td><td>Instinct MI300X, MI300A, MI325X</td><td class="gfx-seg-DC">CDNA3 DC</td></tr>
<tr><td><code>gfx950</code></td><td>Antares</td><td>CDNA4</td><td>Instinct MI355X</td><td class="gfx-seg-DC">CDNA4 DC</td></tr>
</tbody></table>

<h3 class="gfx-grp-h">GFX10 &mdash; RDNA 1</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx1010</code></td><td>Navi 10</td><td>Navi 10</td><td>RX 5700 XT, RX 5700, RX 5600 XT, Radeon Pro 5700 XT</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1011</code></td><td>Navi 12</td><td>Navi 12</td><td>Radeon Pro 5600M, Radeon Pro VII</td><td class="gfx-seg-Pro">Pro / Mobile</td></tr>
<tr><td><code>gfx1012</code></td><td>Navi 14</td><td>Navi 14</td><td>RX 5500 XT, RX 5500, RX 5300 XT, RX 5300</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1013</code></td><td>Cyan Skillfish</td><td>Cyan Skillfish</td><td>Embedded / rare discrete variant</td><td class="gfx-seg-Embedded">Embedded</td></tr>
</tbody></table>

<h3 class="gfx-grp-h">GFX10.3 &mdash; RDNA 2</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx1030</code></td><td>Navi 21</td><td>Navi 21 XTXH/XTX/XT/XL</td><td>RX 6950 XT, RX 6900 XT, RX 6800 XT, RX 6800, Radeon Pro W6800</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1031</code></td><td>Navi 22</td><td>Navi 22 XT/XL</td><td>RX 6700 XT, RX 6700, Radeon Pro W6600</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1032</code></td><td>Navi 23</td><td>Navi 23 XT/XL/XM</td><td>RX 6600 XT, RX 6600, RX 6650 XT</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1033</code></td><td>Navi 24</td><td>Navi 24 XT/XL/XM</td><td>RX 6500 XT, RX 6400, RX 6300</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1034</code></td><td>Beige Goby</td><td>Navi 24 (mobile)</td><td>RX 6500M, RX 6300M</td><td class="gfx-seg-Mobile">Mobile</td></tr>
<tr><td><code>gfx1035</code></td><td>Yellow Carp</td><td>Rembrandt</td><td>Ryzen 6000 APU &mdash; Radeon 680M, 660M</td><td class="gfx-seg-APU">APU</td></tr>
<tr><td><code>gfx1036</code></td><td>Barcelo-R</td><td>Rembrandt-R</td><td>Ryzen 5000 refresh APU &mdash; Radeon 610M</td><td class="gfx-seg-APU">APU</td></tr>
</tbody></table>

<h3 class="gfx-grp-h">GFX11 &mdash; RDNA 3</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx1100</code></td><td>Navi 31</td><td>Navi 31 XTX/XT</td><td>RX 7900 XTX, RX 7900 XT, RX 7900 GRE, Radeon Pro W7900</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1101</code></td><td>Navi 32</td><td>Navi 32 XT/XL</td><td>RX 7800 XT, RX 7700 XT, Radeon Pro W7700</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1102</code></td><td>Navi 33</td><td>Navi 33 XT/XL</td><td>RX 7600 XT, RX 7600, Radeon Pro W7600</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1103</code></td><td>Phoenix</td><td>Phoenix 1</td><td>Ryzen 7040 APU &mdash; Radeon 780M, 760M, 740M</td><td class="gfx-seg-APU">APU</td></tr>
</tbody></table>

<h3 class="gfx-grp-h">GFX11 &mdash; RDNA 3.5</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx1150</code></td><td>Strix Point</td><td>Strix Point</td><td>Ryzen AI 300 &mdash; Radeon 890M, 880M</td><td class="gfx-seg-APU">APU</td></tr>
<tr><td><code>gfx1151</code></td><td>Strix Halo</td><td>Strix Halo</td><td>Ryzen AI Max &mdash; Radeon 8060S, 8050S</td><td class="gfx-seg-APU">APU (large die)</td></tr>
<tr><td><code>gfx1152</code></td><td>Krackan Point</td><td>Krackan Point</td><td>Ryzen AI 300 &mdash; Radeon 840M</td><td class="gfx-seg-APU">APU</td></tr>
<tr><td><code>gfx1153</code></td><td>Krackan Point</td><td>Krackan Point</td><td>Ryzen AI 300 &mdash; Radeon 820M</td><td class="gfx-seg-APU">APU</td></tr>
</tbody></table>
<p style="font-size:11px;color:#666;margin:-12px 0 16px 4px;font-style:italic">
  <code>gfx1152</code> and <code>gfx1153</code> are separate ISA targets despite sharing the
  Krackan Point codename &mdash; different CU configs produce different ISA IDs.
</p>

<h3 class="gfx-grp-h">GFX12 &mdash; RDNA 4</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX ISA</th><th>Codename</th><th>Chip</th><th>Products</th><th>Segment</th></tr></thead>
<tbody>
<tr><td><code>gfx1200</code></td><td>Navi 48</td><td>Navi 48 XT/XTX</td><td>RX 9070 XT, RX 9070</td><td class="gfx-seg-Consumer">Consumer</td></tr>
<tr><td><code>gfx1201</code></td><td>Navi 44</td><td>Navi 44 XT</td><td>RX 9060 XT</td><td class="gfx-seg-Consumer">Consumer</td></tr>
</tbody></table>

<h3 class="gfx-grp-h">Architecture Summary</h3>
<table class="gfx-tbl">
<thead><tr><th>GFX Range</th><th>Architecture</th><th>Generation</th><th>Primary Use</th></tr></thead>
<tbody>
<tr><td><code>gfx803&ndash;gfx804</code></td><td>GCN 4</td><td>Polaris / Fiji</td><td>Legacy (ROCm dropped)</td></tr>
<tr><td><code>gfx900&ndash;gfx90c</code></td><td>GFX9 / Vega</td><td>Vega + APUs</td><td>ROCm legacy (build-only in CI)</td></tr>
<tr><td><code>gfx908</code></td><td>GFX9 / CDNA1</td><td>Arcturus</td><td>Datacenter (ROCm 4+)</td></tr>
<tr><td><code>gfx90a</code></td><td>GFX9 / CDNA2</td><td>Aldebaran</td><td>Datacenter (MI200)</td></tr>
<tr><td><code>gfx940&ndash;gfx942</code></td><td>GFX9 / CDNA3</td><td>Aqua Vanjaram</td><td>Datacenter (MI300 series)</td></tr>
<tr><td><code>gfx950</code></td><td>GFX9 / CDNA4</td><td>Antares</td><td>Datacenter (MI355X)</td></tr>
<tr><td><code>gfx1010&ndash;gfx1013</code></td><td>GFX10 / RDNA 1</td><td>Navi 1x</td><td>Consumer (build-only in CI)</td></tr>
<tr><td><code>gfx1030&ndash;gfx1036</code></td><td>GFX10.3 / RDNA 2</td><td>Navi 2x</td><td>Consumer + APU</td></tr>
<tr><td><code>gfx1100&ndash;gfx1103</code></td><td>GFX11 / RDNA 3</td><td>Navi 3x</td><td>Consumer + APU</td></tr>
<tr><td><code>gfx1150&ndash;gfx1153</code></td><td>GFX11 / RDNA 3.5</td><td>Strix / Krackan</td><td>APU (Ryzen AI)</td></tr>
<tr><td><code>gfx1200&ndash;gfx1201</code></td><td>GFX12 / RDNA 4</td><td>Navi 4x</td><td>Consumer</td></tr>
</tbody></table>

</div>

<footer>ROCm CI/CD Matrix &mdash; Last updated: {_TIMESTAMP}{_imax_timestamp_note} &bull; AMD Advanced Micro Devices &bull; Data sourced from TheRock/.github/workflows &amp; amdgpu_family_matrix.py</footer>

<script>
function filterTable(){{
  const cat=document.getElementById('catFilter').value.toLowerCase();
  const ci=document.getElementById('ciFilter').value.toLowerCase();
  const q=document.getElementById('searchInput').value.toLowerCase();
  document.querySelectorAll('#compTbody tr').forEach(r=>{{
    const cells=[...r.querySelectorAll('td')].map(c=>c.innerText.toLowerCase());
    const matchCat=!cat||cells[0].includes(cat);
    const matchCI=!ci||cells[4].includes(ci);
    const matchQ=!q||cells.some(c=>c.includes(q));
    r.style.display=(matchCat&&matchCI&&matchQ)?'':'none';
  }});
}}
function resetFilter(){{
  document.getElementById('catFilter').value='';
  document.getElementById('ciFilter').value='';
  document.getElementById('searchInput').value='';
  filterTable();
}}
document.querySelectorAll('nav a').forEach(a=>{{
  a.addEventListener('click',e=>{{
    const href=a.getAttribute('href');
    if(href&&href.startsWith('http'))return; // external links open normally
    e.preventDefault();
    const id=href.slice(1);
    document.getElementById(id)?.scrollIntoView({{behavior:'smooth'}});
    document.querySelectorAll('nav a').forEach(x=>x.classList.remove('active'));
    a.classList.add('active');
  }});
}});
</script>
</body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"HTML written: {OUT}")
print(f"Components: {total} total ({non_fw} non-framework, {fw_rows} framework slots)")
print(f"CI-Enabled (non-FW): {ci_enabled}")
