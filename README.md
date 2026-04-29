# ROCm CI/CD Comprehensive Report

An automated documentation generator for AMD ROCm's CI/CD ecosystem. It produces an interactive HTML report and an Excel workbook that map every component, runner, framework, and inference benchmark across the entire TheRock + InferenceMAX pipeline.

---

## Running the Report — `rocm_report_bundle.py`

**`rocm_report_bundle.py` is the file to run.** It is fully self-contained — no repo clone, no extra files, no GitHub token required.

```bash
pip install xlsxwriter
python rocm_report_bundle.py
```

This produces two output files next to `rocm_report_bundle.py`:
- `ROCm_CICD_Comprehensive.html` — interactive report
- `ROCm_CICD_Comprehensive.xlsx` — 8-sheet Excel workbook

> **Do not run `create_bundle.py`** — that is a developer tool used only to rebuild the bundle itself and requires the full project folder.

---

## Self-Contained Bundle (`rocm_report_bundle.py`)

`rocm_report_bundle.py` is a **single Python file** that anyone can run without cloning this repo, setting up the project, or having a GitHub token.

### What is it?

`create_bundle.py` packages three things into one self-contained file:
- The data snapshot (`rocm_ci_data.py` — frozen at bundle creation time)
- Both generator scripts (`generate_rocm_html.py`, `generate_rocm_cicd.py`)
- The live data fetcher (`fetch_rocm_data.py`) — used only when a token is provided

At runtime the bundle extracts these files into a temp directory, runs them, copies the two output files (`ROCm_CICD_Comprehensive.html` and `ROCm_CICD_Comprehensive.xlsx`) next to itself, and cleans up.

### Running the bundle — snapshot mode (no token needed)

The baked-in data snapshot is used. No internet access required.

**Linux / macOS:**
```bash
pip install xlsxwriter
python rocm_report_bundle.py
```

**Windows PowerShell:**
```powershell
pip install xlsxwriter
python rocm_report_bundle.py
```

### Running the bundle — live mode (fetches fresh data from GitHub)

When `GITHUB_TOKEN` is set, the bundle runs `fetch_rocm_data.py` internally, which hits the GitHub APIs for all four repos and generates fresh outputs.

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

**Windows Command Prompt (cmd.exe):**
```cmd
set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
pip install xlsxwriter
python rocm_report_bundle.py
```

> **Token tip:** A classic GitHub Personal Access Token (PAT) with no scopes (read-only public access) is enough. Generate one at GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens. The token raises the GitHub API rate limit from 60 → 5000 requests/hour and enables access to private repos like `ROCm/InferenceMAX_rocm`.

### How to regenerate the bundle

Run this after updating any source file or after running `fetch_rocm_data.py` to bake in a fresh data snapshot:

```bash
python create_bundle.py
```

This reads the four source files, base64-encodes them, and writes a new `rocm_report_bundle.py`.

---

## Complete Data Flow

```
GitHub APIs / Local clones
        │
        ▼
fetch_rocm_data.py          ← pulls from 4 repos (see "How Data Is Fetched")
        │
        ▼
rocm_ci_data.py             ← intermediate data module (generated, not checked in)
        │
        ├──► generate_rocm_html.py  → ROCm_CICD_Comprehensive.html
        │
        └──► generate_rocm_cicd.py  → ROCm_CICD_Comprehensive.xlsx
```

`generate_rocm_html.py` is the **canonical data source** — all component tuples, runner configs, tier definitions, and color palettes live there. `generate_rocm_cicd.py` shares that data by executing the first ~530 lines of the HTML generator via Python's `exec()` at startup.

When `rocm_ci_data.py` is present in the same folder, both generators load their data from it instead of using their hardcoded baseline. Delete `rocm_ci_data.py` to revert to the static baseline.

---

## Output Files

| File | Description |
|------|-------------|
| `ROCm_CICD_Comprehensive.html` | Interactive HTML report with filtering, search, and smooth-scroll nav |
| `ROCm_CICD_Comprehensive.xlsx` | 8-sheet Excel workbook with AMD "Internal Only" MIP sensitivity label |
| `rocm_ci_data.py` | Generated data module (intermediate artifact, not checked in). Delete to revert generators to static data. |
| `rocm_report_bundle.py` | Generated self-contained bundle for sharing. Regenerate with `python create_bundle.py`. |

---

## Project Structure

