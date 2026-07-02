## nfc-halfpipe

Federated fMRI analysis using [HALFpipe](https://github.com/HALFpipe/HALFpipe) on the NeuroFLAME platform. Each participating site runs HALFpipe's preprocessing and feature extraction locally; only summary statistics are shared across sites.

Three aggregation modes are supported (and can be combined):

| Mode | What sites share | Aggregated output |
|---|---|---|
| `qc_metadata` | Motion QC stats (mean FD, FD%) | Cross-site weighted QC report |
| `roi_values` | Atlas-parcellated feature means (ReHo, ALFF, …) | Weighted global parcel means |
| `voxelwise_maps` | Within-site NIfTI stat maps | Weighted meta-analysis maps |

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

Docker on Apple Silicon runs Linux containers. fMRIPrep depends on FSL (BET for BOLD brain extraction, FAST for tissue segmentation), and FSL does not currently publish `linux/aarch64` binaries. Until it does, the production image (`linux/amd64`) must be used with Rosetta emulation on Apple Silicon:

```bash
docker pull --platform linux/amd64 nfc-halfpipe:prod
```

This works but is **3–5× slower** than native execution due to Rosetta's x86 JIT overhead. For a single subject, expect 4–6 hours vs ~1.5 hours natively.

**Planned fix:** configure fMRIPrep to use ANTs for all brain-extraction and registration steps (`--skull-strip-template` and related flags), eliminating the FSL dependency. Once validated, a native `linux/arm64` image will be published alongside the amd64 image as a multi-arch manifest so `docker pull` selects the right image automatically.

**Tracking:** FSL `linux/aarch64` support — monitor [FSL GitHub](https://github.com/Washington-University/FSLInstaller) for an official arm64 release.

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

`mock_derivatives` is read when `run_halfpipe=false` and no `derivatives_directory` is set (pure mock/dev mode). In production, the data directory the user points to in the NeuroFLAME UI is used directly as the BIDS root. Set `derivatives_directory` to skip re-running HALFpipe when derivatives from a prior run already exist — the computation will read real QC and feature maps from that path instead.

---

## Running with Real HALFpipe Data

**1. Update the Docker image**

In `Dockerfile-dev`, change the `FROM` line:

```dockerfile
FROM ghcr.io/halfpipe/halfpipe:latest
```

**2. Enable HALFpipe execution**

In `parameters.json`, set `"run_halfpipe": true` and provide a valid `halfpipe_spec`:

```json
{
  "run_halfpipe": true,
  "aggregation_types": ["qc_metadata", "roi_values"],
  "halfpipe_spec": {
    "version": "1.0.0",
    "files": [ { "datatype": "func", "suffix": "bold", ... } ],
    "settings": [ { "name": "default", "bandpass_filter": { ... } } ],
    "features": [
      { "name": "reho", "type": "reho", "setting": "default" },
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

## Task Flow

```
Phase 1  → RUN_HALFPIPE (all sites)
             site: run halfpipe → extract QC
             server: store QC per site

Phase 2a → SEND_ROI_VALUES (if "roi_values" in aggregation_types)
             site: extract parcel means from NIfTI feature maps
             server: store ROI values per site

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
