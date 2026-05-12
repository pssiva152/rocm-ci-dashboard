# ROCm CI/CD Comprehensive Report

An automated documentation generator for AMD ROCm's CI/CD ecosystem. It produces an interactive HTML report and a 9-sheet Excel workbook that map every component, runner, framework, and inference benchmark across the entire **TheRock + InferenceMAX** pipeline.

---

## Why this project changed (Nov 2026)

ROCm-org repos now **block classic GitHub Personal Access Tokens** — only fine-grained tokens are accepted, and those typically require admin approval. This project no longer relies on the GitHub API.

Instead, it now uses **anonymous `git clone`** for the public repos and **SSH `git clone`** for the private one:

| Repo / source | Visibility | Method | Auth needed | Fallback |
|---|---|---|---|---|
| `ROCm/TheRock` | public | `git clone` (HTTPS, sparse) | none | `therock_ci_snapshot.json` |
| `ROCm/rocm-libraries` | public | `git clone` (HTTPS, metadata only) | none | `therock_ci_snapshot.json` |
| `ROCm/rocm-systems` | public | `git clone` (HTTPS, metadata only) | none | `therock_ci_snapshot.json` |
| `ROCm/InferenceMAX_rocm` | private | `git clone` (SSH, sparse) | SSH key registered with GitHub | `inferencemax_snapshot.json` |
| `therock-runner-health.com` | AMD-internal | local `.mhtml` → live HTTPS GET | AMD VPN + GitHub-authenticated browser session | `runner_health_snapshot.json` |

If any of these primary sources fail (no network, git missing, SSH key not configured, repo unreachable, dashboard requires login), the fetcher transparently falls back to the **last good JSON snapshot** committed alongside the script.

---

## Requirements

| Requirement | Why |
|---|---|
| **Python 3.11+** | `tomllib` is part of the stdlib from 3.11 onwards — used to parse `BUILD_TOPOLOGY.toml` |
| **`git`** on `PATH` | All live data fetching goes through `git clone` |
| `pip install xlsxwriter` | Required for the Excel workbook |
| `pip install pyyaml` *(optional)* | Only needed by `create_snapshots.py` if you build snapshots from a local `InferenceMAX_rocm/` clone |
| **SSH key registered with GitHub** *(optional)* | Only needed for live `ROCm/InferenceMAX_rocm` data; without it the fetcher falls back to the local clone or the JSON snapshot |

---

## Quick Start — `rocm_report_bundle.py` (recommended)

```bash
pip install xlsxwriter
python rocm_report_bundle.py              # LIVE (clones), falls back to snapshot
python rocm_report_bundle.py --snapshot   # snapshot-only, skip all clones
```

Outputs (written next to the script):

- `ROCm_CICD_Comprehensive.html` — interactive report
- `ROCm_CICD_Comprehensive.xlsx` — 9-sheet Excel workbook

The bundle is just a thin entry point — it copies the source files into a temp folder and invokes either `fetch_rocm_data.py` (LIVE) or the two generators directly (SNAPSHOT). All real logic lives in the source files in this folder.

---

## Two run modes

### LIVE mode (default)

Performs anonymous git clones of the public ROCm repos and a sparse SSH clone of `ROCm/InferenceMAX_rocm`, parses the YAML / Python / TOML configs from the working tree, regenerates `rocm_ci_data.py` and the JSON snapshots, and finally renders the HTML + Excel reports.

```bash
python rocm_report_bundle.py
```

Internally this calls `python fetch_rocm_data.py`. Run it directly if you want to see the fetcher logs in isolation:

```bash
python fetch_rocm_data.py
```

The fetcher uses `--depth=1 --filter=blob:none --sparse` clones, so each repo only downloads metadata + the handful of files we actually read. End-to-end the whole live run completes in **~60 seconds** on a normal connection.

### SNAPSHOT mode

Skips all network access and renders the report straight from the committed `rocm_ci_data.py` plus the two JSON snapshots.

```bash
python rocm_report_bundle.py --snapshot
```

Use this when:

- You don't have `git` installed
- You're offline
- You want a fully reproducible build from a known commit
- You just want to render the report quickly without any clones

---

## Fallback behaviour (built-in resilience)

