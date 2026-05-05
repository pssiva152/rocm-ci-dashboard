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
POR_L = "linux-gfx942-1gpu-ossci-rocm (gfx94X)\nlinux-mi355-1gpu-ossci-rocm (gfx950)"
POR_L_NONE = "—"

# Pre/Post-commit Windows runner
PCR_W = "windows-gfx1151-gpu-rocm (Build-only)"
POR_W = "windows-gfx1151-gpu-rocm (Build-only)"

# Nightly Linux runners — gfx94X + gfx950 only (for components that exclude gfx115X and only support those two families)
NLR_94_950 = ("linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
              "linux-mi355-1gpu-ossci-rocm (gfx950)")

# Nightly Linux runners (full set)
NLR_FULL = ("linux-gfx942-1gpu-ossci-rocm (gfx94X)\n"
            "linux-mi355-1gpu-ossci-rocm (gfx950)\n"
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
     "gfx950 (MI355), gfx94X (MI325), gfx1151 (Strix Halo) — own CI", "linux-mi355-1gpu-ossci-rocm (gfx950)\nlinux-gfx942-1gpu-ossci-rocm (gfx94X)\nlinux-strix-halo-gpu-rocm (gfx1151)", "—", "—", "standard",
     PO_L_FULL, POR_L, PO_W_NONE, "—", "quick",
     NL_FULL, NLR_FULL, NW_NONE, "—", "comprehensive",
     "Linux only", "Own CI (rocprofiler-compute-continuous-integration.yml); ci-matrix.yml: gfx950/gfx94X/gfx1151 × Ubuntu 22.04/24.04 (nightly); gfx950+gfx1151 × Ubuntu 22.04 (CI); ROCm 7.0.0; TheRock adds full GPU matrix at post-commit and nightly; 2 shards"),

    ("Tools","Performance","ROCm System Profiler","rocm-systems","Yes",
     "gfx950 (MI355), gfx94X (MI325) — own CI", "linux-mi355-1gpu-ossci-rocm (gfx950)\nlinux-gfx942-1gpu-ossci-rocm (gfx94X)", "—", "—", "standard",
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
    ("linux-gfx942-1gpu-ccs-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","0 (label not present in fleet)","MI300X / MI325X","gfx942 / gfx94X","1","PR · postsubmit · nightly","Label not assigned to any runner in current fleet; effectively retired","runner-linux"),
    ("linux-gfx942-8gpu-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","4 (8g2wk-* pool)","MI300X / MI325X","gfx942 / gfx94X","8","Nightly · distributed tests · RCCL","PyTorch distributed (3 shards); RCCL multi-GPU","runner-linux"),
    ("linux-mi355-1gpu-ossci-rocm","Linux","Ubuntu 22.04 LTS","OSSCI","3 (j5v9z-* pool)","MI355X","gfx950","1","Postsubmit · nightly","gfx950 not tested at PR; postsubmit matrix only","runner-linux"),
    ("linux-gfx90a-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem (AUS)","12 GPU slots (3 nodes × 4)","MI200","gfx90a","1","Nightly only","Supermicro nodes in Australia datacenter","runner-linux"),
    ("linux-gfx1030-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","2","RX 6000 (RDNA2)","gfx1030 / gfx103X","1","Nightly only","Consumer GPU (RX 6950 XT)","runner-linux"),
    ("linux-gfx110X-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","6 (gfx110X-gpu-rocm-1/2/3/4 + labctr-gfx1103 + labxsj-gfx1103)","Navi3 / RX 7900","gfx1100/1101","1","Nightly only","nightly_check_only_for_family; Build-only at PR/postsubmit","runner-linux"),
    ("linux-gfx1150-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","1–2","Strix Point","gfx1150","1","Nightly only","APU — Strix Point; nightly_check_only","runner-linux"),
    ("linux-gfx1151-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","4 (strix-halo-6/7 + shark-strixhalo-17/18; strix-halo-3 mis-labelled)","Strix Halo","gfx1151","1","Nightly only","nightly_check_only; Build-only at PR/postsubmit on Linux; strix-halo-3 offline and lacks gfx1151 label","runner-linux"),
    ("linux-strix-halo-gpu-rocm-oem","Linux","Ubuntu 22.04 LTS","On-Prem","4","Strix Halo (OEM)","gfx1151","1","Nightly only","OEM kernel variant; selected via test_runner:oem PR label","runner-linux"),
    ("linux-gfx1153-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","3","Krackan Point (Radeon 820M)","gfx1153","1","Nightly only","APU — Krackan Point; disabled since 7.12.0a20260214 (CK instability); gfx1152 (Krackan 840M) is a separate ISA target","runner-linux"),
    ("linux-gfx120X-gpu-rocm","Linux","Ubuntu 22.04 LTS","On-Prem","4 (rx9070-1/3/4 + rx9700-1; rx9070-2 mis-labelled)","Navi4 / RX 9070","gfx1200/1201","1","Nightly only","nightly_check_only_for_family; rx9070-2 lacks gfx120X label","runner-linux"),
    ("windows-gfx1151-gpu-rocm","Windows","Windows 11","On-Prem","11 (strix-halo-1/4/6/8/10-16; -7 DO-NOT-ENABLE)","Strix Halo","gfx1151","1","PR (Build-only) · postsubmit (Build-only) · nightly (Build + Test)","Primary Windows GPU runner; strix-halo-7 excluded (DO-NOT-ENABLE flag)","runner-windows"),
    ("windows-gfx110X-gpu-rocm","Windows","Windows 11","On-Prem","23 (22 online + 1 offline; azure-windows-11-gfx1101-*)","Navi3 / RX 7900 (gfx1101)","gfx1100/1101","1","Nightly only","nightly_check_only","runner-windows"),
    ("windows-gfx1030-gpu-rocm","Windows","Windows 11","On-Prem","2","RX 6000 (RDNA2)","gfx1030","1","Nightly only","","runner-windows"),
    ("windows-gfx120X-gpu-rocm","Windows","Windows 11","On-Prem","0 (label doesn't exist; use windows-gfx1201-gpu-rocm)","Navi4 / RX 9070","gfx1200/1201","1","Nightly only","Label windows-gfx120X-gpu-rocm not present in fleet; actual label is windows-gfx1201-gpu-rocm","runner-windows"),
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

_pt_build_servers = _runner_counts.get("azure-linux-scale-rocm", 0) + _runner_counts.get("azure-windows-scale-rocm", 0)
_pt_gpu_runners = [
    ("linux-gfx942-1gpu-ossci-rocm", "gfx94X (MI300X/MI325X)"),
    ("linux-gfx942-8gpu-ossci-rocm", "gfx94X 8-GPU distributed"),
    ("linux-mi355-1gpu-ossci-rocm",  "gfx950 (MI355X)"),
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

_jax_build_servers = _runner_counts.get("azure-linux-scale-rocm", 0)
_jax_gpu_servers   = _runner_counts.get("linux-gfx942-1gpu-ossci-rocm", 0)
_jax_total_servers = _jax_build_servers + _jax_gpu_servers
_jax_combinations  = "4 versions × 4 Python vers × 1 GPU runner type (gfx94X test-only)"
_grand_physical    = _pt_gpu_total   # unique physical GPU machines used by frameworks (JAX shares PyTorch's pool — no double-count)
_grand_total       = _pt_build_servers + _grand_physical # shared build VMs + unique physical GPU machines

# ── Per-tier server counts for Component CI Matrix summary bar ──────────────
_build_vms        = _pt_build_servers   # 182 shared Azure VMs (Linux 113 + Windows 69)
_pc_gpu_nodes     = (_runner_counts.get("linux-gfx942-1gpu-ossci-rocm", 0) +
                     _runner_counts.get("windows-gfx1151-gpu-rocm", 0))          # 84 + 11 = 95
_po_gpu_nodes     = (_pc_gpu_nodes +
                     _runner_counts.get("linux-mi355-1gpu-ossci-rocm", 0))        # +3 = 98
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
        rows += f"""<tr>
          <td style="vertical-align:middle"><span style="background:{badge_color};color:#fff;padding:2px 6px;border-radius:3px;font-size:12.5px">{ecosystem}</span></td>
          <td style="vertical-align:middle"><b>{gpu_type}</b></td>
          <td style="font-size:12.5px;vertical-align:middle">{node_list}</td>
          <td style="text-align:center;font-weight:700;font-size:13px;vertical-align:middle">{len(nodes)}</td>
          <td style="font-size:12.5px;vertical-align:middle">{cluster}</td>
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
        </tr>\n"""
    return rows

_imax_rows  = _inf_rows_html(INFERENCEMAX_DATA, "imax-row") if INFERENCEMAX_DATA else "<tr><td colspan='8' style='color:#999;text-align:center'>No InferenceMAX data available — run fetch_rocm_data.py with GITHUB_TOKEN or local clone</td></tr>"
_amd_run_rows = _inf_runner_rows_html(INFERENCE_RUNNERS.get("amd", {}), "AMD", "#4A148C")
_inf_run_rows_html = _amd_run_rows if _amd_run_rows else "<tr><td colspan='5' style='color:#999;text-align:center'>No runner data available</td></tr>"

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
  <a href="#inference-runners" style="color:#CE93D8">Inf Runners</a>
  <span class="nav-divider"></span>
  <a href="#data-sources">Data Sources</a>
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
  <td>pull_request: opened / synchronized / labeled</td>
  <td>Every PR</td>
  <td>
    <b>standard</b> = full unit suite<br>
    <small>&#x2192; rocm-libraries / rocm-systems component PRs</small><br><br>
    <b>quick</b> = smoke/sanity only<br>
    <small>&#x2192; TheRock infra/build PRs &bull; default when no <code>test:*</code> label</small>
  </td>
  <td>
    <span class="tag">gfx94X-dcgpu</span> <b>Build + Test</b> (MI300X/MI325X)<br>
    <span class="tag">gfx110X</span> <span class="tag">gfx1151</span> <span class="tag">gfx120X</span> <b>Build-only</b> (<code>nightly_check_only</code>)
  </td>
  <td>
    <span class="tag tag-win">gfx1151</span> <b>Build-only</b> (<code>nightly_check_only</code> on Windows too)
  </td>
  <td>PyTorch torch package only (no wheel upload)<br><b>No JAX in PR CI</b></td>
  <td>Ubuntu 22.04 LTS<br><small>(OSSCI scale pool)</small></td>
  <td>Windows 11<br><small>(azure-windows-11-* runners)</small></td>
</tr>
<tr class="tier-row" style="background:#f7faff">
  <td>Post-commit<br><small>(Submodule Bump)</small></td>
  <td>push to main / release/therock-* branches<br><small>Fires on every merged commit incl. submodule bumps from rocm-libraries or rocm-systems</small></td>
  <td>Every merged commit</td>
  <td><b>quick</b> = smoke/sanity only</td>
  <td>
    <span class="tag">gfx94X-dcgpu</span> <b>Build + Test</b><br>
    <span class="tag">gfx950-dcgpu</span> <b>Build + Test</b> (MI355X &mdash; postsubmit matrix only)<br>
    <span class="tag">gfx110X</span> <span class="tag">gfx1151</span> <span class="tag">gfx120X</span> <b>Build-only</b>
  </td>
  <td>
    <span class="tag tag-win">gfx1151</span> <b>Build-only</b>
  </td>
  <td>PyTorch torch package only<br>ROCm Python wheels (Ubuntu 24.04 + UBI10 smoke)<br><b>No JAX</b></td>
  <td>Ubuntu 22.04 LTS</td>
  <td>Windows 11</td>
</tr>
<tr class="tier-row">
  <td>CI Nightly</td>
  <td>ci_nightly.yml + ci_nightly_pytorch_full_test.yml (schedule)</td>
  <td>02:00 UTC ({_utc_to_pt(2)}) daily (ROCm)<br>12:00 UTC ({_utc_to_pt(12)}) daily (PyTorch full)</td>
  <td><b>comprehensive</b> = full + integration (ROCm)<br><b>full</b> = complete suite (PyTorch)</td>
  <td>
    <span class="tag">gfx94X</span> <span class="tag">gfx950</span> <span class="tag">gfx90a</span>
    <span class="tag">gfx103X</span> <span class="tag">gfx110X</span> <span class="tag">gfx1150</span>
    <span class="tag">gfx1151</span> <span class="tag">gfx1153</span> <span class="tag">gfx120X</span> &mdash; all <b>Build + Test</b><br>
    <small><i>gfx900/906/908/101X &mdash; Build-only (no HW runners)</i></small>
  </td>
  <td>
    <span class="tag tag-win">gfx1151</span> <span class="tag tag-win">gfx110X</span>
    <span class="tag tag-win">gfx103X</span> <span class="tag tag-win">gfx120X</span> &mdash; all <b>Build + Test</b>
  </td>
  <td>PyTorch: all 5 versions &times; 5 Python vers &times; all families<br>JAX: all 4 versions &times; 4 Python vers<br>Triton + Apex (Linux)</td>
  <td>Ubuntu 22.04 LTS</td>
  <td>Windows 11</td>
</tr>
<tr class="tier-row" style="background:#f7faff">
  <td>ASAN / TSAN</td>
  <td>ci_asan.yml / ci_tsan.yml (schedule)</td>
  <td>02:00 UTC ({_utc_to_pt(2)}) daily</td>
  <td><b>quick</b> = smoke/sanity only<br><small>Same suite as Post-commit but with sanitizer build</small></td>
  <td><span class="tag">gfx94X-dcgpu</span> <span class="tag">gfx950-dcgpu</span> &mdash; <b>Build + Test</b></td>
  <td>&mdash;</td>
  <td>None (sanitizer build validation only)</td>
  <td>Ubuntu 22.04 LTS<br><small>(rocm-asan-mi325-sandbox)</small></td>
  <td>&mdash;</td>
</tr>
<tr class="tier-row">
  <td>Release</td>
  <td>workflow_dispatch (rockrel or manual)</td>
  <td>On-demand: dev / nightly / prerelease</td>
  <td>quick / none<br><small>(tests not yet fully wired in multi_arch_release)</small></td>
  <td>
    <span class="tag">gfx94X</span> <span class="tag">gfx950</span> <span class="tag">gfx90a</span>
    <span class="tag">gfx103X</span> <span class="tag">gfx110X</span> <span class="tag">gfx1150</span>
    <span class="tag">gfx1151</span> <span class="tag">gfx1153</span> <span class="tag">gfx120X</span> &mdash; <b>Build + Test</b> (quick)<br>
    <small><i>gfx900/906/908/101X &mdash; Build-only (no HW runners)</i></small>
  </td>
  <td>
    <span class="tag tag-win">gfx1151</span> <span class="tag tag-win">gfx110X</span>
    <span class="tag tag-win">gfx103X</span> <span class="tag tag-win">gfx120X</span> &mdash; <b>Build + Test</b> (quick)
  </td>
  <td>PyTorch all 5 versions &times; all Pythons<br>JAX all 4 versions<br>ROCm tarballs to S3</td>
  <td>Ubuntu 22.04 LTS + RHEL 8.8/9.5 + SLES 15.6</td>
  <td>Windows 11</td>
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

<h3 style="margin:20px 0 8px 0;font-size:13px;color:#444;font-weight:600">Component CI Matrix — Unique Server Counts by Tier</h3>
<div class="tbl-wrap" style="margin-bottom:6px"><table class="fw-table fw-server-table">
<thead><tr>
  <th>CI Tier</th>
  <th>Pool Type</th>
  <th style="text-align:center">Count</th>
  <th>Azure Build Pool (no GPU)</th>
  <th>Physical GPU Machines</th>
  <th>Runner Labels &amp; Counts</th>
  <th>Notes</th>
</tr></thead>
<tbody>

<!-- Shared Azure Build Pool row -->
<tr style="background:#FFF9E6">
  <td rowspan="2" style="font-weight:700;color:#555;vertical-align:middle;text-align:center;border-left:4px solid #F9A825">All Tiers</td>
  <td>Azure Build Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">cloud VMs, no GPU — compile &amp; package only</span></td>
  <td style="text-align:center"><b>{_build_vms}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">VMs (snapshot)</span></td>
  <td style="text-align:center"><b>{_runner_counts.get('azure-linux-scale-rocm',0)}</b> Linux VMs<br>+<br><b>{_runner_counts.get('azure-windows-scale-rocm',0)}</b> Windows VMs</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td><code>azure-linux-scale-rocm</code> = <b>{_runner_counts.get('azure-linux-scale-rocm',0)}</b> &bull; <code>azure-windows-scale-rocm</code> = <b>{_runner_counts.get('azure-windows-scale-rocm',0)}</b></td>
  <td style="font-size:12.5px;color:#555">Shared across all tiers; elastic — can scale beyond snapshot count under queue pressure</td>
</tr>
<tr style="font-weight:700;background:#F5F0D8">
  <td>Build Subtotal</td>
  <td style="text-align:center;font-size:13px"><b>{_build_vms}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} VMs total</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_runner_counts.get('azure-linux-scale-rocm',0)} Linux + {_runner_counts.get('azure-windows-scale-rocm',0)} Windows Azure VMs — no GPU hardware involved</td>
