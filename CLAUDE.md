# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

This is a Python-based documentation generator for AMD ROCm's CI/CD pipeline. It produces interactive HTML reports and Excel workbooks that catalog component CI coverage across GPU families, runner configurations, and test tiers (pre-commit, post-commit, nightly, ASAN, release).

## Running the Generators

Install the only external dependency first:
```bash
pip install xlsxwriter
```

Generate outputs (each script writes directly to the current directory):
```bash
python generate_rocm_html.py     # HTML interactive report
python generate_rocm_cicd.py     # Excel workbook (reuses HTML data)
```

There are no tests, linters, or build steps.

## Fetching Live Data from GitHub

`fetch_rocm_data.py` pulls current data from three GitHub repos on demand and regenerates both outputs:

```bash
python fetch_rocm_data.py
```

This script:
1. Fetches `amdgpu_family_matrix.py`, `BUILD_TOPOLOGY.toml`, `.gitmodules`, and workflow YAMLs from `ROCm/TheRock`
2. Fetches the `projects/` directory listings from `ROCm/rocm-libraries` and `ROCm/rocm-systems`
3. Updates runner labels and GPU family strings from the live matrix; discovers new components
4. Writes `rocm_ci_data.py` (an intermediate data module, not checked in)
5. Calls `generate_rocm_html.py` and `generate_rocm_cicd.py` which load from `rocm_ci_data.py` when it exists

**Optional: set `GITHUB_TOKEN` for higher API rate limits** (unauthenticated = 60 req/hr; token = 5000 req/hr):
```bash
export GITHUB_TOKEN=ghp_...
python fetch_rocm_data.py
```

**`rocm_ci_data.py`** — generated artifact written by `fetch_rocm_data.py`. When this file is present alongside the generators, both `generate_rocm_html.py` and `generate_rocm_cicd.py` load COMPONENTS (and RUNNER_DATA/TIER_DATA for the Excel generator) from it instead of their hardcoded static data. Delete it to revert to static data.

## Architecture

**`generate_rocm_html.py` is the canonical data source.** All component data, runner configs, and tier definitions live here.

**`generate_rocm_cicd.py` reuses HTML constants** by executing the first ~520 lines of `generate_rocm_html.py` via `exec()` to import `COMPONENTS`, `RUNNER_DATA`, `TIER_DATA`, and color palettes, then generates an xlsxwriter workbook mirroring the HTML layout.

### Core data structures (all defined in `generate_rocm_html.py`)

- **`COMPONENTS`** — list of ~70 tuples (23 fields each): `(category, subcategory, component_name, super_repo, ci_enabled, pre_commit_linux_gpu_families, pre_commit_runners, ..., notes)`. Categories: Libraries, Tools, Compilers, Runtime, iree-libs, Sysdeps, Frameworks.
- **`RUNNER_DATA`** — ~22 GPU/build runner configs with labels (e.g., `linux-gfx942-1gpu-ossci-rocm`), GPU families, shard counts, and timeouts.
- **`TIER_DATA`** — 6 CI tiers with trigger conditions, associated GPU families, and test types.
- **GPU family shorthands**: `gfx94X` (MI300X/MI325X), `gfx950` (MI355X), `gfx90a` (MI200), `gfx103X/110X/1150/1151/1153/120X` (RDNA families).

## InferenceMAX / InferenceX Integration

`fetch_rocm_data.py` also fetches benchmark CI data from two additional repos and adds them as new sheets/sections:

| Source | Data | Report sections |
|--------|------|-----------------|
| `ROCm/InferenceMAX_rocm` | AMD benchmark configs (MI300X/MI325X/MI355X), runner pools | Excel Sheet 6, HTML `#inferencemax` |
| `SemiAnalysisAI/InferenceX` | NVIDIA benchmark configs (H100/H200/B200/B300/GB200/GB300), runner pools | Excel Sheet 7, HTML `#inferencex` |

**Data source priority for InferenceMAX:**
1. GitHub API (`ROCm/InferenceMAX_rocm`) — if `GITHUB_TOKEN` is set
2. Local clone at `InferenceMAX_rocm/` (relative to this folder) or `../InferenceMAX_rocm/`

**Data source priority for InferenceX:**
1. GitHub API (`SemiAnalysisAI/InferenceX`) — if `GITHUB_TOKEN` is set (public repo)
2. `nvidia-master.yaml` from the InferenceMAX_rocm local clone as fallback

**Excel sheet layout:**
- Sheet 6: `InferenceMAX — AMD Benchmarks` (purple headers, `#4A148C`)
- Sheet 7: `InferenceX — NVIDIA Benchmarks` (teal headers, `#006064`)
- Sheet 8: `Inference Runners` (brown headers, `#4E342E`) — AMD + NVIDIA runner pool inventory

Benchmark config tuple schema (12 fields):
`(name, model, model_prefix, runner, precision, framework, multinode, disagg, isl, osl, max_tp, spec_decoding)`

## Key Conventions

- Color palette follows AMD branding: `#CC0000` (red), `#1A1A1A` (dark). Tier colors: blue (pre-commit), green (post-commit), orange (nightly).
- When adding or modifying components, edit `COMPONENTS` in `generate_rocm_html.py`. The Excel generator picks up changes automatically since it re-executes the HTML script's data section.
- The HTML output includes JavaScript for interactive filtering by category, CI status, and search — this logic is inline in the generator.