```
┌─ Public repos (TheRock / rocm-libraries / rocm-systems) ─────────────┐
│  ① anonymous git clone (HTTPS, sparse, --depth=1)                    │
│       ↓ fails (no git / no network / repo down) ↓                    │
│  ② therock_ci_snapshot.json   ← committed to repo                    │
└──────────────────────────────────────────────────────────────────────┘

┌─ Private repo (InferenceMAX_rocm) ───────────────────────────────────┐
│  ① local clone at  ./InferenceMAX_rocm/  or  ../InferenceMAX_rocm/   │
│       ↓ not present ↓                                                │
│  ② SSH clone via git@github.com:ROCm/InferenceMAX_rocm.git           │
│       ↓ fails (no SSH key / no access) ↓                             │
│  ③ inferencemax_snapshot.json   ← committed to repo                  │
└──────────────────────────────────────────────────────────────────────┘

┌─ Runner-health (therock-runner-health.com, AMD-internal) ────────────┐
│  ① local TheRock Runner Health.mhtml in this folder                  │
│     (saved manually from the dashboard while signed in on AMD VPN;   │
│      NEVER committed — it's a verbatim copy of an internal page)     │
│       ↓ not present ↓                                                │
│  ② anonymous HTTPS GET of https://therock-runner-health.com/         │
│     (will succeed only if your shell can reach the host AND the      │
│      response isn't bounced to a GitHub OAuth login page)            │
│       ↓ fails (page gated, host unreachable, parse mismatch) ↓       │
│  ③ runner_health_snapshot.json   ← committed to repo                 │
│     (auto-refreshed every time path ① or ② succeeds, so even this    │
│      committed cache stays current as long as one team-mate runs     │
│      with the .mhtml present and pushes the regenerated snapshot)    │
└──────────────────────────────────────────────────────────────────────┘
```

The loaders print exactly which path was used at every step, so you can always tell whether the report is built from live data or a cached snapshot. The HTML report itself shows a coloured "source" chip in the live-status banner: green = mhtml, blue = live, orange = snapshot.

---

## File layout & data flow

```
TheRock_CI-CD/
├── generate_rocm_html.py        # HTML report generator — owns COMPONENTS, RUNNER_DATA
├── generate_rocm_cicd.py        # Excel workbook generator — owns TIER_DATA, FW_DATA, WH_DATA
├── fetch_rocm_data.py           # Live fetcher (sparse git clones); writes rocm_ci_data.py
├── rocm_report_bundle.py        # Single entry point — LIVE or --snapshot
├── create_snapshots.py          # Dev tool: rebuild snapshots from static defaults + local InferenceMAX clone
├── create_bundle.py             # Dev tool: rebuild rocm_report_bundle.py from sources
├── runner_health_parser.py      # Parses TheRock Runner Health.mhtml for live online/busy data
│
├── rocm_ci_data.py              # COMMITTED snapshot — full COMPONENTS / RUNNER_DATA / TIER_DATA / etc.
├── therock_ci_snapshot.json     # COMMITTED snapshot — raw text of TheRock files (matrix, topology, …)
├── inferencemax_snapshot.json   # COMMITTED snapshot — parsed InferenceMAX configs + runner pools
├── runner_health_snapshot.json  # COMMITTED snapshot — parsed runner-health dashboard (online/busy/idle)
├── TheRock Runner Health.mhtml  # GIT-IGNORED — manual save of the internal runner-health dashboard
│                                #   (NOT in repo; produces runner_health_snapshot.json when present)
│
├── InferenceMAX_rocm/           # OPTIONAL local clone (`git clone git@github.com:ROCm/InferenceMAX_rocm.git`)
└── README.md
```

```
                ┌─────────────────────────────────────────┐
                │             Data Sources                │
                │                                         │
                │  ROCm/TheRock          (public, HTTPS)  │
                │  ROCm/rocm-libraries   (public, HTTPS)  │
                │  ROCm/rocm-systems     (public, HTTPS)  │
                │  ROCm/InferenceMAX_rocm (private, SSH)  │
                │                                         │
                │  ── if clone fails: JSON snapshot ──    │
                └────────────────────┬────────────────────┘
                                     ▼
                          fetch_rocm_data.py
                                     │
                                     ▼
                            rocm_ci_data.py
                                     │
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
            generate_rocm_html.py       generate_rocm_cicd.py
                       │                           │
                       ▼                           ▼
            ROCm_CICD_                  ROCm_CICD_
            Comprehensive.html          Comprehensive.xlsx
```