</tr>

<!-- Pre-commit rows -->
<tr style="background:#EBF3FB">
  <td rowspan="2" style="font-weight:700;color:#1565C0;vertical-align:middle;text-align:center;border-left:4px solid #1565C0">&#128196; Pre-commit<br>(PR)</td>
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">2 physical runner types</span></td>
  <td style="text-align:center"><b>{_pc_gpu_nodes}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">physical</span></td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_pc_gpu_nodes}</b> unique nodes</td>
  <td style="font-size:10.5px;line-height:1.7">
    linux-gfx942-1gpu-ossci-rocm (gfx94X) = <b>{_runner_counts.get('linux-gfx942-1gpu-ossci-rocm',0)}</b><br>
    windows-gfx1151-gpu-rocm (gfx1151, build-only) = <b>{_runner_counts.get('windows-gfx1151-gpu-rocm',0)}</b>
  </td>
  <td style="font-size:12.5px;color:#555">gfx94X: Build + Test &bull; gfx1151 Win: Build-only (nightly_check_only)</td>
</tr>
<tr style="font-weight:700;background:#D0E8F8">
  <td>Pre-commit Subtotal</td>
  <td style="text-align:center;font-size:13px;color:#1565C0"><b>{_pc_gpu_nodes}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} shared build VMs</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_pc_gpu_nodes} physical GPU</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_build_vms} Azure build VMs + <b>{_pc_gpu_nodes}</b> physical GPU machines = <b>{_build_vms + _pc_gpu_nodes}</b> total</td>