```
TheRock_CI-CD/
├── fetch_rocm_data.py       # Data fetcher + orchestrator
├── generate_rocm_html.py    # HTML report generator (canonical data source)
├── generate_rocm_cicd.py    # Excel workbook generator (reuses HTML data via exec())
├── create_bundle.py         # Packages everything into rocm_report_bundle.py
├── rocm_report_bundle.py    # GENERATED — self-contained single-file distribution
├── rocm_ci_data.py          # GENERATED — written by fetch_rocm_data.py
├── InferenceMAX_rocm/       # Local clone of ROCm/InferenceMAX_rocm (optional)
└── README.md                # This file
```

---

## How Data Is Fetched (`fetch_rocm_data.py`)

The fetcher pulls from four GitHub repositories. With `GITHUB_TOKEN` set it uses the [GitHub REST API](https://docs.github.com/en/rest/repos/contents); without it, it falls back to unauthenticated API calls (60 req/hr) or a local clone where available.

### Source 1 — `ROCm/TheRock`

GitHub repo: [https://github.com/ROCm/TheRock](https://github.com/ROCm/TheRock)

| File fetched | Direct link | What it populates |
|---|---|---|
| `amdgpu_family_matrix.py` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/amdgpu_family_matrix.py) | Runner labels per GPU family (e.g. `linux-gfx942-1gpu-ossci-rocm`), GPU ISA strings (`gfx94X`, `gfx950`, etc.), and which families are `nightly_check_only` |
| `BUILD_TOPOLOGY.toml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml) | Component → super-repo mapping; determines whether a component lives in `rocm-libraries`, `rocm-systems`, or directly in TheRock |
| `.gitmodules` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.gitmodules) | List of direct submodules (used to identify components tested inside TheRock itself vs. via sub-repos) |
| `.github/workflows/ci_nightly.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) | Nightly schedule time (e.g. `02:00 UTC`), GPU family test matrix for the nightly tier |

**Additional TheRock workflow files** used for curating `TIER_DATA` in `generate_rocm_html.py`:

| Workflow | Direct link | Tier it covers |
|---|---|---|
| `ci.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml) | Pre-commit (PR trigger, quick builds) |
| `ci_postsubmit.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_postsubmit.yml) | Post-commit (submodule bump trigger) |
| `ci_nightly.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) | Nightly (cron `02:00 UTC`, all GPU families) |
| `ci_asan.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_asan.yml) | ASAN sanitizer builds |
| `ci_tsan.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_tsan.yml) | TSAN sanitizer builds |
| `multi_arch_release.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_release.yml) | Release pipeline (`workflow_dispatch`) |

---

### Source 2 — `ROCm/rocm-libraries`

