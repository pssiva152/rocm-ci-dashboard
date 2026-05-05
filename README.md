# ROCm CI/CD Comprehensive Report

An automated documentation generator for AMD ROCm's CI/CD ecosystem. It produces an interactive HTML report and a 9-sheet Excel workbook that map every component, runner, framework, and inference benchmark across the entire TheRock + InferenceMAX pipeline.

---

## Requirements

```bash
pip install xlsxwriter        # required — Excel workbook generation
pip install pyyaml            # required only if using create_snapshots.py with a local InferenceMAX_rocm clone
```

Python 3.11+ is required (`tomllib` is used for TOML parsing in `fetch_rocm_data.py`).

---

## Quick Start — `rocm_report_bundle.py`

**`rocm_report_bundle.py` is the recommended entry point.** It is fully self-contained — all source files must exist alongside it in the same folder; no extra setup or GitHub token required.

```bash
pip install xlsxwriter
python rocm_report_bundle.py
```

Produces two output files next to the script:
- `ROCm_CICD_Comprehensive.html` — interactive report
- `ROCm_CICD_Comprehensive.xlsx` — 9-sheet Excel workbook

> **Note:** `create_bundle.py` is a developer tool used only to _rebuild_ the bundle from source. Do not run it unless you are updating the source files.

---

## Data Modes

The report can be generated in three modes depending on what data sources are available:

### Mode 1 — Snapshot (no token, no internet required)

Uses the pre-built `rocm_ci_data.py` committed alongside the scripts. This is the **fastest and most portable** mode — no internet access needed.

```bash
pip install xlsxwriter
python rocm_report_bundle.py
```