</tr>

<!-- Post-commit rows -->
<tr style="background:#EBF5EB">
  <td rowspan="2" style="font-weight:700;color:#2E7D32;vertical-align:middle;text-align:center;border-left:4px solid #2E7D32">&#10003; Post-commit<br>(Sub Bump)</td>
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">3 physical runner types</span></td>
  <td style="text-align:center"><b>{_po_gpu_nodes}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">physical</span></td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_po_gpu_nodes}</b> unique nodes</td>
  <td style="font-size:10.5px;line-height:1.7">
    linux-gfx942-1gpu-ossci-rocm (gfx94X) = <b>{_runner_counts.get('linux-gfx942-1gpu-ossci-rocm',0)}</b><br>
    linux-mi355-1gpu-ossci-rocm (gfx950 / MI355X) = <b>{_runner_counts.get('linux-mi355-1gpu-ossci-rocm',0)}</b><br>
    windows-gfx1151-gpu-rocm (gfx1151, build-only) = <b>{_runner_counts.get('windows-gfx1151-gpu-rocm',0)}</b>
  </td>
  <td style="font-size:12.5px;color:#555">Adds gfx950 (MI355X) vs Pre-commit; gfx1151 Win remains build-only</td>
</tr>
<tr style="font-weight:700;background:#C8E6C9">
  <td>Post-commit Subtotal</td>
  <td style="text-align:center;font-size:13px;color:#2E7D32"><b>{_po_gpu_nodes}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} shared build VMs</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_po_gpu_nodes} physical GPU</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_build_vms} Azure build VMs + <b>{_po_gpu_nodes}</b> physical GPU machines = <b>{_build_vms + _po_gpu_nodes}</b> total</td>
