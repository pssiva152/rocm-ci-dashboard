#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_snapshots.py
===================
Manually create / refresh the snapshot files so they can be committed to
GitHub and used by anyone who runs the report without a GitHub token or
SSH access to InferenceMAX_rocm.

    python create_snapshots.py

Outputs (written next to this script):
    rocm_ci_data.py              — full data module (COMPONENTS, RUNNER_DATA,
                                   TIER_DATA, FW_DATA, WH_DATA, INFERENCEMAX_DATA,
                                   INFERENCE_RUNNERS) sourced entirely from the
                                   static data in the two generator scripts.
                                   Commit this file so others get the full dataset.

    inferencemax_snapshot.json   — InferenceMAX benchmark configs + runner pools
                                   with a timestamp, used as the 4th-tier fallback
                                   when no local clone is present.

    therock_ci_snapshot.json     — minimal marker file so fetch_rocm_data.py
                                   recognises a snapshot run; actual data comes
                                   from rocm_ci_data.py.

How data is sourced
-------------------
rocm_ci_data.py
  COMPONENTS, RUNNER_DATA, TIER_DATA  — exec'd from generate_rocm_html.py static
                                        data (already has all gfx / runner / tier
                                        info baked in).
  FW_DATA, WH_DATA                   — extracted verbatim from generate_rocm_cicd.py.
  INFERENCEMAX_DATA, INFERENCE_RUNNERS — parsed from local InferenceMAX_rocm/ clone,
                                         or re-used from existing inferencemax_snapshot.json.

inferencemax_snapshot.json
  Parsed from local InferenceMAX_rocm/ clone (preferred), or re-stamps the
  existing snapshot if no clone is found.

If you want everything fetched live from GitHub instead, run:
    export GITHUB_TOKEN=ghp_...
    python fetch_rocm_data.py
