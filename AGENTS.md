--- 
description: Persistent agent context for the ROCm CI/CD report generator project. Read this BEFORE making changes to understand the data flow, exec()-coupling between scripts, and common gotchas.
alwaysApply: true
---

# AGENTS.md — ROCm CI/CD Report Generator

This file is the synthesized "mental model" for an AI agent working in this repo. It complements (does **not** replace) `README.md` (user-facing docs) and `CLAUDE.md` (project overview). Read this first; then `README.md` for user behaviour; then `CLAUDE.md` for high-level conventions.

## 1. What this project is, in one sentence

Three small Python scripts that read static + GitHub-fetched ROCm CI metadata and emit one interactive HTML report (`ROCm_CICD_Comprehensive.html`) and one 9-sheet Excel workbook (`ROCm_CICD_Comprehensive.xlsx`) describing AMD's full CI/CD topology (TheRock, rocm-libraries, rocm-systems, InferenceMAX_rocm).

There are **no tests, no linters, no build step, no package**. Just `pip install xlsxwriter` (and `pyyaml` if parsing a local InferenceMAX clone) and `python <script>.py`.

## 2. The exec()-coupling — the most important thing to understand

Three scripts share data via `exec()` of source slices. **Editing any of them carelessly breaks the others.**

| Script | What it does | How it gets data |
|---|---|---|
| `generate_rocm_html.py` | **Canonical data source.** Defines `COMPONENTS` (~73 tuples × 23 fields), `RUNNER_DATA` (23 rows × 11 fields), color palettes, GPU-family shorthands (`PC_L_94`, `NL_FULL`, `NLR_FULL`, etc.), then emits HTML. | Static literals; if `rocm_ci_data.py` exists it overrides `COMPONENTS`, `INFERENCEMAX_DATA`, `INFERENCE_RUNNERS` (see `generate_rocm_html.py:544-557`). |
| `generate_rocm_cicd.py` | Excel generator. Owns `TIER_DATA`, `FW_DATA`, `WH_DATA`, the `_PT_*`/`_JAX_*` helpers. | `exec()`s `generate_rocm_html.py` up to the line containing `"─── Summary counts"` (`generate_rocm_cicd.py:14-22`) to inherit `COMPONENTS`/`RUNNER_DATA`, then re-overrides `RUNNER_DATA`/`TIER_DATA` from `rocm_ci_data.py` if present. |
| `fetch_rocm_data.py` | Live fetcher. Hits the GitHub API for 4 repos, parses, regenerates `rocm_ci_data.py`, and re-runs both generators. | GitHub API + local `InferenceMAX_rocm/` clone fallback. Has its own `RUNNER_DATA` builder (`build_runner_data`) that emits **10-field tuples**, not 11 — see gotcha #2. |
| `create_snapshots.py` | Builds `rocm_ci_data.py` + the two JSON snapshot files from static generator data + local InferenceMAX clone. Runs both generators afterward to verify. | `exec()`s `generate_rocm_html.py` (hides `rocm_ci_data.py` first via rename, see `_exec_html_data`) up to the line starting with `"HTML = f"`, then text-extracts `TIER_DATA`/`FW_DATA`/`WH_DATA` from `generate_rocm_cicd.py` via bracket-counting (`_extract_block`). |
| `rocm_report_bundle.py` | User entry point. Copies all source files into a temp dir and runs them. **NOT self-contained** despite the docstring — needs sibling `.py` files. | Orchestrator; no data of its own. |
| `create_bundle.py` | Old base64-bundling tool that produces a *truly* self-contained `rocm_report_bundle.py`. Currently overwritten by the lightweight orchestrator version — only run if you intend to revert to base64-embedded mode. |

### Concrete exec() boundary lines (these change!)
- `generate_rocm_cicd.py:17-20` looks for the first line containing the comment marker `"─── Summary counts"` in `generate_rocm_html.py`. Fallback: line 560.
- `create_snapshots.py:_exec_html_data` looks for the first line starting with `"HTML = f"`. Fallback: line 893.
- `create_snapshots.py:_exec_cicd_tier_data` looks for the first line whose `lstrip()` starts with `"_PT_BUILD_L"`. Fallback: line 172.