</tr>

<!-- Nightly rows -->
<tr style="background:#FFF3E0">
  <td rowspan="2" style="font-weight:700;color:#E65100;vertical-align:middle;text-align:center;border-left:4px solid #E65100">&#127769; CI Nightly</td>
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">{_ni_runner_types} physical runner types</span></td>
  <td style="text-align:center"><b>{_ni_gpu_nodes}</b><br><span style="font-weight:400;font-size:11.5px;color:#777">physical</span></td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_ni_gpu_nodes}</b> unique nodes</td>
  <td style="font-size:10.5px;line-height:1.7">
    linux-gfx942-1gpu-ossci-rocm (gfx94X) = <b>{_runner_counts.get('linux-gfx942-1gpu-ossci-rocm',0)}</b> &bull;
    linux-gfx942-8gpu-ossci-rocm (gfx94X 8-GPU) = <b>{_runner_counts.get('linux-gfx942-8gpu-ossci-rocm',0)}</b><br>
    linux-mi355-1gpu-ossci-rocm (gfx950) = <b>{_runner_counts.get('linux-mi355-1gpu-ossci-rocm',0)}</b> &bull;
    linux-gfx90a-gpu-rocm (gfx90a) = <b>{_runner_counts.get('linux-gfx90a-gpu-rocm',0)}</b><br>
    linux-gfx1030-gpu-rocm (gfx103X) = <b>{_runner_counts.get('linux-gfx1030-gpu-rocm',0)}</b> &bull;
    linux-gfx110X-gpu-rocm (gfx110X) = <b>{_runner_counts.get('linux-gfx110X-gpu-rocm',0)}</b> &bull;
    windows-gfx110X-gpu-rocm = <b>{_runner_counts.get('windows-gfx110X-gpu-rocm',0)}</b><br>
    linux-gfx1150-gpu-rocm (gfx1150) = <b>{_runner_counts.get('linux-gfx1150-gpu-rocm',0)}</b> &bull;
    linux-gfx1151-gpu-rocm (gfx1151 L) = <b>{_runner_counts.get('linux-gfx1151-gpu-rocm',0)}</b> &bull;
    windows-gfx1151-gpu-rocm (gfx1151 W) = <b>{_runner_counts.get('windows-gfx1151-gpu-rocm',0)}</b><br>
    linux-gfx1153-gpu-rocm (gfx1153) = <b>{_runner_counts.get('linux-gfx1153-gpu-rocm',0)}</b> &bull;
    linux-gfx120X-gpu-rocm (gfx120X) = <b>{_runner_counts.get('linux-gfx120X-gpu-rocm',0)}</b> &bull;
    windows-gfx1030-gpu-rocm (gfx103X W) = <b>{_runner_counts.get('windows-gfx1030-gpu-rocm',0)}</b>
  </td>
  <td style="font-size:12.5px;color:#555">Full GPU family coverage; all unique physical machines, each counted once</td>
