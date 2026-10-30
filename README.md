## nfc-halfpipe

fMRI preprocessing and connectivity export using [HALFpipe](https://github.com/HALFpipe/HALFpipe) on the NeuroFLAME platform. Each participating site runs HALFpipe's full preprocessing and feature extraction locally; only QC summary statistics are shared across sites. Per-subject connectivity matrices are written locally at each site as FedLAMP CSVs, ready for downstream federated analysis computations.

> **Branch structure:**
> - `main` — preprocessing and connectivity export only (this branch)
> - `halfpipe-federated` — full 9-step federated workflow (federated connectivity, ROI values, voxelwise maps)

---

## What this computation does

Each site's computation runs in three steps:

1. **RUN_HALFPIPE** — HALFpipe preprocessing and feature extraction run on the site's BIDS data. Per-atlas FedLAMP connectivity CSVs (`data_Schaefer200.csv`, `data_Schaefer400.csv`, etc.) and a `labels.csv` are written to the output directory.
2. **Server aggregation** — The server collects QC statistics (subject counts, motion metrics) from all sites and computes weighted cross-site means.
3. **ACCEPT_GLOBAL_RESULTS** — Each site receives the federated QC summary and writes `global_results.json` and `index.html`.

Nothing beyond QC metadata is shared with the server. All connectivity data stays local.

---

## Supported Atlases

Four atlases are baked into the Docker image at build time:

| Atlas | Parcels | Image path | FedLAMP output file |
|---|---|---|---|
| Schaefer 2018 (200-parcel, 17-network) | 200 | `/atlases/Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz` | `data_Schaefer200.csv` |
| Schaefer 2018 (400-parcel, 17-network) | 400 | `/atlases/Schaefer2018_400Parcels_17Networks_order_FSLMNI152_2mm.nii.gz` | `data_Schaefer400.csv` |
| NeuroMark fMRI 1.0 ([Du et al., 2020](https://doi.org/10.1016/j.nicl.2020.102375)) | 53 | `/atlases/NeuroMark_1.0_parcellation.nii.gz` | `data_NeuroMark1.csv` |
| Brainnetome Atlas 246 ([Fan et al., 2016](https://doi.org/10.1093/cercor/bhw157)) | 246 | `/atlases/BNA_246.nii.gz` | `data_Brainnetome246.csv` |

---

## Platform Support

NeuroFLAME is designed to run on desktops, laptops, and HPC clusters. The Docker image must be available for the host architecture.

| Platform | Architecture | Status |
|---|---|---|
| Linux (HPC / cloud / workstation) | amd64 | ✅ Fully supported |
| Windows (via WSL2) | amd64 | ✅ Fully supported |
| Intel Mac | amd64 | ✅ Fully supported |
| Apple Silicon Mac | arm64 | ⚠️ Runs under Rosetta (see below) |

### Apple Silicon (arm64) — known limitation

Docker on Apple Silicon runs Linux containers. fMRIPrep calls FSL FAST unconditionally for tissue segmentation (smriprep Stage 3), and FSL does not publish `linux/aarch64` binaries. Until fMRIPrep replaces that step or FSL ships an arm64 release, the production image (`linux/amd64`) must be used with Rosetta emulation on Apple Silicon:

```bash
docker pull --platform linux/amd64 coinstacteam/nfc-halfpipe
```

This works but is **3–5× slower** than native execution due to Rosetta's x86 JIT overhead.

**Planned fix:** fMRIPrep dropping the FSL FAST dependency in favour of a pure-Python or FreeSurfer-based segmentation (e.g. SynthSeg). This is tracked in the [nipreps/smriprep](https://github.com/nipreps/smriprep) roadmap and is more likely to land before FSL publishes linux/aarch64 binaries. Once the FSL dependency is gone, a native `linux/arm64` image will be published alongside the amd64 image as a multi-arch manifest.

---

## Quick Start (Simulation with Mock Data)

No fMRI data or HALFpipe installation required — the test data uses pre-computed mock derivatives.

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Build the job folder for three sites**

```bash
python makeJob.py site1,site2,site3
```

**3. Run the NVFlare simulator**

```bash
python debugger.py job -w simulator_workspace -c site1,site2,site3
```

---

## Docker Development Setup

> **Architecture note:** `Dockerfile-dev` is **Apple Silicon (M1/M2/M3/M4) only**.  
> Linux x86\_64 users (HPC clusters, cloud VMs, Intel workstations) must use `Dockerfile-prod`.

### Mac (Apple Silicon)

```bash
docker build -t nfc-halfpipe:dev -f Dockerfile-dev .
./dockerRun.sh
```

First build compiles ANTs from source (~40–60 min); subsequent builds are cached.

### Linux x86\_64 / amd64

Use the production Dockerfile, tagged for local dev:

```bash
docker build -t nfc-halfpipe:dev -f Dockerfile-prod .
./dockerRun.sh
```

`Dockerfile-prod` starts from the official `halfpipe/halfpipe:1.3.2` amd64 image — no source compilation needed, build time ~10–20 min depending on network.

### Common error: `exec format error`

If you see `exec /bin/sh: exec format error` during `docker build`, you are on Linux x86\_64 but trying to build `Dockerfile-dev` (ARM64). Switch to `Dockerfile-prod` as shown above.

---

## Check Results

After a run, each site's output directory contains:

```
{output_dir}/
├── data_Schaefer200.csv      ← per-subject connectivity matrix rows (200-parcel atlas)
├── data_Schaefer400.csv      ← per-subject connectivity matrix rows (400-parcel atlas)
├── data_NeuroMark1.csv       ← per-subject connectivity matrix rows (NeuroMark 53 ICs)
├── data_Brainnetome246.csv   ← per-subject connectivity matrix rows (BNA 246 parcels)
├── labels.csv                ← per-subject metadata (subject_id, demographics, QC metrics)
├── global_results.json       ← federated QC summary from server
├── index.html                ← interactive QC report (open in browser)
└── halfpipe_reports/         ← HALFpipe's own per-subject QC report
    └── index.html
```

Open `index.html` for the federated QC summary. Open `halfpipe_reports/index.html` for HALFpipe's detailed per-subject report.

---

## Project Structure

```
nfc-halfpipe/
├── app/
│   ├── code/
│   │   ├── _utils/utils.py                 # Path helpers (data, output, parameters directories)
│   │   ├── computation/
│   │   │   ├── spec.py                     # 3-step workflow declaration
│   │   │   ├── local_steps.py              # run_halfpipe, build_outputs
│   │   │   └── remote_steps.py             # aggregate_qc_step
│   │   ├── executor/
│   │   │   ├── run_halfpipe.py             # Runs HALFpipe subprocess (or returns mock data)
│   │   │   ├── extract_qc_metadata.py      # Packages motion QC for transmission
│   │   │   ├── write_fedlamp_export.py     # Writes per-atlas data_*.csv + labels.csv
│   │   │   ├── atlas_labels.py             # Parcel label tables for all 4 atlases
│   │   │   ├── generate_report.py          # Generates index.html QC report
│   │   │   ├── extract_connectivity.py     # (halfpipe-federated branch only)
│   │   │   ├── extract_roi_values.py       # (halfpipe-federated branch only)
│   │   │   └── run_site_group_level.py     # (halfpipe-federated branch only)
│   │   └── framework/                      # NVFlare boilerplate (paths, step decorators)
│   └── config/
│       ├── config_fed_client.json          # Task list for executor
│       └── config_fed_server.json          # Controller + aggregator wiring
├── test_data/
│   ├── server/parameters.json             # Computation parameters
│   ├── site1/data.json                    # Site 1: mock_derivatives
│   ├── site2/data.json                    # Site 2
│   └── site3/data.json                    # Site 3
├── makeJob.py                             # Creates job/ folder from app/ config
├── debugger.py                            # Launches NVFlare simulator
├── Dockerfile-prod                        # Production image (amd64, halfpipe:1.3.2 base)
├── Dockerfile-dev                         # Dev image (arm64 / Apple Silicon)
└── display_notes.md                       # Platform-facing computation description
```

---

## Configuration

### `test_data/server/parameters.json`

```json
{
  "run_halfpipe": false,
  "aggregation_types": ["qc_metadata"],
  "halfpipe_spec": {
    "version": "1.0.0",
    "files": [
      { "datatype": "func", "suffix": "bold",
        "tags": { "task": "rest" },
        "path": "{bids_directory}/sub-{subject}/func/sub-{subject}_task-rest_bold.nii.gz" },
      { "datatype": "anat", "suffix": "T1w", "tags": {},
        "path": "{bids_directory}/sub-{subject}/anat/sub-{subject}_T1w.nii.gz" },
      { "datatype": "ref", "suffix": "atlas", "tags": { "desc": "Schaefer200" },
        "path": "/atlases/Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz" },
      { "datatype": "ref", "suffix": "atlas", "tags": { "desc": "Schaefer400" },
        "path": "/atlases/Schaefer2018_400Parcels_17Networks_order_FSLMNI152_2mm.nii.gz" },
      { "datatype": "ref", "suffix": "atlas", "tags": { "desc": "NeuroMark1" },
        "path": "/atlases/NeuroMark_1.0_parcellation.nii.gz" },
      { "datatype": "ref", "suffix": "atlas", "tags": { "desc": "Brainnetome246" },
        "path": "/atlases/BNA_246.nii.gz" }
    ],
    "settings": [
      { "name": "default", "ica_aroma": true,
        "bandpass_filter": { "type": "gaussian", "lp_width": 125.0 },
        "smoothing": { "fwhm": 6.0 },
        "grand_mean_scaling": { "mean": 10000.0 } }
    ],
    "features": [
      { "name": "reho",  "type": "reho",  "setting": "default" },
      { "name": "alff",  "type": "alff",  "setting": "default" },
      { "name": "connectivity",   "type": "atlas_based_connectivity",
        "setting": "default", "atlases": ["Schaefer200"],    "min_region_coverage": 0.8 },
      { "name": "connectivity400","type": "atlas_based_connectivity",
        "setting": "default", "atlases": ["Schaefer400"],    "min_region_coverage": 0.8 },
      { "name": "neuromark",      "type": "atlas_based_connectivity",
        "setting": "default", "atlases": ["NeuroMark1"],     "min_region_coverage": 0.5 },
      { "name": "brainnetome",    "type": "atlas_based_connectivity",
        "setting": "default", "atlases": ["Brainnetome246"], "min_region_coverage": 0.8 }
    ],
    "models": []
  },
  "min_subjects": 5,
  "n_procs": 1
}
```

### `test_data/siteN/data.json`

```json
{
  "derivatives_directory": null,
  "mock_derivatives": {
    "n_subjects": 12,
    "qc_metadata": { "mean_fd": 0.38, "mean_fd_perc": 8.2 }
  }
}
```

`mock_derivatives` is read when `run_halfpipe=false` and no `derivatives_directory` is set (pure mock/dev mode). In production, the data directory the user points to in the NeuroFLAME UI is used directly as the BIDS root.

**Skipping HALFpipe when derivatives already exist:** The computation checks for a HALFpipe derivatives tree at `{halfpipe_workdir}/derivatives/halfpipe` before running the pipeline. If that directory exists — either because `derivatives_directory` is set in `data.json`, or because a prior run already completed there — HALFpipe is skipped and the existing results are used. This prevents a multi-hour pipeline re-run when a container restarts mid-federation. To force a fresh run, delete `{halfpipe_workdir}/derivatives/` before starting.

---

## Running with Real HALFpipe Data

**1. Update the Docker image**

In `Dockerfile-dev`, change the `FROM` line:

```dockerfile
FROM ghcr.io/halfpipe/halfpipe:latest
```

**2. Enable HALFpipe execution**

In `parameters.json`, set `"run_halfpipe": true` and provide a valid `halfpipe_spec`. Include EPI fieldmaps (AP/PA phase-encoding pairs) if your dataset has them — halfpipe links them automatically via the BIDS `IntendedFor` field and runs TOPUP-based susceptibility distortion correction:

```json
{
  "run_halfpipe": true,
  "fs_license_path": "/workspace/license.txt",
  "aggregation_types": ["qc_metadata"],
  "halfpipe_spec": {
    "files": [
      { "datatype": "func", "suffix": "bold",
        "tags": { "task": "rest" },
        "path": "{bids_directory}/sub-{sub}/func/sub-{sub}_task-rest_bold.nii.gz" },
      { "datatype": "anat", "suffix": "T1w", "tags": {},
        "path": "{bids_directory}/sub-{sub}/anat/sub-{sub}_T1w.nii.gz" },
      { "datatype": "ref", "suffix": "atlas", "tags": { "desc": "Schaefer200" },
        "path": "/atlases/Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz" }
    ],
    "settings": [ { "name": "default", "ica_aroma": false,
                    "bandpass_filter": { "type": "gaussian", "lp_width": 125.0 } } ],
    "features": [
      { "name": "reho",  "type": "reho",  "setting": "default" },
      { "name": "alff",  "type": "alff",  "setting": "default" },
      { "name": "connectivity", "type": "atlas_based_connectivity",
        "setting": "default", "atlases": ["Schaefer200"], "min_region_coverage": 0.8 }
    ],
    "models": []
  },
  "min_subjects": 5,
  "n_procs": 4
}
```

Omit the `fmap` entries if your dataset has no fieldmaps — halfpipe will run without SDC.

**3. Point each site to its BIDS data**

Each site's data directory (configured in the NeuroFLAME UI) must be the BIDS root for that site. The computation reads it automatically via `DATA_DIR` — no `bids_directory` field is required in `data.json`. Optionally add `"derivatives_directory"` to reuse existing HALFpipe outputs.

**4. Run the simulation inside Docker**

```bash
docker run --rm --platform linux/amd64 \
  -v "$(pwd):/workspace/repo" \
  -v "/path/to/bids:/workspace/data:ro" \
  -v "$HOME/license.txt:/workspace/data/license.txt:ro" \
  -v "/path/to/output:/workspace/output" \
  -e "PYTHONPATH=/workspace/repo/app/code/" \
  -e "PARAMETERS_FILE_PATH=/workspace/repo/test_data/server/parameters_tier4test.json" \
  coinstacteam/nfc-halfpipe \
  /opt/nfc-env/bin/python3 /workspace/repo/debugger.py /workspace/repo/job \
    -w /workspace/repo/simulator_workspace \
    -c site1
```

The image bakes `DATA_DIR=/workspace/data/` and `OUTPUT_DIR=/workspace/output/` as defaults. The `PYTHONPATH` override is required because the image ships with an older copy of the app code at `/workspace/app/code/` that takes precedence over NVFlare's job-staging paths without it.

> **Security note:** The FreeSurfer license file (`license.txt`) must never be committed to this repository. Copy it into each site's data directory or mount it directly at runtime.

---

## Output Files

Each site's output directory receives these files after a successful run:

| File | Description |
|---|---|
| `data_Schaefer200.csv` | Per-subject functional connectivity rows. Each row is one subject's upper-triangle correlation values for the Schaefer 200-parcel atlas (19,900 columns: 200×199/2). Column names: `{feature_key}_{i:03d}x{j:03d}` (1-indexed, i < j). |
| `data_Schaefer400.csv` | Same format for the Schaefer 400-parcel atlas (79,800 columns). |
| `data_NeuroMark1.csv` | Same format for NeuroMark 1.0 53-IC atlas (1,378 columns). |
| `data_Brainnetome246.csv` | Same format for Brainnetome 246-parcel atlas (30,135 columns). |
| `labels.csv` | Per-subject metadata row-aligned with all data CSVs. Columns: `subject_id`, all BIDS `participants.tsv` demographics, then HALFpipe QC metrics (`mean_fd`, `mean_fd_perc`, `mean_gm_tsnr`). |
| `global_results.json` | Federated QC summary from the server (subject counts, weighted motion statistics across sites). |
| `index.html` | Interactive HTML QC report. Open in any browser. |
| `halfpipe_reports/index.html` | HALFpipe's own per-subject QC report (preprocessing details, motion traces, registration figures). |

---

## Chaining with nfc-label-noise-filtering

The `data_*.csv` + `labels.csv` output is the direct input for [nfc-label-noise-filtering](../nfc-label-noise-filtering/). Point nfc-label-noise-filtering's data directory at this computation's output directory for each site and set:

```json
{
  "DataFile": "data_Schaefer200.csv",
  "LabelColumn": "diagnosis"
}
```

Adjust `DataFile` to the atlas you want to analyse. `LabelColumn` must match a column present in `labels.csv` (populated from `participants.tsv`).

---

## Task Flow

```
Phase 1  → RUN_HALFPIPE (all sites)
             site: run HALFpipe → write per-atlas data_*.csv + labels.csv
             site: send QC payload (n_subjects, mean_fd, mean_fd_perc) to server
             server: collect QC from all sites → compute weighted means

Phase 2  → (server aggregates QC)
           → ACCEPT_GLOBAL_RESULTS (all sites)
             site: save global_results.json + index.html to output directory
```

---

## NeuroFLAME Documentation

- **[Computation Interface](docs/neuroflame_computation_interface/neuroflame_computation_interface.md)**
- **[Developer Guides](docs/computation_development/computation_development.md)**
- **[Publishing Requirements](docs/computation_publishing/Computation_Publishing_Requirements.md)**