**If you move/rename those marker lines, fix the fallbacks too.** The fallback line numbers are stale once code shifts.

## 3. Tuple schemas — count fields carefully

Wrong field counts cause silent misalignment. Confirmed schemas:

- **`COMPONENTS` (23 fields)** — defined in `generate_rocm_html.py:104-109`:
  ```
  (cat, sub, comp, repo, ci_en,
   pc_lgfx, pc_lr, pc_wgfx, pc_wr, pc_tt,        ← Pre-commit (5)
   po_lgfx, po_lr, po_wgfx, po_wr, po_tt,        ← Post-commit (5)
   ni_lgfx, ni_lr, ni_wgfx, ni_wr, ni_tt,        ← Nightly (5)
   plat, notes)                                    ← meta (2)
  ```
- **`RUNNER_DATA`**:
  - in `generate_rocm_html.py` and `rocm_ci_data.py` → **11 fields** (last is CSS class: `runner-linux` / `runner-windows` / `runner-build`)
  - in `generate_rocm_cicd.py` (its own static fallback) and `fetch_rocm_data.py` (`build_runner_data`) → **10 fields** (no CSS class)
  - The Excel generator handles **both** schemas — see commit `e4d940f` "Fix RUNNER_DATA unpack to handle both 10-field … and 11-field … tuple schemas". Maintain this dual unpack if you change the schema.
- **`TIER_DATA` (9 fields)**: `(tier_name, trigger, schedule, test_type, linux_gpu_families, windows_gpu_families, frameworks_built, distro, windows_distro)` — see `generate_rocm_cicd.py:103-141`.
- **`FW_DATA` (13 fields)**: `(fw, version, py_vers, distro, linux_pkgs, win_pkgs, branch, nightly_gpu, ci_test, ni_test, build_runner, test_runner, notes)` — see `generate_rocm_cicd.py:172-246`.
- **`INFERENCEMAX_DATA` (8 fields)** *(was 12 historically — see CLAUDE.md, but actual schema is 8)*: `(name, model, model_prefix, runner, precision, framework, multinode, image)` — see `rocm_ci_data.py:303-341`.
- **`INFERENCE_RUNNERS`**: `dict[str, dict[str, list[str]]]` keyed by ecosystem (`"amd"` / `"nvidia"`) → pool name → list of physical node labels.

> **CLAUDE.md states `INFERENCEMAX_DATA` is 12-field**, but the current code is 8-field. Treat CLAUDE.md as out of date on this — defer to `rocm_ci_data.py`.

## 4. Three runtime modes — match user setup before changing fetch logic

1. **Snapshot mode (default, no internet)** — `rocm_ci_data.py` is present and committed; generators load from it.
2. **Live fetch mode** — `GITHUB_TOKEN` is set; `fetch_rocm_data.py` rewrites `rocm_ci_data.py` and the two JSON snapshots, then runs both generators.
3. **Local InferenceMAX clone mode** — `./InferenceMAX_rocm/` exists; only InferenceMAX data is parsed locally (via PyYAML), TheRock data still comes from snapshot or API depending on token.

`rocm_report_bundle.py:103-126` selects the mode. The "local clone without token" path runs `fetch_rocm_data.py` with `GITHUB_TOKEN` removed from env so it skips API calls.

## 5. Data sources & where they end up

| Source repo | File / endpoint | Drives |
|---|---|---|
| `ROCm/TheRock` | `build_tools/github_actions/amdgpu_family_matrix.py` | Per-tier GPU family matrix → `TIER_DATA`, `RUNNER_DATA` test-runs-on labels |
| `ROCm/TheRock` | `BUILD_TOPOLOGY.toml` | Component → super-repo mapping |
| `ROCm/TheRock` | `.gitmodules` | Direct TheRock submodules |
| `ROCm/TheRock` | `.github/workflows/ci_nightly.yml` | Nightly cron schedule |
| `ROCm/rocm-libraries` | `projects/` directory listing | Library component discovery |
| `ROCm/rocm-systems` | `projects/` directory listing | Systems component discovery |
| `ROCm/InferenceMAX_rocm` | `.github/configs/amd-master.yaml` | `INFERENCEMAX_DATA` |
| `ROCm/InferenceMAX_rocm` | `.github/configs/runners.yaml` | `INFERENCE_RUNNERS` (split AMD/NVIDIA by `pool_name.startswith("mi")`) |