</tr>
<tr style="font-weight:700;background:#FFE0B2">
  <td>Nightly Subtotal</td>
  <td style="text-align:center;font-size:13px;color:#E65100"><b>{_ni_gpu_nodes}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_build_vms} shared build VMs</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_ni_gpu_nodes} physical GPU</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_build_vms} Azure build VMs + <b>{_ni_gpu_nodes}</b> physical GPU machines = <b>{_build_vms + _ni_gpu_nodes}</b> total</td>
</tr>

<!-- Grand Total -->
<tr style="font-weight:700;background:#37474F;color:#fff">
  <td colspan="2" style="text-align:center;font-size:13px;letter-spacing:0.3px">Grand Total (all tiers, unique)</td>
  <td style="text-align:center;font-size:13px"><b>{_build_vms + _ni_gpu_nodes}</b></td>
  <td style="text-align:center;font-size:12px">{_build_vms} VMs<br><span style="font-weight:400;font-size:11.5px;opacity:0.85">(Azure, no GPU)</span></td>
  <td style="text-align:center;font-size:12px"><b>{_ni_gpu_nodes}</b> physical<br><span style="font-weight:400;font-size:11.5px;opacity:0.85">unique GPU machines</span></td>
  <td colspan="2" style="font-size:12.5px;opacity:0.9">{_build_vms} Azure build VMs (cloud, no GPU) + {_ni_gpu_nodes} unique physical GPU machines = <b>{_build_vms + _ni_gpu_nodes}</b> &nbsp;&bull;&nbsp; <span style="font-weight:400">GPU node counts cumulative across tiers — each physical machine counted once</span></td>