> **Canonical data rule**: `generate_rocm_html.py` owns `COMPONENTS` and `RUNNER_DATA`. `generate_rocm_cicd.py` re-uses them via `exec()` of the HTML script's data block. When `rocm_ci_data.py` is present in the working directory, both generators load all data from it instead of their hardcoded baseline.

---

## What the live fetcher actually clones

### `ROCm/TheRock` — sparse clone of these 4 paths only

| Path | Purpose |
|---|---|
| `build_tools/github_actions/amdgpu_family_matrix.py` | Runner labels per GPU family, `nightly_check_only_for_family` flags |
| `BUILD_TOPOLOGY.toml` | Component → super-repo mapping (`rocm-libraries` / `rocm-systems` / TheRock direct) |
| `.gitmodules` | Direct TheRock submodules (components tested inside TheRock) |
| `.github/workflows/ci_nightly.yml` | Nightly cron schedule |

Everything else in TheRock is filtered out via `--filter=blob:none`, so this clone weighs only a few hundred KB regardless of TheRock's actual size.

### `ROCm/rocm-libraries` — directory listing only

We only need the names of `projects/*` subdirectories. The fetcher uses `git ls-tree -d --name-only HEAD projects/` against a `--no-checkout` clone, so **no blobs** are downloaded at all.

### `ROCm/rocm-systems` — directory listing only

Same approach as `rocm-libraries`.

### `ROCm/InferenceMAX_rocm` — sparse SSH clone of these 2 files

| Path | Purpose |
|---|---|
| `.github/configs/amd-master.yaml` | All AMD inference benchmark configurations |
| `.github/configs/runners.yaml` | AMD GPU runner pool definitions |

---

## Setting up SSH for InferenceMAX (one-time, optional)

Skip this section if you're happy to rely on the JSON snapshot for InferenceMAX data.

```bash
# 1. Generate a key (if you don't already have one)
ssh-keygen -t ed25519 -C "you@amd.com"

# 2. Add the public key to GitHub: Settings → SSH and GPG keys → New SSH key
cat ~/.ssh/id_ed25519.pub          # macOS / Linux
type %USERPROFILE%\.ssh\id_ed25519.pub   # Windows cmd

# 3. Verify the key works
ssh -T git@github.com
#  → "Hi <your-username>! You've successfully authenticated, ..."

# 4. Confirm you have access to the private repo
git ls-remote git@github.com:ROCm/InferenceMAX_rocm.git HEAD
```

If step 4 fails with "Repository not found", request access from the InferenceMAX maintainers.

Once SSH is set up, every `python fetch_rocm_data.py` run will pick up the latest InferenceMAX configs automatically.

> **Tip**: If you already have a local clone of `InferenceMAX_rocm/` next to this folder, the fetcher reads from that first (faster, offline-friendly). It pulls the file content from `origin/main` via `git show`, so even a stale or feature-branch checkout is fine.

---

## Refreshing the runner-health snapshot (AMD VPN required)

`runner_health_snapshot.json` is the public-facing cache of live runner-fleet status (online/offline/busy/idle counts, per-label queue lag, per-machine details). It is committed to the repo so the report always renders. To refresh it:

1. **On AMD VPN**, open <https://therock-runner-health.com/> in a browser and sign in with GitHub.
2. **Save the page** as `TheRock Runner Health.mhtml` in this folder
   *(Edge / Chrome → "Save page as…" → "Webpage, Single File")*. The file name must match exactly (or any of the other four names listed in `.gitignore`).
3. Run any of the generators:
   ```bash
   python generate_rocm_html.py        # or
   python rocm_report_bundle.py        # full report
   ```
   The runner-health loader detects the `.mhtml`, parses it, and **automatically rewrites** `runner_health_snapshot.json` so that downstream users without VPN access still see your refreshed numbers.
4. Commit the regenerated snapshot:
   ```bash
   git add runner_health_snapshot.json
   git commit -m "chore: refresh runner-health snapshot"
   git push
   ```

> **Why isn't the `.mhtml` in the repo?**
> It's a verbatim copy of an AMD-internal dashboard page (with internal hostnames, GitHub session metadata, etc.). The parsed JSON snapshot is safe to publish — it's the same numerical data we already render in the public HTML report — but the raw page is not. `.gitignore` covers all four common name variants of the saved page.