## 6. Snapshot file roles (don't confuse them)

| File | Critical? | Contents |
|---|---|---|
| `rocm_ci_data.py` | **Yes — commit it.** | All 7 datasets (COMPONENTS, RUNNER_DATA, TIER_DATA, FW_DATA, WH_DATA, INFERENCEMAX_DATA, INFERENCE_RUNNERS). This is what generators load. |
| `inferencemax_snapshot.json` | Secondary | InferenceMAX configs + runner pools cache, used by `fetch_rocm_data.py` as fallback. |
| `therock_ci_snapshot.json` | Marker only | Just a timestamp + empty fields. Real data is in `rocm_ci_data.py`. Don't put data here. |

## 7. Repo conventions & gotchas

- **Excel "Internal Only" MIP label** is injected automatically at write time in `generate_rocm_cicd.py`. Don't strip it unless going public.
- **AMD red `#CC0000` and dark `#1A1A1A`** are mandatory brand colors. Tier headers use blue (`#1565C0` PC), green (`#2E7D32` PO), orange (`#E65100` NI).
- **GPU family shorthands** (`PC_L_94`, `PCR_L`, `NL_FULL`, `NLR_FULL`, etc.) are defined at the top of `generate_rocm_html.py:37-101`. Components reuse these by reference — change the constant and every component using it updates.
- **`nightly_check_only_for_family`** is the matrix flag that means "build at PR/post-commit but only test at nightly". Reflected in HTML strings via `PC_L_TEST` and the `Build-only` suffixes.
- **Strix Halo Linux is "Build-only at PR/postsubmit, test at nightly"**, but Windows Strix Halo is "Build-only at PR/postsubmit, Build + Test at nightly". Keep these straight.
- **`gfx1153` (Krackan Point)** is currently disabled in CK due to instability since `7.12.0a20260214`. Keep in matrix but note in `notes` field.
- **`gfx115X` exclusion**: `hipSPARSELt`, `rocRoller` exclude all `gfx115X` (`gfx1150/1151/1152/1153`); reflected in their custom GPU family strings.
- **Windows Powershell, not bash**: this repo's working dir is on Windows under OneDrive. Use `Get-ChildItem` not `ls -la`.
- **Encoding**: scripts call `sys.stdout.reconfigure(encoding="utf-8")` at top — keep that, output contains `—`, `•`, `→`, etc.
- **`tomllib`** is used → Python 3.11+ required.
- **`projects/` are the canonical CI list** for `rocm-libraries` / `rocm-systems` — every subdirectory there is a CI component.
- **`.gitignore`** keeps `InferenceMAX_rocm/` (local clone) untracked. Don't add it.
- **Old artifact `ROCm_Components_CICD.xlsx`** still in folder — it's gitignored and superseded.

## 8. Common workflows

### Add or update a component
1. Edit the tuple in `generate_rocm_html.py` `COMPONENTS` (around line 110+). Use shorthand constants where possible.
2. Run `python create_snapshots.py` to refresh `rocm_ci_data.py` (and verify by re-running both generators).
3. Run `python rocm_report_bundle.py` (or the two generators directly) to produce updated HTML/Excel.
4. Commit `generate_rocm_html.py` + `rocm_ci_data.py` + `inferencemax_snapshot.json` + `therock_ci_snapshot.json` + the two output files.

### Refresh InferenceMAX benchmarks after upstream change
1. `git -C InferenceMAX_rocm pull` (or set `GITHUB_TOKEN` and run `fetch_rocm_data.py`).
2. `python create_snapshots.py` → updates `rocm_ci_data.py` and `inferencemax_snapshot.json`.
3. New configs auto-appear in HTML `#inferencemax` and Excel Sheet 6.

### Fully refresh from GitHub
```powershell
$env:GITHUB_TOKEN = "ghp_..."
python rocm_report_bundle.py
```
This runs `fetch_rocm_data.py` end-to-end, which writes both snapshots and both outputs.

## 9. Output file inventory