</tr>

</tbody>
</table></div>
<p style="font-size:10.5px;color:#777;margin:4px 0 16px 4px">
  <b>Azure Build Pool</b>: Cloud-managed VMs with no GPU — used exclusively for compile, package, and artifact jobs. VM counts are point-in-time snapshots; elastic pools can provision beyond this number under load.<br>
  <b>Physical GPU counts</b>: Unique machines counted once regardless of how many tiers use them. Pre-commit uses {_pc_gpu_nodes}, Post-commit adds MI355X for {_po_gpu_nodes}, Nightly expands to all {_ni_gpu_nodes} GPU machines across {_ni_runner_types} runner types.
</p>
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
  <td><small>linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-mi355-1gpu-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br><i>gfx1153: excluded entirely</i></small></td>
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
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-mi355-1gpu-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
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
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-mi355-1gpu-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
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
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-mi355-1gpu-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
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
  <td><small>Linux: linux-gfx942-1gpu-ossci-rocm (gfx94X)<br>linux-mi355-1gpu-ossci-rocm (gfx950)<br>linux-gfx90a-gpu-rocm (gfx90a)<br>linux-gfx1030-gpu-rocm (gfx103X)<br>linux-gfx110X-gpu-rocm (gfx110X)<br>linux-gfx1150-gpu-rocm (gfx1150)<br>linux-gfx1151-gpu-rocm (gfx1151)<br>linux-gfx1153-gpu-rocm (gfx1153)<br>linux-gfx120X-gpu-rocm (gfx120X)<br>linux-gfx942-8gpu-ossci-rocm (distributed, 3 shards)<br>Windows: windows-gfx1151-gpu-rocm (gfx1151)<br>windows-gfx110X-gpu-rocm (gfx110X)<br>windows-gfx1030-gpu-rocm (gfx103X)<br>windows-gfx120X-gpu-rocm (gfx120X)</small></td>
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
     SERVER COUNT DETAILS
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="server-counts">
<h2>Framework Runner &amp; Server Count Details</h2>
<div class="tbl-wrap" style="margin-bottom:18px"><table class="fw-table fw-server-table">
<thead><tr>
  <th>Framework</th>
  <th>Pool</th>
  <th>Count</th>
  <th>Build (VMs)</th>
  <th>GPU Test (Physical)</th>
  <th>Runner Labels &amp; Counts</th>
  <th>Coverage</th>
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
  <td>GPU Test Pool<br><span style="font-weight:400;font-size:11.5px;color:#777">13 physical runner types</span></td>
  <td style="text-align:center"><b>{_pt_gpu_total}</b> physical</td>
  <td style="text-align:center;color:#aaa">&mdash;</td>
  <td style="text-align:center"><b>{_pt_gpu_total}</b> across {len(_pt_gpu_runners)} runner types</td>
  <td style="font-size:10.5px;line-height:1.6">{_pt_gpu_runner_breakdown}</td>
  <td>{_pt_combinations}</td>
