## nfc-halfpipe

Federated fMRI analysis using [HALFpipe](https://github.com/HALFpipe/HALFpipe) on the NeuroFLAME platform. Each participating site runs HALFpipe's preprocessing and feature extraction locally; only summary statistics are shared across sites.

Four aggregation modes are supported (and can be combined):

| Mode | What sites share | Output |
|---|---|---|
| `qc_metadata` | Motion QC stats (mean FD, FD%) | Cross-site weighted QC report |
| `roi_values` | Atlas-parcellated feature means (ReHo, ALFF, …) | Weighted global parcel means |
| `atlas_connectivity` | Per-subject Fisher-z correlation matrices (one per atlas) | Federated mean correlation matrix in `global_results.json` + interactive heatmap in `index.html` |
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
│   │   │   ├── executor.py            # HALFpipeExecutor — routes all NVFlare tasks
│   │   │   ├── run_halfpipe.py        # Runs HALFpipe subprocess (or returns mock data)
│   │   │   ├── extract_qc_metadata.py # Packages motion QC for transmission
│   │   │   ├── extract_roi_values.py  # Extracts atlas-parcellated means from NIfTI maps
│   │   │   ├── extract_connectivity.py# Reads correlation matrix TSVs, applies Fisher z-transform
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

## Atlas-Based Connectivity

Add `"atlas_connectivity"` to `aggregation_types` to federate full functional connectivity matrices:

```json
"aggregation_types": ["qc_metadata", "atlas_connectivity"],
"halfpipe_spec": {
  "files": [
    { ... },
    {
      "datatype": "ref",
      "suffix": "atlas",
      "tags": { "desc": "Schaefer200" },
      "path": "/atlases/Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz"
    }
  ],
  "features": [
    {
      "name": "connectivity",
      "type": "atlas_based_connectivity",
      "setting": "default",
      "atlases": ["Schaefer200"],
      "min_region_coverage": 0.8
    }
  ]
}
```

**How it works:**

1. HALFpipe's `atlas_based_connectivity` feature extracts the mean BOLD time series for every parcel in the atlas, then computes the full N×N covariance and correlation matrix per subject.
2. Each site's executor reads the per-subject `*_correlation_matrix.tsv` files, Fisher z-transforms each matrix (`atanh(r)`), and averages across subjects to produce a site-mean Fisher-z matrix.
3. The server computes a subject-count-weighted mean across sites, then back-transforms (`tanh`) to produce the federated mean correlation matrix.
4. The result appears in `global_results.json` under `connectivity.matrices` and is rendered as an interactive blue→white→red heatmap in `index.html`.

**Atlas options:**

Any integer-labeled NIfTI parcellation atlas works. The Schaefer 2018 atlas (200 parcels, 17 networks) ships with the Docker image at `/atlases/`. To use a different atlas:

| Atlas | Parcels | Notes |
|---|---|---|
| Schaefer 2018 (200-parcel, 17-network) | 200 | Baked into image at `/atlases/Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz` |
| NeuroMark 1.0 (53 ICs) | 53 | Derived from ICA; 7 functional network domains; winner-takes-all parcellation from Z-maps. Not yet in image — see below. |
| NeuroMark 2.0 (105 ICs) | 105 | Higher-resolution ICA template. |

**NeuroMark integration (planned):** NeuroMark ([Du et al., 2020](https://doi.org/10.1016/j.nicl.2020.102375)) is a data-driven ICA atlas from the TReNDS Center with 53 components organized in 7 functional network domains. Its 53×53 connectivity matrix naturally shows the block-diagonal network structure. To use it:

1. Obtain the NeuroMark 1.0 spatial maps (`NeuroMark_fMRI_1.0`) from [the TReNDS data portal](https://trendscenter.org/data/).
2. Convert the 4D Z-map NIfTI to an integer-labeled parcellation (winner-takes-all per voxel).
3. Add the parcellation NIfTI to the Docker image (e.g. at `/atlases/NeuroMark_1.0_parcellation.nii.gz`).
4. Register it in the spec the same way as above, using `"desc": "NeuroMark1"` as the tag.

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

Phase 2b → SEND_ATLAS_CONNECTIVITY (if "atlas_connectivity" in aggregation_types)
             site: load per-subject correlation matrix TSVs from halfpipe derivatives
                   apply Fisher z-transform → compute site-mean Fisher-z matrix
                   send {atlas_key → mean_fisher_z_matrix, n_subjects} to server
             server: weighted-average Fisher-z matrices across sites → tanh back-transform
                     → federated mean correlation matrix per atlas

Phase 2c → SEND_SITE_STATS (if "voxelwise_maps" in aggregation_types)
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