| File | Generated by | Purpose |
|---|---|---|
| `ROCm_CICD_Comprehensive.html` | `generate_rocm_html.py` | Single self-contained HTML, JS-filterable, includes all sections |
| `ROCm_CICD_Comprehensive.xlsx` | `generate_rocm_cicd.py` | 9-sheet workbook with AMD MIP "Internal Only" label |

### 9-sheet Excel layout
1. Component CI Matrix (per-tier blue/green/orange columns) + server-count summary table appended below
2. CI Tiers
3. Framework Detail (PyTorch + JAX)
4. Runner Inventory + Physical GPU Machines by Location summary + Framework Runner & Server Count Details
5. Wheel Artifact Publishing
6. InferenceMAX — AMD Benchmarks (red `#CC0000`)
7. Inference Runners (brown `#4E342E`) — both AMD (red badge) + NVIDIA (green badge) rows
8. InferenceMAX Workflows (purple-tinted)
9. Data Sources (grey `#78909C`)

## 10. Commit history quick-reference (most recent first)

| Commit | Notable change |
|---|---|
| `f519d25` | Split inference runners into AMD vs NVIDIA buckets (was lumping NVIDIA pools under `amd` key). |
| `c45892a` | Nav links with `http*` href no longer get `e.preventDefault()`. |
| `e46489f` | Regenerate HTML+xlsx with `rocm_ci_data.py` present so InferenceMAX sheets populate. |
| `b4a56d7` | Major: introduces `create_snapshots.py`, the snapshot pipeline, README rewrite, removes `<code>` tags from runner cells, adds Azure build VMs, sorts Runner Inventory by location, sheet 8→9. |
| `e4d940f` | Server count tables, "Azure Build Pool" rename, dual-schema `RUNNER_DATA` unpack, mi355x corrected to 10 nodes, 3 missing InferenceMAX configs added (34→37). |
| `c07d5a4` | Initial commit. |

## 11. MANDATORY: Regenerate + verify outputs after every change

After **any** change to `generate_rocm_html.py`, `generate_rocm_cicd.py`, `fetch_rocm_data.py`, `create_snapshots.py`, or `rocm_ci_data.py`, you MUST:

1. **Regenerate both outputs**:
   ```powershell
   python generate_rocm_html.py
   python generate_rocm_cicd.py
   ```
   (or `python rocm_report_bundle.py` to do both via the orchestrator)

2. **Verify both succeeded** — check the exit codes are 0 and the files were written:
   - `ROCm_CICD_Comprehensive.html`
   - `ROCm_CICD_Comprehensive.xlsx`

3. **Sanity-check the changed area**:
   - For HTML changes: `rg` the output file for the new/changed string to confirm it rendered.
   - For Excel changes: confirm file size changed and (if practical) note which sheet was affected.
   - For data changes: confirm the count/value in `rocm_ci_data.py` matches what's expected.

4. **Tell the user** the outputs were regenerated successfully so they can open them and visually verify.

5. **If the change touches data** (`COMPONENTS`, `RUNNER_DATA`, `TIER_DATA`, `FW_DATA`, `WH_DATA`, `INFERENCEMAX_DATA`, `INFERENCE_RUNNERS`): also run `python create_snapshots.py` to refresh `rocm_ci_data.py` and the JSON snapshots, then regenerate the outputs again from the refreshed snapshot.

Never end a turn that modified generator/data code without producing fresh `ROCm_CICD_Comprehensive.html` and `ROCm_CICD_Comprehensive.xlsx`. The user needs them to visually verify.

## 12. Things NOT to do

- Don't add tests, build configs, or CI files unless the user asks — this repo is intentionally minimal.
- Don't move the `"─── Summary counts"` or `"HTML = f"` marker lines without updating their fallback line numbers in the consuming scripts.
- Don't store actual CI data in `therock_ci_snapshot.json` — it's a marker; data lives in `rocm_ci_data.py`.
- Don't change `RUNNER_DATA` field count without updating both 10-field and 11-field unpack code paths in `generate_rocm_cicd.py`.
- Don't drop `pip install xlsxwriter` from instructions — it's the only hard dependency.
- Don't add emojis to generated reports unless explicitly requested.
- Don't commit `InferenceMAX_rocm/` (it's a local clone of a separate repo, gitignored).
- Don't commit `ROCm_Components_CICD.xlsx` (legacy, gitignored).