</tr>
<tr class="fw-pytorch" style="font-weight:700;background:#D0E8F8">
  <td>Total</td>
  <td style="text-align:center;color:#1F4E79"><b>{_pt_total_servers}</b></td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_pt_build_servers} VMs (build)</td>
  <td style="text-align:center;font-weight:400;font-size:12.5px">{_pt_gpu_total} physical (GPU test)</td>
  <td colspan="2" style="color:#555;font-size:12.5px">{_pt_build_servers} build VMs + {_pt_gpu_total} physical GPU machines = <b>{_pt_total_servers}</b> &nbsp;(mixed: VMs + physical)</td>
</tr>
<tr class="fw-jax">
  <td rowspan="2" style="font-weight:700;color:#2E7D32;vertical-align:middle;text-align:center">JAX</td>
  <td>Build + Test<br><span style="font-weight:400;font-size:11.5px;color:#777">shared build VM pool</span></td>
  <td style="text-align:center"><b>{_jax_gpu_servers}</b> physical<br><span style="font-weight:400;font-size:11.5px;color:#777">(dedicated GPU)</span></td>
  <td style="color:#777;font-size:10.5px">Shared with PyTorch<br><span style="font-size:11.5px">azure-linux-scale-rocm</span><br><span style="font-size:11.5px">(VMs, not counted separately)</span></td>
  <td style="text-align:center"><b>{_jax_gpu_servers}</b> physical<br><span style="font-size:11.5px">(gfx94X only)</span></td>
  <td>linux-gfx942-1gpu-ossci-rocm = <b>{_jax_gpu_servers}</b> physical &nbsp;<span style="color:#888;font-size:10.5px">| Build: shared azure-linux-scale-rocm VMs</span></td>
  <td>{_jax_combinations}</td>
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
<p style="font-size:10.5px;color:#777;margin:4px 0 16px 4px">
  <b>Count</b>: VM instance counts are point-in-time snapshots from the runner fleet; elastic pools can provision beyond this number under load.<br>
  <b>Build VMs</b>: Azure-managed virtual machines with no GPU — 2 pools total (<code>azure-linux-scale-rocm</code>, <code>azure-windows-scale-rocm</code>). Physical server count underneath is managed by Azure and not exposed.
</p>
</div>
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
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     INFERENCE RUNNER INVENTORY
════════════════════════════════════════════════════════════════════ -->
<div class="section" id="inference-runners" style="border-left:5px solid #4E342E">
<h2 style="color:#4E342E">&#128295; Inference Runner Inventory</h2>
<p class="inf-source">AMD runner pools (ROCm/InferenceMAX_rocm)</p>
<div class="tbl-wrap"><table>
<thead><tr class="hdr-infr">
  <th style="vertical-align:middle">Ecosystem</th><th style="vertical-align:middle">GPU Type</th><th style="vertical-align:middle">Runner Labels</th>
  <th style="vertical-align:middle;text-align:center">Node Count</th><th style="vertical-align:middle">Cluster Type</th>
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
  <code>fetch_rocm_data.py</code> pulls live data from four GitHub repositories via the
  <a href="https://docs.github.com/en/rest/repos/contents" target="_blank" rel="noopener">GitHub REST API</a>.
  With <code>GITHUB_TOKEN</code> set it uses authenticated calls (5 000 req/hr); without it, unauthenticated
  calls are used (60 req/hr) with automatic fallback to local clones where available.
</p>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:18px">