That regenerates all three files automatically.
"""

import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


# ── Timestamp ─────────────────────────────────────────────────────────────────
def _now_pt() -> str:
    try:
        import zoneinfo
        _pt = zoneinfo.ZoneInfo("America/Los_Angeles")
    except ImportError:
        _pt = datetime.timezone(datetime.timedelta(hours=-7))
    return datetime.datetime.now(_pt).strftime("%Y-%m-%d %I:%M %p %Z").lstrip("0")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Exec the HTML generator's data section to get static COMPONENTS /
#    RUNNER_DATA / TIER_DATA (includes all gfx families and runner labels).
# ══════════════════════════════════════════════════════════════════════════════
def _exec_html_data() -> dict:
    """
    Exec generate_rocm_html.py up to just before the HTML template string to
    capture COMPONENTS, RUNNER_DATA, and any other data constants.

    TIER_DATA is not defined in generate_rocm_html.py — it lives in
    generate_rocm_cicd.py and is fetched separately by _exec_cicd_tier_data().
    """
    html_gen = HERE / "generate_rocm_html.py"
    if not html_gen.exists():
        print("ERROR: generate_rocm_html.py not found", file=sys.stderr)
        sys.exit(1)
    src_lines = html_gen.read_text(encoding="utf-8").splitlines(keepends=True)
    # Stop just before the HTML template string (line starting with "HTML = f")
    end = next(
        (i for i, l in enumerate(src_lines) if l.startswith("HTML = f")),
        893,
    )
    # Temporarily hide rocm_ci_data.py so the exec uses only static defaults
    ci_data = HERE / "rocm_ci_data.py"
    ci_data_hidden = HERE / "_rocm_ci_data_hidden.py"
    _hidden = False
    if ci_data.exists():
        ci_data.rename(ci_data_hidden)
        _hidden = True
    try:
        ns: dict = {
            "__file__": str(html_gen),
            "_imax_snapshot_ts":    None,
            "_therock_snapshot_ts": None,
        }
        exec("".join(src_lines[:end]), ns)  # noqa: S102
    finally:
        if _hidden:
            ci_data_hidden.rename(ci_data)
    return ns


def _exec_cicd_tier_data() -> list:
    """Extract TIER_DATA from generate_rocm_cicd.py by exec-ing its data section."""
    cicd_gen = HERE / "generate_rocm_cicd.py"
    src_lines = cicd_gen.read_text(encoding="utf-8").splitlines(keepends=True)
    # Stop just before Sheet 1 construction (after TIER_DATA closes)
    end = next(
        (i for i, l in enumerate(src_lines) if l.strip().startswith("_PT_BUILD_L")),
        172,
    )
    ns: dict = {"__file__": str(cicd_gen)}
    # exec needs COMPONENTS etc. — just capture TIER_DATA block via _extract_block
    tier_block = _extract_block(cicd_gen.read_text(encoding="utf-8"), "TIER_DATA")
    exec(tier_block, ns)  # noqa: S102
    return ns.get("TIER_DATA", [])


# ══════════════════════════════════════════════════════════════════════════════
# 2. Extract FW_DATA and WH_DATA verbatim from generate_rocm_cicd.py
#    (same logic as fetch_rocm_data._extract_block).
# ══════════════════════════════════════════════════════════════════════════════
def _extract_block(src: str, var_name: str) -> str:
    lines = src.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{var_name} = ["):
            start = i
            break
    if start is None:
        return f"{var_name} = []"
    depth, end = 0, start
    for i in range(start, len(lines)):
        depth += lines[i].count("[") - lines[i].count("]")
        if depth <= 0 and i > start:
            end = i
            break
    return "".join(lines[start: end + 1])


def _extract_fw_wh(cicd_src: str) -> tuple[str, str]:
    """
    Extract FW_DATA and WH_DATA with ALL their helper constants.

    Helper constants (_PT_BUILD_L, _PT_TEST_*, _JAX_BUILD, _JAX_TEST, _WH_SMOKE_*)
    are defined between TIER_DATA's closing bracket and the FW_DATA / WH_DATA blocks.
    We find the first helper line and include everything from there through the block.
    """
    lines = cicd_src.splitlines(keepends=True)

    fw_data_idx = next(
        (i for i, l in enumerate(lines) if l.strip().startswith("FW_DATA = [")), None
    )
    wh_data_idx = next(
        (i for i, l in enumerate(lines) if l.strip().startswith("WH_DATA = [")), None
    )

    # Find where the _PT_ / _JAX_ helper block starts before FW_DATA.
    # We scan backwards and stop when we hit the closing ']' of TIER_DATA,
    # which is the boundary between the previous data block and the helpers.
    fw_helper_start = fw_data_idx
    if fw_data_idx:
        for i in range(fw_data_idx - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped == "]":          # closing bracket of TIER_DATA
                fw_helper_start = i + 1
                break

    # Same for WH_DATA — helpers start after FW_DATA's closing bracket.
    wh_helper_start = wh_data_idx
    if wh_data_idx:
        for i in range(wh_data_idx - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped == "]":          # closing bracket of FW_DATA
                wh_helper_start = i + 1
                break

    fw_block = _extract_block(cicd_src, "FW_DATA")
    wh_block = _extract_block(cicd_src, "WH_DATA")

    fw_data_src = "".join(lines[fw_helper_start:fw_data_idx]) + fw_block
    wh_data_src = "".join(lines[wh_helper_start:wh_data_idx]) + wh_block
    return fw_data_src, wh_data_src


# ══════════════════════════════════════════════════════════════════════════════
# 3. Parse InferenceMAX data from local clone
# ══════════════════════════════════════════════════════════════════════════════
def _find_imax_dir() -> Path | None:
    for candidate in [HERE / "InferenceMAX_rocm", HERE.parent / "InferenceMAX_rocm"]:
        if candidate.is_dir():
            return candidate
    return None


def _parse_imax_local(imax_dir: Path) -> tuple[list, dict]:
    try:
        import yaml  # type: ignore
    except ImportError:
        print("ERROR: PyYAML is not installed.  Run:  pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    configs_dir  = imax_dir / ".github" / "configs"
    amd_yaml     = configs_dir / "amd-master.yaml"
    runners_yaml = configs_dir / "runners.yaml"

    if not amd_yaml.exists():
        print(f"  WARN: {amd_yaml} not found — no InferenceMAX data", file=sys.stderr)
        return [], {}

    with amd_yaml.open(encoding="utf-8") as f:
        amd_raw = yaml.safe_load(f)

    # amd-master.yaml is a flat dict: {benchmark_name: {image, model, model-prefix, ...}}
    imax_data = []
    for name, entry in amd_raw.items():
        if not isinstance(entry, dict):
            continue
        imax_data.append((
            name,
            entry.get("model", ""),
            entry.get("model-prefix", ""),
            entry.get("runner", ""),
            entry.get("precision", ""),
            entry.get("framework", ""),
            bool(entry.get("multinode", False)),
            entry.get("image", ""),
        ))

    inference_runners: dict = {"amd": {}}
    if runners_yaml.exists():
        with runners_yaml.open(encoding="utf-8") as f:
            run_raw = yaml.safe_load(f) or {}
        for pool_name, pool_cfg in run_raw.items():
            nodes = pool_cfg if isinstance(pool_cfg, list) else pool_cfg.get("runners", [])
            if nodes:
                inference_runners["amd"][pool_name] = nodes

    return imax_data, inference_runners


def _load_existing_imax_snapshot() -> tuple[list, dict]:
    existing = HERE / "inferencemax_snapshot.json"
    if existing.exists():
        try:
            snap = json.loads(existing.read_text(encoding="utf-8"))
            data    = [tuple(r) for r in snap.get("inferencemax_data", [])]
            runners = snap.get("inference_runners", {})
            print(f"  [InferenceMAX] Re-using existing snapshot ({len(data)} configs)")
            return data, runners
        except Exception as e:
            print(f"  [InferenceMAX] Could not read existing snapshot: {e}", file=sys.stderr)
    return [], {}


# ══════════════════════════════════════════════════════════════════════════════
# 4. Write rocm_ci_data.py
# ══════════════════════════════════════════════════════════════════════════════
def _repr_tuple(t: tuple) -> str:
    return "    " + repr(t)


def write_rocm_ci_data(
    components: list,
    runner_data: list,
    tier_data: list,
    fw_data_src: str,
    wh_data_src: str,
    imax_data: list,
    inference_runners: dict,
    snapshot_ts: str,
) -> Path:
    out = HERE / "rocm_ci_data.py"
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""Generated by create_snapshots.py from static generator data — do not edit manually."""',
        "",
        f"# Generated: {snapshot_ts}",
        "",
        "COMPONENTS = [",
    ]
    for c in components:
        lines.append(_repr_tuple(tuple(c)) + ",")
    lines += ["]", "", "RUNNER_DATA = ["]
    for r in runner_data:
        lines.append(_repr_tuple(tuple(r)) + ",")
    lines += ["]", "", "TIER_DATA = ["]
    for t in tier_data:
        lines.append(_repr_tuple(tuple(t)) + ",")
    lines += ["]", ""]
    lines.append(fw_data_src)
    lines.append("")
    lines.append(wh_data_src)
    lines.append("")
    lines.append("INFERENCEMAX_DATA = [")
    for row in imax_data:
        lines.append(_repr_tuple(tuple(row)) + ",")
    lines.append("]")
    lines.append("")
    lines.append("INFERENCE_RUNNERS = " + repr(inference_runners))
    lines.append("")
    lines.append("IMAX_SNAPSHOT_TS = None")
    lines.append(f"THEROCK_SNAPSHOT_TS = None")
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 5. Write snapshot JSON files
# ══════════════════════════════════════════════════════════════════════════════
def write_imax_snapshot(imax_data: list, inference_runners: dict, ts: str) -> Path:
    snap = {
        "timestamp": ts,
        "inferencemax_data": [list(r) for r in imax_data],
        "inference_runners": inference_runners,
    }
    out = HERE / "inferencemax_snapshot.json"
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_therock_snapshot(ts: str) -> Path:
    """
    Write a minimal marker so fetch_rocm_data.py's snapshot path is satisfied.
    The real data lives in rocm_ci_data.py which generators load directly.
    """
    snap = {
        "timestamp": ts,
        "_note": "Data sourced from static generate_rocm_html.py defaults via create_snapshots.py. "
                 "Run fetch_rocm_data.py with GITHUB_TOKEN for live data.",
        "matrix_src": "",
        "topology_src": "",
        "gitmodules_src": "",
        "nightly_yml": "",
        "lib_projects": [],
        "sys_projects": [],
    }
    out = HERE / "therock_ci_snapshot.json"
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 60)
    print("  Snapshot Creator")
    print("=" * 60)

    ts = _now_pt()

    # ── Step 1: static TheRock data from generators ───────────────────────────
    print("\n[1/4] Loading static data from generators ...")
    ns = _exec_html_data()
    components  = ns.get("COMPONENTS", [])
    runner_data = ns.get("RUNNER_DATA", [])
    tier_data   = _exec_cicd_tier_data()
    print(f"      COMPONENTS: {len(components)}  |  RUNNER_DATA: {len(runner_data)}  |  TIER_DATA: {len(tier_data)}")

    # Quick sanity check: runner labels should be populated
    gpu_runners = [r for r in runner_data if "gfx" in r[0] or "mi3" in r[0]]
    print(f"      GPU runners: {len(gpu_runners)}  (spot-check: {runner_data[0][0] if runner_data else 'EMPTY — check boundary'})")

    # ── Step 2: FW_DATA / WH_DATA from generate_rocm_cicd.py ─────────────────
    print("\n[2/4] Extracting FW_DATA / WH_DATA from generate_rocm_cicd.py ...")
    cicd_gen = HERE / "generate_rocm_cicd.py"
    if not cicd_gen.exists():
        print("ERROR: generate_rocm_cicd.py not found", file=sys.stderr)
        sys.exit(1)
    cicd_src = cicd_gen.read_text(encoding="utf-8")
    fw_data_src, wh_data_src = _extract_fw_wh(cicd_src)
    fw_lines = fw_data_src.count("\n")
    wh_lines = wh_data_src.count("\n")
    print(f"      FW_DATA: ~{fw_lines} lines  |  WH_DATA: ~{wh_lines} lines")

    # ── Step 3: InferenceMAX data ─────────────────────────────────────────────
    print("\n[3/4] Loading InferenceMAX data ...")
    imax_dir = _find_imax_dir()
    if imax_dir:
        print(f"      Using local clone: {imax_dir}")
        imax_data, inference_runners = _parse_imax_local(imax_dir)
    else:
        print("      No local InferenceMAX_rocm/ found — falling back to existing snapshot.")
        imax_data, inference_runners = _load_existing_imax_snapshot()
    print(f"      Benchmark configs: {len(imax_data)}  |  Runner pools: {len(inference_runners.get('amd', {}))}")

    # ── Step 4: Write outputs ─────────────────────────────────────────────────
    print("\n[4/4] Writing output files ...")

    ci_data_path = write_rocm_ci_data(
        components, runner_data, tier_data,
        fw_data_src, wh_data_src,
        imax_data, inference_runners,
        snapshot_ts=ts,
    )
    print(f"      Written: {ci_data_path}")

    imax_snap_path = write_imax_snapshot(imax_data, inference_runners, ts)
    print(f"      Written: {imax_snap_path}  ({len(imax_data)} configs)")

    tr_snap_path = write_therock_snapshot(ts)
    print(f"      Written: {tr_snap_path}  (marker only — data is in rocm_ci_data.py)")

    # ── Verify: run both generators to confirm everything works ───────────────
    print("\n── Verifying: regenerating HTML and Excel from fresh data ...")
    import subprocess
    for script in ("generate_rocm_html.py", "generate_rocm_cicd.py"):
        result = subprocess.run(
            [sys.executable, str(HERE / script)],
            capture_output=True, text=True, cwd=str(HERE),
        )
        last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if result.returncode == 0:
            print(f"      {script}: OK  ({last})")
        else:
            print(f"      {script}: FAILED", file=sys.stderr)
            print(result.stderr[-500:], file=sys.stderr)

    print()
    print("=" * 60)
    print("  Done.")
    print()
    print("  Commit these files to GitHub:")
    print("    rocm_ci_data.py")
    print("    inferencemax_snapshot.json")
    print("    therock_ci_snapshot.json")
    print()
    print("  Anyone who runs rocm_report_bundle.py without a token")
    print("  will use rocm_ci_data.py for the full dataset, with")
    print("  inferencemax_snapshot.json as the 4th-tier fallback.")
    print("=" * 60)


if __name__ == "__main__":
    main()