GitHub repo: [https://github.com/ROCm/rocm-libraries](https://github.com/ROCm/rocm-libraries)

| Endpoint | What it populates |
|---|---|
| `projects/` directory listing ([GitHub API](https://api.github.com/repos/ROCm/rocm-libraries/contents/projects)) | Discovers all library component names (rocBLAS, hipBLAS, rocFFT, MIOpen, etc.). Any directory in `projects/` is treated as an active CI component. |

---

### Source 3 — `ROCm/rocm-systems`

GitHub repo: [https://github.com/ROCm/rocm-systems](https://github.com/ROCm/rocm-systems)

| Endpoint | What it populates |
|---|---|
| `projects/` directory listing ([GitHub API](https://api.github.com/repos/ROCm/rocm-systems/contents/projects)) | Discovers all system component names (RCCL, rocminfo, ROCm-SMI, etc.) |

---

### Source 4 — `ROCm/InferenceMAX_rocm` (AMD fork of SemiAnalysis InferenceX)

GitHub repo: [https://github.com/ROCm/InferenceMAX_rocm](https://github.com/ROCm/InferenceMAX_rocm)

**Data source priority:**
1. GitHub API — used when `GITHUB_TOKEN` is set (or if the repo is public)
2. Local clone at `InferenceMAX_rocm/` (relative to this project folder) or `../InferenceMAX_rocm/`
3. Skip gracefully with a `WARN` message if neither is available

| File fetched | Direct link | What it populates |
|---|---|---|
| `.github/configs/amd-master.yaml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml) | All AMD inference benchmark configurations — model, precision, GPU, framework, tensor-parallel config, ISL/OSL sequence lengths |
| `.github/configs/runners.yaml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml) | AMD GPU runner pool definitions — maps logical runner names (`mi300x`, `mi325x`, `mi355x`) to physical node labels |

**Note:** InferenceMAX_rocm is AMD's fork of [SemiAnalysis/InferenceX](https://github.com/SemiAnalysisAI/InferenceX), adapted for AMD MI300X/MI325X/MI355X hardware. The benchmark configs and runner pools captured here cover the full InferenceMAX CI scope (both SemiAnalysis-originated workflow logic and AMD-specific hardware configs).

---

## HTML Report Sections

### Overview Summary Cards
**Source:** Computed from `COMPONENTS`, `RUNNER_DATA`, `FW_DATA` (all in `generate_rocm_html.py`).
Shows total component rows, CI-enabled count, GPU family count, runner count, PyTorch/JAX version count, CI tier count, and submodule count.

---

### CI Tier Overview (`#tiers`)
**Source:** `TIER_DATA` list in `generate_rocm_html.py` — manually curated from these TheRock workflow files:

| Workflow | Link | Tier |
|---|---|---|
| `ci.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml) | Pre-commit — triggered on every PR, runs quick builds across core GPU families |
| `ci_postsubmit.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_postsubmit.yml) | Post-commit — triggered by submodule bump merges |
| `ci_nightly.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) | Nightly — cron `02:00 UTC`, comprehensive coverage of all GPU families |
| `ci_asan.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_asan.yml) | ASAN sanitizer builds |
| `multi_arch_release.yml` | [view on GitHub](https://github.com/ROCm/TheRock/blob/main/.github/workflows/multi_arch_release.yml) | Release pipeline (`workflow_dispatch`) |

Each tier row records: trigger condition, schedule, test type (quick/standard/comprehensive), Linux GPU families, Windows GPU families, frameworks built (PyTorch/JAX versions), and distro.

---

### Component CI Matrix (`#components`)
**Source:** `COMPONENTS` list — 23-field tuples, one per component.

When `rocm_ci_data.py` is present, `COMPONENTS` is loaded from it (written by `fetch_rocm_data.py`). Otherwise, a hardcoded baseline is used.

Each component tuple covers:

| Field | Source |
|---|---|
| Category, Sub-category | Manually classified |
| Component name | Discovered from `rocm-libraries/projects/`, `rocm-systems/projects/`, or TheRock `.gitmodules` |
| Super repo | From [`BUILD_TOPOLOGY.toml`](https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml) |
| CI Enabled (Yes/Partial/No) | Derived from GPU family matrix and workflow analysis |
| Pre-commit Linux gfx | From [`amdgpu_family_matrix.py`](https://github.com/ROCm/TheRock/blob/main/amdgpu_family_matrix.py) — families with `ci_enabled=True` at PR time |
| Pre-commit Linux Runners | From `amdgpu_family_matrix.py` runner label mapping |
| Pre-commit Windows gfx | Windows families from `amdgpu_family_matrix.py` |
| Pre-commit Windows Runners | Windows runner labels |
| Pre-commit Test Type | From [`ci.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml) test-type matrix |
| Post-commit Linux/Windows gfx & Runners | From [`ci_postsubmit.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_postsubmit.yml) matrix |
| Nightly Linux/Windows gfx & Runners | From [`ci_nightly.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) matrix (includes `nightly_check_only` families) |
| Platform | Linux / Windows / Both |
| Notes | Manual annotations (known issues, special CI behavior) |

---

### Framework Detail (`#frameworks`)
**Source:** `FW_DATA` list in `generate_rocm_cicd.py` — manually curated from these workflow files:

**PyTorch (5 versions: 2.8, 2.9, 2.10, 2.11, nightly):**
- [`ROCm/pytorch`](https://github.com/ROCm/pytorch) → `.github/workflows/` on branches `release/2.8`, `release/2.9`, etc.
- [`ci_nightly.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci_nightly.yml) → PyTorch CI matrix, GPU families, Python versions
- PyTorch test sharding: 6 default + 3 distributed (8-GPU runner) + 2 compiler/inductor = 11 parallel jobs

**JAX (4 versions: 0.8.0, 0.8.2, 0.9.0, 0.9.1):**
- [`ROCm/rocm-jax`](https://github.com/ROCm/rocm-jax) → `.github/workflows/` on version branches
- Only `gfx94X` (MI300X/MI325X) gets GPU test; all other families are build-only

Each row records: framework, version, Python versions supported, distro, Linux/Windows packages, branch/ref, nightly GPU families, PR test suite, nightly full test description, build runner, test runner, and notes.

---

### Wheel Artifact Publishing (`#wheels`)
**Source:** `WH_DATA` list in `generate_rocm_cicd.py` — curated from:
- [`ROCm/pytorch`](https://github.com/ROCm/pytorch) release pipeline workflows → which GPU families get published wheels vs. build-only
- [`ROCm/rocm-jax`](https://github.com/ROCm/rocm-jax) release pipeline → JAX wheel publishing scope
- Post-merge push triggers on `release/*` branches
- Smoke test runners: `ubuntu-24.04` (GitHub-hosted) + UBI10 container smoke install

Captures: which framework+version combinations publish PyPI-ready wheels, which GPU families are included, which are build-only (no upload), the build trigger, and smoke test runner.

---

### Runner Inventory (`#runners`)
**Source:** `RUNNER_DATA` list in `generate_rocm_html.py` — curated from live runner fleet snapshots and:
- [`ci.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/ci.yml) runner label usage
- [`amdgpu_family_matrix.py`](https://github.com/ROCm/TheRock/blob/main/amdgpu_family_matrix.py) → runner label strings per GPU ISA
- Manual fleet audit (runner pool sizes, online/offline status, location)

Each runner entry includes: label, platform (Linux/Windows), OS/distro, location (OSSCI/On-Prem/GitHub-hosted), physical machine count, GPU family, GPU ISA, GPU count per machine, which CI tiers use it, and notes.

**Key runners:**

| Runner Label | GPU | Pool Size | Used At |
|---|---|---|---|
| `linux-gfx942-1gpu-ossci-rocm` | MI300X/MI325X | 84 | PR · postsubmit · nightly |
| `linux-gfx942-8gpu-ossci-rocm` | MI300X/MI325X | 4 | Nightly distributed / RCCL |
| `linux-mi355-1gpu-ossci-rocm` | MI355X | 3 | Postsubmit · nightly |
| `windows-gfx1151-gpu-rocm` | Strix Halo | 11 | PR (build) · nightly (test) |
| `azure-linux-scale-rocm` | Build-only | ~113 | All tiers (compile jobs) |
| `nova-linux-slurm-scale-runner` | MI355X multi-node | 1 | RCCL multi-node (Slurm) |

---

### InferenceMAX AMD Benchmarks (`#inferencemax`)
**Source:** [`.github/configs/amd-master.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml) from `ROCm/InferenceMAX_rocm`

This is the SemiAnalysis InferenceX benchmark framework adapted for AMD GPUs. Each top-level YAML key is a named benchmark configuration:

```yaml
glm5-fp8-mi355x-atom:        # config name (key)
  model: zai-org/GLM-5-FP8   # HuggingFace model path
  model-prefix: glm5         # short display name
  runner: mi355x             # target GPU type (mi300x / mi325x / mi355x)
  precision: fp8             # quantization format (fp8 / bf16 / int4)
  framework: atom            # inference framework (atom / sglang / vllm / sglang-disagg)
  multinode: false           # true = spans multiple nodes
  seq-len-configs:
  - isl: 1024                # input sequence length
    osl: 1024                # output sequence length
    search-space:
    - { tp: 8, conc-start: 4, conc-end: 128 }  # tensor-parallel degree + concurrency sweep
```

Parsed fields displayed: Config Name | Model | Model Prefix | GPU Runner | Precision | Framework | Multi-Node | Pinned Docker Image

---

### InferenceMAX Workflows (`#inferencemax-workflows` in Excel Sheet 8)
**Source:** `.github/workflows/` directory of `ROCm/InferenceMAX_rocm`

These are the GitHub Actions workflow files that orchestrate the InferenceMAX benchmarking CI:

| Workflow File | Link | Trigger | Purpose |
|---|---|---|---|
| `run-sweep.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/run-sweep.yml) | `workflow_dispatch`; or PR with `sweep-enabled` label (non-draft) | Main benchmark orchestrator — iterates configs from `amd-master.yaml` and fans out benchmark jobs across the GPU runner pool |
| `atom-docker-ci.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/atom-docker-ci.yml) | `workflow_dispatch` | ATOM framework CI using Docker containers — targets configs matching `*-atom-*docker-ci` |
| `atom-slurm-ci.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/atom-slurm-ci.yml) | `workflow_dispatch` | ATOM framework CI using SLURM job scheduler — targets configs matching `*-atom-*slurm-ci` |
| `e2e-tests.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/e2e-tests.yml) | `workflow_dispatch` (interactive); called by sweep workflows | End-to-end test runner; accepts a `generate-cli-command` input that selects specific config keys from `amd-master.yaml` via `runners.yaml` |
| `pr-comment-sweep.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/pr-comment-sweep.yml) | `issue_comment` (type: created); slash command `/run-sweep` in PR comments | Slash-command sweep trigger — parses `/run-sweep` from PR comments and dispatches benchmark runs |
| `profile.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/profile.yml) | `workflow_dispatch`; called by `run-sweep.yml` | Profiling run (nsys / rocprof) on specified configs |
| `docker-tag-monitor.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/docker-tag-monitor.yml) | `schedule: cron '0 8 * * 6'` (Saturdays 08:00 UTC) | Weekly check — monitors upstream Docker image tag changes and opens a PR when a new tag is detected |
| `benchmark-tmpl.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/benchmark-tmpl.yml) | `workflow_call` only (internal template) | Single-node benchmark job template called by `run-sweep.yml` for each config |
| `benchmark-multinode-tmpl.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/benchmark-multinode-tmpl.yml) | `workflow_call` only (internal template) | Multi-node benchmark job template (Slurm-orchestrated, disaggregated prefill/decode) |
| `collect-results.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/collect-results.yml) | `workflow_call` only (post-sweep) | Aggregates throughput and latency benchmark results after a sweep completes |
| `collect-evals.yml` | [view on GitHub](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/workflows/collect-evals.yml) | `workflow_call` only (post-sweep) | Aggregates model evaluation (accuracy) results after a sweep completes |

---

### Inference Runner Inventory (`#inference-runners`)
**Source:** [`.github/configs/runners.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml) from `ROCm/InferenceMAX_rocm`

Maps logical GPU type names to physical runner node labels and cluster configuration (Docker vs. SLURM):

```yaml
mi355x:
  - amds-mi355x-node-01
  - amds-mi355x-node-02
  ...
```

AMD GPU types covered: `mi300x`, `mi325x`, `mi355x`, `mi355x-disagg`, and multi-node variants.

---

## Excel Workbook Sheets

| # | Sheet Name | Color Theme | Data Source |
|---|---|---|---|
| 1 | Component CI Matrix | Blue/Green/Orange per tier | `COMPONENTS` (same as HTML) |
| 2 | CI Tiers | Alternating pastels | `TIER_DATA` (same as HTML) |
| 3 | Framework Detail | Blue (PyTorch) / Green (JAX) | `FW_DATA` — from PyTorch/JAX workflow files |
| 4 | Runner Inventory | Blue (Linux) / Green (Windows) / Yellow (Build) | `RUNNER_DATA` (same as HTML) |
| 5 | Wheel Artifact Publishing | Blue (PyTorch) / Green (JAX) | `WH_DATA` — from release pipeline workflows |
| 6 | InferenceMAX — AMD Benchmarks | Purple (`#4A148C`) | [`amd-master.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml) |
| 7 | Inference Runners | Brown (`#4E342E`) | [`runners.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/runners.yaml) |
| 8 | InferenceMAX Workflows | Purple-tinted rows | `.github/workflows/` in `ROCm/InferenceMAX_rocm` — all 11 workflow files |

Sheets 6–8 only appear when `rocm_ci_data.py` is present, except Sheet 8 (InferenceMAX Workflows) which is always written since its data is hardcoded in `generate_rocm_cicd.py`.

The workbook is automatically injected with AMD's **"Internal Only"** Microsoft Information Protection (MIP) sensitivity label at write time — no manual labelling needed.

---

## Adding or Updating Components

When a new component is added to `ROCm/rocm-libraries`, `ROCm/rocm-systems`, or TheRock:

1. **Run `fetch_rocm_data.py`** — it will auto-discover the new directory in `projects/` and add it to `COMPONENTS` with a baseline entry.
2. **Check the output** — the new component will appear with `CI Enabled: Partial` by default and empty GPU family / runner columns.
3. **Refine in `generate_rocm_html.py`** if needed — add accurate GPU family strings, runner labels, and test type info to the `COMPONENTS` list entry for that component.

The Excel generator (`generate_rocm_cicd.py`) picks up all changes automatically since it re-executes the data portion of `generate_rocm_html.py` at startup via `exec()`.

---

## Adding New InferenceMAX Benchmark Configs

InferenceMAX configs are driven entirely by [`amd-master.yaml`](https://github.com/ROCm/InferenceMAX_rocm/blob/main/.github/configs/amd-master.yaml) in the `ROCm/InferenceMAX_rocm` repo. When a new config is added to that YAML:

1. Pull the latest changes to the local `InferenceMAX_rocm/` clone (or set `GITHUB_TOKEN`)
2. Run `python fetch_rocm_data.py`
3. The new config will appear in Excel Sheet 6 and the HTML `#inferencemax` section automatically

No changes to the generator scripts are needed.

---

## Color Palette

| Section | Primary Color | Light Accent | Meaning |
|---|---|---|---|
| Pre-commit tier | `#1565C0` | `#1976D2` | Blue — PR-gated |
| Post-commit tier | `#2E7D32` | `#388E3C` | Green — post-merge |
| Nightly tier | `#E65100` | `#F57C00` | Orange — scheduled |
| InferenceMAX AMD | `#4A148C` | `#CE93D8` | Purple — inference |
| Inference Runners | `#4E342E` | `#BCAAA4` | Brown — infra |
| AMD branding | `#CC0000` | `#1A1A1A` | Red/dark — header |
| CI Yes | `#C6EFCE` | — | Green fill |
| CI No | `#FFCCCC` | — | Red fill |
| CI Partial | `#FFEB9C` | — | Yellow fill |

---

## GPU Family Reference

| ISA | Hardware | CI Coverage |
|---|---|---|
| `gfx942` / `gfx94X` | MI300X, MI325X | PR + postsubmit + nightly (primary) |
| `gfx950` | MI355X | Postsubmit + nightly |
| `gfx90a` | MI200 | Nightly only (AUS datacenter) |
| `gfx103X` / `gfx1030` | RX 6000 (RDNA2) | Nightly only |
| `gfx110X` / `gfx1100/1101` | Navi3 / RX 7900 | Nightly only (`nightly_check_only`) |
| `gfx1150` | Strix Point APU | Nightly only |
| `gfx1151` | Strix Halo | PR (build) + nightly (test) |
| `gfx1153` | Krackan Point APU | Nightly (disabled since Feb 2026 — CK instability) |
| `gfx120X` / `gfx1200/1201` | Navi4 / RX 9070 | Nightly only (`nightly_check_only`) |

Families without hardware runners (build-only, no GPU test): `gfx900`, `gfx906`, `gfx908`, `gfx101X`.

---

## Environment Variables

| Variable | Effect |
|---|---|
| `GITHUB_TOKEN` | GitHub personal access token. Raises API rate limit from 60 → 5000 req/hr and enables fetching from private or rate-limited repos. A no-scope fine-grained PAT is sufficient. |

**Setting `GITHUB_TOKEN`:**

Linux / macOS (terminal session):
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

Windows PowerShell (session only):
```powershell
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
```

Windows PowerShell (persist for current user across sessions):
```powershell
[System.Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_xxxxxxxxxxxxxxxxxxxx", "User")
```

Windows Command Prompt (session only):
```cmd
set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

---

## Key Repositories Referenced

| Repo | Link | Role |
|---|---|---|
| `ROCm/TheRock` | [github.com/ROCm/TheRock](https://github.com/ROCm/TheRock) | Super-repo — CI orchestration, GPU family matrix, submodule coordination |
| `ROCm/rocm-libraries` | [github.com/ROCm/rocm-libraries](https://github.com/ROCm/rocm-libraries) | Super-repo for all ROCm math/communication/ML libraries |
| `ROCm/rocm-systems` | [github.com/ROCm/rocm-systems](https://github.com/ROCm/rocm-systems) | Super-repo for ROCm system tools (RCCL, rocminfo, ROCm-SMI, etc.) |
| `ROCm/InferenceMAX_rocm` | [github.com/ROCm/InferenceMAX_rocm](https://github.com/ROCm/InferenceMAX_rocm) | AMD fork of SemiAnalysis InferenceX — AMD GPU inference benchmarking CI (MI300X/MI325X/MI355X) |
| `ROCm/pytorch` | [github.com/ROCm/pytorch](https://github.com/ROCm/pytorch) | AMD's PyTorch fork — 5 release branches tested in CI |
| `ROCm/rocm-jax` | [github.com/ROCm/rocm-jax](https://github.com/ROCm/rocm-jax) | AMD's JAX fork — 4 release branches tested in CI |
