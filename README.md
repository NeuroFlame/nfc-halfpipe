## nfc-halfpipe

Federated fMRI analysis using [HALFpipe](https://github.com/HALFpipe/HALFpipe) on the NeuroFLAME platform. Each participating site runs HALFpipe's preprocessing and feature extraction locally; only summary statistics are shared across sites.

Four aggregation modes are supported (and can be combined):

| Mode | What sites share | Output |
|---|---|---|
| `qc_metadata` | Motion QC stats (mean FD, FD%) | Cross-site weighted QC report |
| `roi_values` | Atlas-parcellated feature means (ReHo, ALFF, …) | Weighted global parcel means |
| `voxelwise_maps` | Within-site NIfTI stat maps | Weighted meta-analysis maps |
| `subject_csv` | Nothing — files are written locally only | `Data.csv` + `Covariate.csv` per site, ready for [nfc-combatdc](../nfc-combatdc/) |

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
docker pull --platform linux/amd64 nfc-halfpipe:prod
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
python debug.py job -w simulator_workspace -c site1,site2,site3
```

**4. Check results**

```
test_output/simulate_job/site1/global_results.json   ← aggregated results
test_output/simulate_job/site1/index.html             ← interactive HTML report
test_output/simulate_job/site2/global_results.json
test_output/simulate_job/site2/index.html
test_output/simulate_job/site3/global_results.json
test_output/simulate_job/site3/index.html
```

Open any `index.html` in a browser to view the federated QC summary, per-feature ROI value tables, and optional voxelwise map catalogue.

---

## Project Structure

```
nfc-halfpipe/
├── app/
│   ├── code/
│   │   ├── _utils/utils.py            # Path helpers (data, output, parameters directories)
│   │   ├── executor/
│   │   │   ├── executor.py            # HALFpipeExecutor — routes all four NVFlare tasks
│   │   │   ├── run_halfpipe.py        # Runs HALFpipe subprocess (or returns mock data)
│   │   │   ├── extract_qc_metadata.py # Packages motion QC for transmission
│   │   │   ├── extract_roi_values.py  # Extracts atlas-parcellated means from NIfTI maps
│   │   │   └── run_site_group_level.py# Runs halfpipe group-level within a site
│   │   ├── controller/
│   │   │   └── controller.py          # HALFpipeController — multi-round broadcast logic
│   │   └── aggregator/
│   │       ├── aggregator.py          # HALFpipeAggregator — three accept methods + aggregate
│   │       └── aggregate_results.py   # Pure aggregation functions (no NVFlare deps)
│   └── config/
│       ├── config_fed_client.json     # Task list for executor
│       └── config_fed_server.json     # Controller + aggregator wiring
├── test_data/
│   ├── server/parameters.json         # Computation parameters (aggregation_types, halfpipe_spec, …)
│   ├── site1/data.json                # Site 1: mock_derivatives (derivatives_directory optional)
│   ├── site2/data.json                # Site 2
│   └── site3/data.json                # Site 3
├── makeJob.py                         # Creates job/ folder from app/ config
├── debug.py                           # Launches NVFlare simulator
├── Dockerfile-dev                     # Dev image (swap FROM for production HALFpipe image)
└── display_notes.md                   # Platform-facing computation description
```

---

## Configuration

### `test_data/server/parameters.json`

```json
{
  "run_halfpipe": false,
  "aggregation_types": ["qc_metadata", "roi_values"],
  "halfpipe_spec": { ... },
  "roi_extraction": {
    "atlas_path": "/atlases/Schaefer2018_200Parcels_17Networks.nii.gz",
    "features": ["reho", "falff"]
  },
  "voxelwise_maps": {
    "spreadsheet": null,
    "covariates": []
  },
  "subject_csv_config": {
    "data_file": "Data.csv",
    "covariate_file": "Covariate.csv"
  },
  "min_subjects": 1,
  "n_procs": 1
}
```

### `test_data/siteN/data.json`

```json
{
  "derivatives_directory": null,
  "mock_derivatives": {
    "n_subjects": 12,
    "qc_metadata": { "mean_fd": 0.38, "mean_fd_perc": 8.2 },
    "roi_values": {
      "reho": { "parcel_001": 0.412, "parcel_002": 0.367 },
      "falff": { "parcel_001": 0.621, "parcel_002": 0.587 }
    },
    "voxelwise_stats": {}
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
  "aggregation_types": ["qc_metadata", "roi_values"],
  "halfpipe_spec": {
    "files": [
      { "datatype": "func", "suffix": "bold",
        "tags": { "task": "rest" },
        "path": "{bids_directory}/sub-{sub}/func/sub-{sub}_task-rest_bold.nii.gz" },
      { "datatype": "anat", "suffix": "T1w", "tags": {},
        "path": "{bids_directory}/sub-{sub}/anat/sub-{sub}_T1w.nii.gz" },
      { "datatype": "fmap", "suffix": "epi",
        "tags": { "dir": "AP" },
        "path": "{bids_directory}/sub-{sub}/fmap/sub-{sub}_dir-AP_epi.nii.gz" },
      { "datatype": "fmap", "suffix": "epi",
        "tags": { "dir": "PA" },
        "path": "{bids_directory}/sub-{sub}/fmap/sub-{sub}_dir-PA_epi.nii.gz" }
    ],
    "settings": [ { "name": "default", "ica_aroma": false,
                    "bandpass_filter": { "type": "gaussian", "lp_width": 125.0 } } ],
    "features": [
      { "name": "reho",  "type": "reho",  "setting": "default" },
      { "name": "falff", "type": "falff", "setting": "default" }
    ],
    "models": []
  },
  "roi_extraction": {
    "atlas_path": "/atlases/Schaefer2018_200Parcels_17Networks.nii.gz",
    "features": ["reho", "falff"]
  }
}
```

Omit the `fmap` entries if your dataset has no fieldmaps — halfpipe will run without SDC.

**3. Point each site to its BIDS data**

Each site's data directory (configured in the NeuroFLAME UI) must be the BIDS root for that site. The computation reads it automatically via `DATA_DIR` — no `bids_directory` field is required in `data.json`. Optionally add `"derivatives_directory"` to reuse existing HALFpipe outputs.

**4. Install nibabel for ROI extraction and voxelwise aggregation**

Uncomment the `nibabel` line in `requirements.txt` or add it to the Dockerfile.

**5. Run the simulation inside Docker**

When running `debug.py` inside the production container, override `PYTHONPATH` so the NVFlare simulator loads code from your mounted repo rather than the image's baked-in `/workspace/app/code/`:

```bash
docker run --rm --platform linux/amd64 \
  -v "$(pwd):/workspace/repo" \
  -v "/path/to/bids:/workspace/data:ro" \
  -v "$HOME/license.txt:/workspace/license.txt:ro" \
  -v "/path/to/output:/workspace/output" \
  -e "PYTHONPATH=/workspace/repo/app/code/" \
  -e "PARAMETERS_FILE_PATH=/workspace/repo/test_data/server/parameters_tier4test.json" \
  nfc-halfpipe:prod \
  /opt/nfc-env/bin/python3 /workspace/repo/debug.py /workspace/repo/job \
    -w /workspace/repo/simulator_workspace \
    -c site1
```

The image bakes `DATA_DIR=/workspace/data/` and `OUTPUT_DIR=/workspace/output/` as defaults, so mount your BIDS root at `/workspace/data` and your output directory at `/workspace/output`. The `PYTHONPATH` override is required because the image ships with an older copy of the app code at `/workspace/app/code/` that takes precedence over NVFlare's job-staging paths without it.

---

## Chaining with nfc-combatdc

Add `"subject_csv"` to `aggregation_types` to produce per-site input files for [nfc-combatdc](../nfc-combatdc/):

```json
"aggregation_types": ["qc_metadata", "roi_values", "subject_csv"],
"subject_csv_config": {
  "data_file": "Data.csv",
  "covariate_file": "Covariate.csv"
}
```

Each site's output directory will contain:

| File | Contents |
|---|---|
| `Data.csv` | All-numeric matrix — one row per subject, one column per `{feature}_{parcel}`. No subject_id column. Direct input for nfc-combatdc's `data_file`. |
| `Covariate.csv` | Per-subject demographics and QC, row-aligned with `Data.csv`. Populated automatically from the site's BIDS `participants.tsv` (all demographic columns) plus HALFpipe per-subject QC metrics (`mean_fd`, `mean_fd_perc`, `mean_gm_tsnr`). The site administrator selects which columns to declare in nfc-combatdc's `covariates_types`. |

Then set nfc-combatdc's `parameters.json` to point at these files:

```json
{
  "data_file": "Data.csv",
  "covariate_file": "Covariate.csv",
  "combat_algo": "combatMegaDC",
  "covariates_types": {
    "age": "float",
    "gender": "str",
    "psychosis": "bool"
  }
}
```

Point nfc-combatdc's data directory at nfc-halfpipe's output directory for each site so it reads the files nfc-halfpipe wrote. The `covariates_types` keys must match column names present in `Covariate.csv` — use whatever subset of the demographic columns is appropriate for the analysis.

---

## Task Flow

```
Phase 1  → RUN_HALFPIPE (all sites)
             site: run halfpipe → extract QC
             server: store QC per site

Phase 2a → SEND_ROI_VALUES (if "roi_values" or "subject_csv" in aggregation_types)
             site [roi_values]:  extract parcel means → send to server
             site [subject_csv]: write Data.csv + Covariate.csv locally (nothing sent)
             server [roi_values]: store ROI values per site

Phase 2b → SEND_SITE_STATS (if "voxelwise_maps" in aggregation_types)
             site: run halfpipe group-level → compress NIfTI maps
             server: store stat maps per site

Phase 3  → (server aggregates all collected data)
           → ACCEPT_GLOBAL_RESULTS (all sites)
             site: save global_results.json to output directory
```

---

## NeuroFLAME Documentation

- **[Computation Interface](docs/neuroflame_computation_interface/neuroflame_computation_interface.md)**
- **[Developer Guides](docs/computation_development/computation_development.md)**
- **[Publishing Requirements](docs/computation_publishing/Computation_Publishing_Requirements.md)**