> **Resolution order at run time** (mirrored in `runner_health_parser.load_runner_health_any`):
> ① local `.mhtml` → ② live HTTPS GET of the dashboard (usually fails for scripted runs because the URL requires a logged-in browser session) → ③ committed `runner_health_snapshot.json`. The HTML report shows a coloured chip indicating which path was actually used for the current build.

---

## How to refresh snapshots (dev workflow)

After a successful live run, the fetcher always writes the latest `rocm_ci_data.py`, `therock_ci_snapshot.json`, and `inferencemax_snapshot.json`. To update the committed snapshots:

```bash
python fetch_rocm_data.py
git add rocm_ci_data.py therock_ci_snapshot.json inferencemax_snapshot.json
git commit -m "chore: refresh CI / inference snapshots"
git push
```

`create_snapshots.py` is an alternative path that builds snapshots from the **static defaults** baked into the generator scripts (no live fetch). Use it only when you want to commit a known-baseline snapshot independent of GitHub state:

```bash
pip install xlsxwriter pyyaml
python create_snapshots.py
```

---

## Snapshot files reference

| File | Contents | Loaded by |
|---|---|---|
| `rocm_ci_data.py` | **All structured data** — COMPONENTS, RUNNER_DATA, TIER_DATA, FW_DATA, WH_DATA, INFERENCEMAX_DATA, INFERENCE_RUNNERS | `generate_rocm_html.py`, `generate_rocm_cicd.py` (auto-detected) |
| `therock_ci_snapshot.json` | Raw text of `amdgpu_family_matrix.py`, `BUILD_TOPOLOGY.toml`, `.gitmodules`, `ci_nightly.yml` + project-name lists | `fetch_rocm_data.py` (fallback when public clones fail) |
| `inferencemax_snapshot.json` | Parsed InferenceMAX benchmark configs + runner pools | `fetch_rocm_data.py` (fallback when InferenceMAX clone fails) |
| `runner_health_snapshot.json` | Parsed runner-health dashboard — refresh time, online/offline/busy/idle counts, per-label queue metrics, per-machine list | `runner_health_parser.load_runner_health_any` (fallback when no `.mhtml` and live HTTPS fails) |

All four are committed to git so the report can be regenerated reproducibly with `python rocm_report_bundle.py --snapshot` even with no network access.

---

## Output files

| File | Description |
|---|---|
| `ROCm_CICD_Comprehensive.html` | Interactive HTML — filtering, search, smooth-scroll nav, live runner-health badges |
| `ROCm_CICD_Comprehensive.xlsx` | 9-sheet Excel workbook with AMD "Internal Only" MIP sensitivity label |

---

## Excel workbook sheets

| # | Sheet | Source |
|---|---|---|
| 1 | Component CI Matrix | `COMPONENTS` (in `generate_rocm_html.py`) |
| 2 | CI Tiers | `TIER_DATA` (in `generate_rocm_cicd.py`) |
| 3 | Framework Detail | `FW_DATA` (in `generate_rocm_cicd.py`) |
| 4 | Runner Inventory | `RUNNER_DATA` (in `generate_rocm_html.py`) |
| 5 | Wheel Artifact Publishing | `WH_DATA` (in `generate_rocm_cicd.py`) |
| 6 | InferenceMAX — AMD Benchmarks | `amd-master.yaml` |
| 7 | Inference Runners | `runners.yaml` |
| 8 | InferenceMAX Workflows | hardcoded in `generate_rocm_cicd.py` |
| 9 | Data Sources | hardcoded — links to source repos |

The workbook is automatically labelled with AMD's **"Internal Only"** Microsoft Information Protection (MIP) sensitivity label at write time.

---

## HTML report sections (top-nav)

| Anchor | Section |
|---|---|
| `#overview` | High-level summary cards |
| `#tiers` | CI Tier Overview (5 tiers × Linux/Windows family rules) |
| `#components` | Component CI Matrix (75 components, filterable) |
| `#frameworks` | Framework Detail (PyTorch / JAX builds) |
| `#wheels` | Wheel Artifact Publishing |
| `#server-counts` | Consolidated server counts (Component / Framework / Inference) |
| `#runners` | Runner Inventory with live online/busy/offline data |
| `#inferencemax` | InferenceMAX AMD benchmarks |
| `#inference-runner-inventory` | InferenceMAX runner pools |
| `#data-sources` | "How Data Is Fetched" |
| `#appendix-gfx` | AMD GFX ISA → ASIC full lookup table |