<div style="background:#E3F2FD;border-radius:8px;padding:16px 20px;border-left:4px solid #1565C0">
  <div style="font-weight:700;font-size:13px;color:#1565C0;margin-bottom:10px">
    &#128279; Source 1 &mdash; <a href="https://github.com/ROCm/TheRock" target="_blank" rel="noopener" style="color:#1565C0">ROCm/TheRock</a>
  </div>
  <table style="width:100%;font-size:12.5px;border-collapse:collapse">
    <thead><tr><th style="text-align:left;padding:4px 8px;background:#1565C0;color:#fff">File</th><th style="text-align:left;padding:4px 8px;background:#1565C0;color:#fff">What it populates</th></tr></thead>
    <tbody>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/TheRock/blob/main/amdgpu_family_matrix.py" target="_blank" rel="noopener">amdgpu_family_matrix.py</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">Runner labels per GPU family, GPU ISA strings (gfx94X, gfx950, &hellip;), nightly-only flags</td></tr>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml" target="_blank" rel="noopener">BUILD_TOPOLOGY.toml</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">Component &rarr; super-repo mapping (rocm-libraries / rocm-systems / TheRock)</td></tr>
      <tr><td style="padding:4px 8px;border-bottom:1px solid #ddd"><a href="https://github.com/ROCm/TheRock/blob/main/.gitmodules" target="_blank" rel="noopener">.gitmodules</a></td><td style="padding:4px 8px;border-bottom:1px solid #ddd">Direct submodule list — identifies components tested inside TheRock itself</td></tr>
      <tr><td style="padding:4px 8px"><a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml" target="_blank" rel="noopener">ci_nightly.yml</a></td><td style="padding:4px 8px">Nightly schedule time, GPU family test matrix for the nightly tier</td></tr>
    </tbody>
  </table>
  <div style="font-size:12.5px;color:#555;margin-top:8px">
    <b>Workflow files also used (for CI Tiers section):</b>
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml" target="_blank" rel="noopener">ci.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_postsubmit.yml" target="_blank" rel="noopener">ci_postsubmit.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_asan.yml" target="_blank" rel="noopener">ci_asan.yml</a> &bull;
    <a href="https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_release.yml" target="_blank" rel="noopener">multi_arch_release.yml</a>
  </div>
</div>

<div style="background:#E8F5E9;border-radius:8px;padding:16px 20px;border-left:4px solid #2E7D32">
  <div style="font-weight:700;font-size:13px;color:#2E7D32;margin-bottom:10px">
    &#128279; Source 2 &mdash; <a href="https://github.com/ROCm/rocm-libraries" target="_blank" rel="noopener" style="color:#2E7D32">ROCm/rocm-libraries</a>
  </div>
  <p style="font-size:12.5px;margin:0">
    <b>Endpoint:</b> <code>projects/</code> directory listing via
    <a href="https://api.github.com/repos/ROCm/rocm-libraries/contents/projects" target="_blank" rel="noopener">GitHub API</a><br>
    <b>Populates:</b> All library component names (rocBLAS, hipBLAS, MIOpen, rocFFT, &hellip;).
    Every subdirectory in <code>projects/</code> is treated as an active CI component.
  </p>
</div>

<div style="background:#FFF8E1;border-radius:8px;padding:16px 20px;border-left:4px solid #F57C00">
  <div style="font-weight:700;font-size:13px;color:#E65100;margin-bottom:10px">
    &#128279; Source 3 &mdash; <a href="https://github.com/ROCm/rocm-systems" target="_blank" rel="noopener" style="color:#E65100">ROCm/rocm-systems</a>
  </div>
  <p style="font-size:12.5px;margin:0">
    <b>Endpoint:</b> <code>projects/</code> directory listing via
    <a href="https://api.github.com/repos/ROCm/rocm-systems/contents/projects" target="_blank" rel="noopener">GitHub API</a><br>
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
    (1) GitHub API when <code>GITHUB_TOKEN</code> is set &rarr;
    (2) Local clone at <code>InferenceMAX_rocm/</code> &rarr;
    (3) Graceful skip with <code>WARN</code> if neither available
  </div>
</div>

</div><!-- end grid -->

<div style="margin-top:18px;background:#f5f5f5;border-radius:6px;padding:12px 18px;font-size:12.5px;color:#555">
  <b>Fetch pipeline:</b>
  GitHub APIs / Local clones &rarr;
  <code>fetch_rocm_data.py</code> &rarr;
  <code>rocm_ci_data.py</code> (intermediate snapshot) &rarr;
  <code>generate_rocm_html.py</code> + <code>generate_rocm_cicd.py</code> &rarr;
  <b>ROCm_CICD_Comprehensive.html</b> + <b>ROCm_CICD_Comprehensive.xlsx</b>
</div>

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
    e.preventDefault();
    const id=a.getAttribute('href').slice(1);
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