Data comes from: `rocm_ci_data.py` (committed snapshot, see [Snapshot Files](#snapshot-files)).

---

### Mode 2 — Live fetch from GitHub

When `GITHUB_TOKEN` is set, `fetch_rocm_data.py` fetches fresh data from all four GitHub repos, regenerates `rocm_ci_data.py`, and then runs both generators.

**Linux / macOS:**
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
pip install xlsxwriter
python rocm_report_bundle.py
```

**Windows PowerShell:**
```powershell
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
pip install xlsxwriter
python rocm_report_bundle.py
```

**Windows Command Prompt:**
```cmd
set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
pip install xlsxwriter
python rocm_report_bundle.py
```

> **Token tip:** A classic GitHub Personal Access Token (PAT) with no scopes (read-only public access) is enough. Raises the GitHub API rate limit from 60 → 5000 requests/hour and enables access to private repos (`ROCm/InferenceMAX_rocm`). Generate one at: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens.

---

### Mode 3 — Local InferenceMAX_rocm clone (no token needed for InferenceMAX data)

If you have a local clone of `ROCm/InferenceMAX_rocm` placed at `InferenceMAX_rocm/` next to the scripts, the fetcher will parse its YAML config files directly — bypassing the GitHub API for InferenceMAX data entirely.

```bash
# Clone once (SSH — requires GitHub access):
git clone git@github.com:ROCm/InferenceMAX_rocm.git

pip install xlsxwriter pyyaml
python rocm_report_bundle.py
```

TheRock CI data (components, runners, GPU families) still comes from `rocm_ci_data.py` or GitHub depending on whether `GITHUB_TOKEN` is set.

---

## How to Refresh Snapshots (`create_snapshots.py`)

Run this to rebuild all three snapshot files from the static data in the generator scripts and the local `InferenceMAX_rocm/` clone:

```bash
pip install xlsxwriter pyyaml
python create_snapshots.py
```

This writes:
- `rocm_ci_data.py` — full data module with all components, runners, tiers, frameworks, and InferenceMAX benchmarks
- `inferencemax_snapshot.json` — InferenceMAX benchmark configs + runner pools (timestamped)
- `therock_ci_snapshot.json` — marker file (actual data is in `rocm_ci_data.py`)

Then verify and commit:
```bash
# Verify both outputs are generated correctly (already done by create_snapshots.py):
python generate_rocm_html.py
python generate_rocm_cicd.py

git add rocm_ci_data.py inferencemax_snapshot.json therock_ci_snapshot.json
git commit -m "chore: refresh CI/inference snapshots"
git push
```

> `create_snapshots.py` requires a local `InferenceMAX_rocm/` clone to parse InferenceMAX benchmark data. Without it, the script re-uses the existing `inferencemax_snapshot.json` if one is present. `pyyaml` is only needed when the local clone is present.

---

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                         │
│                                                         │
│  GitHub API (live)       Local clone / Snapshots        │
│  ROCm/TheRock            InferenceMAX_rocm/             │
│  ROCm/rocm-libraries     rocm_ci_data.py   ◄── (Mode 1) │
│  ROCm/rocm-systems       inferencemax_snapshot.json     │
│  ROCm/InferenceMAX_rocm                                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
         fetch_rocm_data.py          ← Mode 2 / 3 (needs GITHUB_TOKEN or local clone)
                 │
                 ▼
         rocm_ci_data.py             ← intermediate data module (generated)
                 │
         ┌───────┴───────┐
         ▼               ▼
 generate_rocm_html.py   generate_rocm_cicd.py
         │               │
         ▼               ▼
   ROCm_CICD_         ROCm_CICD_
 Comprehensive.html  Comprehensive.xlsx
```

**Key design rule:** `generate_rocm_html.py` is the **canonical data source** — all component tuples (`COMPONENTS`), runner configs (`RUNNER_DATA`), and color palettes live there. `generate_rocm_cicd.py` shares that data by executing the first ~890 lines of the HTML generator via Python's `exec()` at startup. When `rocm_ci_data.py` is present in the working directory, both generators load all data from it instead of their hardcoded baseline.

---

## Snapshot Files

Three files can be committed to GitHub so others can run the report without a token or local clone:

| File | Contents | Critical? |
|---|---|---|
| `rocm_ci_data.py` | **Everything** — COMPONENTS (73), RUNNER_DATA (23), TIER_DATA (5 tiers), FW_DATA (9 rows), WH_DATA (9 rows), INFERENCEMAX_DATA (37 benchmarks), INFERENCE_RUNNERS (19 AMD pools) | **Yes — commit this** |
| `inferencemax_snapshot.json` | InferenceMAX benchmark configs + runner pools with timestamp | Secondary — used by `fetch_rocm_data.py` as fallback |
| `therock_ci_snapshot.json` | Marker only — tells `fetch_rocm_data.py` a snapshot exists | Secondary — marker only |

> `therock_ci_snapshot.json` contains very little data by design. All the actual CI data (components, runners, tiers, framework rows) lives in `rocm_ci_data.py`. The JSON files are only used by `fetch_rocm_data.py` as fallback caches — the generators (`generate_rocm_html.py`, `generate_rocm_cicd.py`) load directly from `rocm_ci_data.py`.

---

## Project Structure

```
TheRock_CI-CD/
├── generate_rocm_html.py    # HTML report generator — canonical data source (COMPONENTS, RUNNER_DATA)
├── generate_rocm_cicd.py    # Excel workbook generator — shares data via exec(); owns TIER_DATA, FW_DATA, WH_DATA
├── fetch_rocm_data.py       # Live data fetcher — pulls from 4 GitHub repos, writes rocm_ci_data.py
├── create_snapshots.py      # Snapshot builder — produces rocm_ci_data.py + JSON snapshots from static data
├── create_bundle.py         # Bundle packager — embeds source into rocm_report_bundle.py (developer tool)
├── rocm_report_bundle.py    # Main entry point — self-contained runner (source files must be alongside it)
├── rocm_ci_data.py          # COMMITTED — generated snapshot (all data; run create_snapshots.py to refresh)
├── inferencemax_snapshot.json # COMMITTED — InferenceMAX benchmark cache (timestamped)
├── therock_ci_snapshot.json # COMMITTED — marker only; actual data is in rocm_ci_data.py
├── InferenceMAX_rocm/       # LOCAL ONLY — optional local clone of ROCm/InferenceMAX_rocm
└── README.md
```

---

## How Data Is Fetched

### TheRock CI Data (`ROCm/TheRock`)

GitHub repo: [https://github.com/ROCm/TheRock](https://github.com/ROCm/TheRock)

| File | What it populates |
|---|---|
| [`amdgpu_family_matrix.py`](https://github.com/ROCm/TheRock/blob/main/amdgpu_family_matrix.py) | Runner labels per GPU family, GPU ISA strings (`gfx94X`, `gfx950`, etc.), `nightly_check_only` flags |
| [`BUILD_TOPOLOGY.toml`](https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml) | Component → super-repo mapping (`rocm-libraries` / `rocm-systems` / TheRock direct) |
| [`.gitmodules`](https://github.com/ROCm/TheRock/blob/main/.gitmodules) | Direct TheRock submodules (components tested inside TheRock vs. via sub-repos) |
| [`.github/workflows/ci_nightly.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) | Nightly schedule time, GPU family test matrix |

**Workflow files used for `TIER_DATA`:**

| Workflow | Tier |
|---|---|
| [`ci.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml) | Pre-commit (PR trigger, quick builds) |
| [`ci_postsubmit.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_postsubmit.yml) | Post-commit (submodule bump trigger) |
| [`ci_nightly.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) | Nightly (cron `02:00 UTC`, all GPU families) |
| [`ci_asan.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_asan.yml) | ASAN sanitizer builds |
| [`multi_arch_release.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_release.yml) | Release pipeline (`workflow_dispatch`) |

---

### Library Components (`ROCm/rocm-libraries`)

GitHub repo: [https://github.com/ROCm/rocm-libraries](https://github.com/ROCm/rocm-libraries)

The `projects/` directory listing ([GitHub API](https://api.github.com/repos/ROCm/rocm-libraries/contents/projects)) is scanned — every subdirectory is treated as an active CI component (rocBLAS, hipBLAS, rocFFT, MIOpen, etc.).

---

### System Components (`ROCm/rocm-systems`)

GitHub repo: [https://github.com/ROCm/rocm-systems](https://github.com/ROCm/rocm-systems)

The `projects/` directory listing ([GitHub API](https://api.github.com/repos/ROCm/rocm-systems/contents/projects)) is scanned — every subdirectory is treated as an active CI component (RCCL, rocminfo, ROCm-SMI, etc.).

---

### InferenceMAX AMD Benchmark Data (`ROCm/InferenceMAX_rocm`)

GitHub repo: [https://github.com/ROCm/InferenceMAX_rocm](https://github.com/ROCm/InferenceMAX_rocm) (private — requires token or local clone)

**Data source priority (in order):**
1. **GitHub API** — used when `GITHUB_TOKEN` is set
2. **Local clone** at `InferenceMAX_rocm/` (relative to the project folder) or `../InferenceMAX_rocm/`
3. **Existing `inferencemax_snapshot.json`** — used when neither API nor local clone is available
4. **Skip gracefully** with a warning if none of the above exist

| File | What it populates |
|---|---|
| [`.github/configs/amd-master.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml) | All AMD inference benchmark configurations — model, precision, GPU runner, framework, multi-node flag, ISL/OSL |
| [`.github/configs/runners.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml) | AMD GPU runner pool definitions — maps logical names (`mi300x`, `mi325x`, `mi355x`) to physical node labels |

**YAML format** — `amd-master.yaml` is a flat dictionary where each top-level key is a named benchmark config:

```yaml
glm5-fp8-mi355x-atom:            # config name
  model: zai-org/GLM-5-FP8       # HuggingFace model path
  model-prefix: glm5             # short display name
  runner: mi355x                 # target GPU (mi300x / mi325x / mi355x)
  precision: fp8                 # quantization (fp8 / bf16 / int4)
  framework: atom                # inference engine (atom / sglang / vllm / sglang-disagg)
  multinode: false               # true = spans multiple nodes
  image: rocm/atom:latest        # pinned Docker image
```

> InferenceMAX_rocm is AMD's fork of [SemiAnalysis/InferenceX](https://github.com/SemiAnalysisAI/InferenceX), adapted for MI300X/MI325X/MI355X hardware.

---

## Output Files

| File | Description |
|---|---|
| `ROCm_CICD_Comprehensive.html` | Interactive HTML report with filtering, search, and smooth-scroll navigation |
| `ROCm_CICD_Comprehensive.xlsx` | 9-sheet Excel workbook with AMD "Internal Only" MIP sensitivity label |
| `rocm_ci_data.py` | Generated data module — commit this for offline use; delete to revert generators to static baseline |
| `inferencemax_snapshot.json` | Generated InferenceMAX cache — commit alongside `rocm_ci_data.py` |
| `therock_ci_snapshot.json` | Generated marker file — commit alongside `rocm_ci_data.py` |

---

## Excel Workbook Sheets

| # | Sheet Name | Color Theme | Data Source |
|---|---|---|---|
| 1 | Component CI Matrix | Blue/Green/Orange per tier | `COMPONENTS` — `generate_rocm_html.py` |
| 2 | CI Tiers | Alternating pastels | `TIER_DATA` — `generate_rocm_cicd.py` |
| 3 | Framework Detail | Blue (PyTorch) / Green (JAX) | `FW_DATA` — `generate_rocm_cicd.py` |
| 4 | Runner Inventory | Blue (Linux) / Green (Windows) / Yellow (Build) | `RUNNER_DATA` — `generate_rocm_html.py` |
| 5 | Wheel Artifact Publishing | Blue (PyTorch) / Green (JAX) | `WH_DATA` — `generate_rocm_cicd.py` |
| 6 | InferenceMAX — AMD Benchmarks | Red (`#CC0000`) | [`amd-master.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml) |
| 7 | Inference Runners | Brown (`#4E342E`) | [`runners.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml) |
| 8 | InferenceMAX Workflows | Purple-tinted rows | `.github/workflows/` in `ROCm/InferenceMAX_rocm` — 11 workflow files |
| 9 | Data Sources | Grey (`#78909C`) | Hardcoded — links to all source repos and files |

Sheets 6–7 are populated from `rocm_ci_data.py` (or live fetch). Sheet 8 (Workflows) is always written since its data is hardcoded in `generate_rocm_cicd.py`. Sheet 9 (Data Sources) is always written.

The workbook is automatically injected with AMD's **"Internal Only"** Microsoft Information Protection (MIP) sensitivity label at write time — no manual labelling needed.

---

## HTML Report Sections

### CI Tier Overview (`#tiers`)
Curated from TheRock workflow files — trigger, schedule, GPU families (Linux + Windows), test type, Python versions, distro.

### Component CI Matrix (`#components`)
73 components across Libraries, Tools, Compilers, Runtime, Frameworks, and Sysdeps categories. Each row covers pre-commit / post-commit / nightly coverage per GPU family, runner labels, and test type.

### Framework Detail (`#frameworks`)
**PyTorch** (5 versions: 2.8, 2.9, 2.10, 2.11, nightly) — from [`ROCm/pytorch`](https://github.com/ROCm/pytorch) release branches.  
**JAX** (4 versions: 0.8.0, 0.8.2, 0.9.0, 0.9.1) — from [`ROCm/rocm-jax`](https://github.com/ROCm/rocm-jax) version branches.

### Framework Runner & Server Count Details (`#framework-runners`)
Shows VM/physical machine counts broken down by framework and CI pool (PyTorch build, GPU test, JAX build+test, grand total).

### Wheel Artifact Publishing (`#wheels`)
Which framework+version combinations publish PyPI-ready wheels, which GPU families are included vs. build-only, and smoke test runner.

### Runner Inventory (`#runners`)
**Source:** `RUNNER_DATA` in `generate_rocm_html.py` — 23 runners covering OSSCI, On-Prem, and GitHub-hosted locations, sorted by location.

Summary table: runner count by location (OSSCI / On-Prem / GitHub-hosted) with Linux/Windows breakdown.

Detailed table: label, platform, OS/distro, location, physical machine count, GPU family, ISA, GPU count, CI tiers using it, notes.

| Runner Label | GPU | Pool Size | Used At |
|---|---|---|---|
| `linux-gfx942-1gpu-ossci-rocm` | MI300X/MI325X | 84 nodes | PR · postsubmit · nightly |
| `linux-gfx942-8gpu-ossci-rocm` | MI300X/MI325X | 4 nodes | Nightly distributed / RCCL |
| `linux-mi355-1gpu-ossci-rocm` | MI355X | 3 nodes | Postsubmit · nightly |
| `windows-gfx1151-gpu-rocm` | Strix Halo | 11 nodes | PR (build) · nightly (test) |
| `azure-linux-scale-rocm` | Build-only (VMs) | ~113 VMs | All tiers (compile jobs) |
| `nova-linux-slurm-scale-runner` | MI355X multi-node | 1 node | RCCL multi-node (Slurm) |

### InferenceMAX AMD Benchmarks (`#inferencemax`)
37 benchmark configurations from `amd-master.yaml`. Columns: Config Name, Model, Model Prefix, GPU Runner, Precision, Framework, Multi-Node, Pinned Docker Image.

### Inference Runner Inventory (`#inference-runners`)
19 AMD GPU runner pools from `runners.yaml`. Maps logical GPU type names to physical node labels.

---

## GPU Family Reference

| ISA | Hardware | CI Coverage |
|---|---|---|
| `gfx942` / `gfx94X` | MI300X, MI325X | PR + postsubmit + nightly (primary) |
| `gfx950` | MI355X | Postsubmit + nightly |
| `gfx90a` | MI200 | Nightly only (AUS datacenter) |
| `gfx103X` | RX 6000 (RDNA2) | Nightly only |
| `gfx110X` | Navi3 / RX 7900 | Nightly only (`nightly_check_only`) |
| `gfx1150` | Strix Point APU | Nightly only |
| `gfx1151` | Strix Halo | PR (build) + nightly (test) |
| `gfx1153` | Krackan Point APU | Nightly (disabled since Feb 2026 — CK instability) |
| `gfx120X` | Navi4 / RX 9070 | Nightly only (`nightly_check_only`) |

Families without hardware runners (build-only, no GPU test): `gfx900`, `gfx906`, `gfx908`, `gfx101X`.

---

## Adding or Updating Components

When a new component is added to `ROCm/rocm-libraries`, `ROCm/rocm-systems`, or TheRock:

1. **Run `fetch_rocm_data.py`** — auto-discovers new directories in `projects/` and adds baseline entries to `COMPONENTS`
2. **Check the output** — new components appear with `CI Enabled: Partial` and empty GPU family / runner columns
3. **Refine in `generate_rocm_html.py`** — add accurate GPU family strings, runner labels, and test type info to the `COMPONENTS` tuple for that component

## Adding New InferenceMAX Benchmarks

InferenceMAX configs are driven entirely by `amd-master.yaml` in `ROCm/InferenceMAX_rocm`. When a new config is added:

1. Pull latest changes to the local `InferenceMAX_rocm/` clone (or ensure `GITHUB_TOKEN` is set)
2. Run `python create_snapshots.py` to refresh `rocm_ci_data.py` and `inferencemax_snapshot.json`
3. The new config appears in Excel Sheet 6 and HTML `#inferencemax` automatically

No changes to the generator scripts are needed.

---

## Key Repositories

| Repo | Link | Role |
|---|---|---|
| `ROCm/TheRock` | [github.com/ROCm/TheRock](https://github.com/ROCm/TheRock) | Super-repo — CI orchestration, GPU family matrix, submodule coordination |
| `ROCm/rocm-libraries` | [github.com/ROCm/rocm-libraries](https://github.com/ROCm/rocm-libraries) | Super-repo for all ROCm math/communication/ML libraries |
| `ROCm/rocm-systems` | [github.com/ROCm/rocm-systems](https://github.com/ROCm/rocm-systems) | Super-repo for ROCm system tools (RCCL, rocminfo, ROCm-SMI, etc.) |
| `ROCm/InferenceMAX_rocm` | [github.com/ROCm/InferenceMAX_rocm](https://github.com/ROCm/InferenceMAX_rocm) | AMD fork of SemiAnalysis InferenceX — AMD GPU inference benchmarking CI |
| `ROCm/pytorch` | [github.com/ROCm/pytorch](https://github.com/ROCm/pytorch) | AMD's PyTorch fork — 5 release branches tested in CI |
| `ROCm/rocm-jax` | [github.com/ROCm/rocm-jax](https://github.com/ROCm/rocm-jax) | AMD's JAX fork — 4 release branches tested in CI |

---

## Environment Variables

| Variable | Effect |
|---|---|
| `GITHUB_TOKEN` | GitHub PAT — raises API rate limit 60 → 5000 req/hr, enables private repo access. No scopes needed (read-only public access is sufficient for public repos; a repo-scoped token is needed for `ROCm/InferenceMAX_rocm`). |

**Setting `GITHUB_TOKEN`:**

Linux / macOS:
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

Windows PowerShell (session):
```powershell
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
```

Windows PowerShell (persist across sessions):
```powershell
[System.Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_xxxxxxxxxxxxxxxxxxxx", "User")
```

Windows Command Prompt:
```cmd
set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```