---

## Adding or updating components

When a new component appears in `ROCm/rocm-libraries`, `ROCm/rocm-systems`, or TheRock:

1. Run `python fetch_rocm_data.py` — auto-discovers new directories under `projects/` and adds baseline entries to `COMPONENTS`.
2. New components show up with `CI Enabled: Partial` and empty GPU family / runner columns.
3. Open `generate_rocm_html.py` and refine the new tuple in `COMPONENTS` with accurate GPU family strings, runner labels, and test-type info.
4. Re-run `python rocm_report_bundle.py` to verify.

## Adding new InferenceMAX benchmarks

Driven entirely by `amd-master.yaml` in `ROCm/InferenceMAX_rocm`. When a new config is added upstream:

1. Either pull latest in your local `InferenceMAX_rocm/` clone, or rely on the SSH clone path.
2. Run `python fetch_rocm_data.py` — the new config automatically appears in Excel sheet 6 and HTML `#inferencemax`.

No generator changes needed.

---

## Key repositories

| Repo | Role |
|---|---|
| [`ROCm/TheRock`](https://github.com/ROCm/TheRock) | Super-repo — CI orchestration, GPU family matrix, submodule coordination |
| [`ROCm/rocm-libraries`](https://github.com/ROCm/rocm-libraries) | Math/communication/ML libraries |
| [`ROCm/rocm-systems`](https://github.com/ROCm/rocm-systems) | System tools (RCCL, rocminfo, ROCm-SMI, etc.) |
| [`ROCm/InferenceMAX_rocm`](https://github.com/ROCm/InferenceMAX_rocm) | AMD fork of SemiAnalysis InferenceX — AMD GPU inference benchmarking |
| [`ROCm/pytorch`](https://github.com/ROCm/pytorch) | AMD's PyTorch fork — release branches tested in CI |
| [`ROCm/rocm-jax`](https://github.com/ROCm/rocm-jax) | AMD's JAX fork — release branches tested in CI |

---

## Troubleshooting

**`fatal: unable to access ... Could not resolve host`**
No network or DNS issue. The fetcher will fall back to `therock_ci_snapshot.json` automatically — the HTML and Excel will still be generated.

**`Permission denied (publickey)` on the InferenceMAX clone**
Your SSH key isn't registered with GitHub or doesn't have access to the private repo. The fetcher falls back to `inferencemax_snapshot.json`. To enable live data, follow the [SSH setup section](#setting-up-ssh-for-inferencemax-one-time-optional) above.

**`git: command not found` / `'git' is not recognized`**
Install Git from [git-scm.com/downloads](https://git-scm.com/downloads). The fetcher will skip all clones and use snapshots until git is installed.

**Stale data in the report**
Either snapshots are out of date (run `python fetch_rocm_data.py` and commit the regenerated files), or you ran in `--snapshot` mode. Run without `--snapshot` to refresh.

**Windows: long-path errors during clone**
The fetcher already passes `-c core.longpaths=true` to every git command. If you still see issues, enable the Windows long-path policy: `git config --global core.longpaths true`.

**Live-status banner shows orange "snapshot" chip even on AMD VPN**
The live HTTPS fetch silently fell back because the request was bounced to GitHub's OAuth flow (the dashboard is gated by GitHub login). This is expected for any non-browser HTTP client. To get fresh numbers, save the dashboard page as `TheRock Runner Health.mhtml` in this folder and re-run — see the *Refreshing the runner-health snapshot* section above. The orange chip means the report is rendering from the last committed snapshot, which is always present.

**`AttributeError: 'RunnerHealth' object has no attribute …` after pulling latest**
You have a stale `runner_health_snapshot.json` written by an older schema. Delete it and re-run:
```bash
rm runner_health_snapshot.json
python generate_rocm_html.py
```
If a `.mhtml` is on disk, it'll be parsed and a fresh snapshot will be written. Otherwise the live fetch will be tried and (if it fails) the report will simply render without the live-runner enrichment.
