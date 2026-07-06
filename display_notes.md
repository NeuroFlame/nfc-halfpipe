### Computation Description

#### Overview

This computation implements federated fMRI analysis using [HALFpipe](https://github.com/HALFpipe/HALFpipe), a reproducible neuroimaging pipeline built on fmriprep and FSL. Each participating site runs HALFpipe's full subject-level preprocessing and feature extraction pipeline on its local fMRI data. Only summary statistics — never raw images or individual-level data — are shared with the central aggregator.

Four aggregation modes are supported and can be combined:

- **`qc_metadata`** — collect motion and data-quality statistics (mean framewise displacement, FD percentage) across sites, producing a federated QC report. Always runs as part of the first phase.
- **`roi_values`** — extract atlas-parcellated mean values from HALFpipe feature maps (e.g., ReHo, ALFF, seed-based connectivity) at each site, then compute weighted cross-site means per parcel.
- **`voxelwise_maps`** — each site runs a within-site group-level analysis using HALFpipe's `group-level` command, and the resulting statistical maps are combined at the server via a weighted meta-analysis.
- **`subject_csv`** — write per-subject parcel values (`Data.csv`) and a covariate file (`Covariate.csv`) to each site's output directory. Nothing is shared with the server. These files are the direct inputs for [nfc-combatdc](https://github.com/NeuroFLAME/nfc-combatdc) harmonisation.


#### Example

```json
{
    "run_halfpipe": true,
    "fs_license_path": "/workspace/license.txt",
    "aggregation_types": ["qc_metadata", "roi_values"],
    "halfpipe_spec": {
        "files": [
            {
                "datatype": "func",
                "suffix": "bold",
                "tags": { "task": "rest" },
                "path": "{bids_directory}/sub-{sub}/func/sub-{sub}_task-rest_bold.nii.gz"
            },
            {
                "datatype": "anat",
                "suffix": "T1w",
                "tags": {},
                "path": "{bids_directory}/sub-{sub}/anat/sub-{sub}_T1w.nii.gz"
            },
            {
                "datatype": "fmap",
                "suffix": "epi",
                "tags": { "dir": "AP" },
                "path": "{bids_directory}/sub-{sub}/fmap/sub-{sub}_dir-AP_epi.nii.gz"
            },
            {
                "datatype": "fmap",
                "suffix": "epi",
                "tags": { "dir": "PA" },
                "path": "{bids_directory}/sub-{sub}/fmap/sub-{sub}_dir-PA_epi.nii.gz"
            }
        ],
        "settings": [
            {
                "name": "default",
                "ica_aroma": false,
                "bandpass_filter": { "type": "gaussian", "lp_width": 125.0 }
            }
        ],
        "features": [
            { "name": "reho",  "type": "reho",  "setting": "default" },
            { "name": "falff", "type": "falff", "setting": "default" }
        ],
        "models": []
    },
    "roi_extraction": {
        "atlas_path": "/atlases/Schaefer2018_200Parcels_17Networks_order.nii.gz",
        "features": ["reho", "falff"]
    },
    "min_subjects": 5,
    "n_procs": 4
}
```

The `fmap` entries are optional. When AP/PA EPI fieldmaps are present in the BIDS dataset and listed in the spec, HALFpipe links them automatically via `IntendedFor` and runs TOPUP-based susceptibility distortion correction. Omit the `fmap` entries if your dataset has no fieldmaps.


#### Settings Specification

| Variable Name | Type | Description | Allowed Options | Default | Required |
|---|---|---|---|---|---|
| `run_halfpipe` | `bool` | Whether to run HALFpipe on local data. Set to `false` to use pre-computed derivatives. | `true`, `false` | `true` | ✅ Yes |
| `aggregation_types` | `list[string]` | Which aggregation modes to run. Can be a single string or a list. | `"qc_metadata"`, `"roi_values"`, `"voxelwise_maps"`, `"subject_csv"` | `["qc_metadata"]` | ✅ Yes |
| `halfpipe_spec` | `object` | HALFpipe `spec.json` content. Defines input files, preprocessing settings, and features. Required when `run_halfpipe` is `true`. See [HALFpipe documentation](https://github.com/HALFpipe/HALFpipe) for the full spec format. File paths must use the `{bids_directory}` placeholder — see note below. | valid HALFpipe spec | — | Conditional |
| `fs_license_path` | `string` | Absolute path to a FreeSurfer license file inside the container. Required when `run_halfpipe` is `true` (fMRIPrep uses FreeSurfer for surface reconstruction). | any valid path | `/workspace/license.txt` | Conditional |
| `roi_extraction.atlas_path` | `string` | Absolute path to an integer-labeled parcellation atlas NIfTI file (`.nii` or `.nii.gz`). Each unique nonzero integer is treated as one parcel. Required when `"roi_values"` is in `aggregation_types`. | any valid path | — | Conditional |
| `roi_extraction.features` | `list[string]` | HALFpipe feature names to extract ROI values from. Must match feature names defined in `halfpipe_spec`. | e.g. `["reho", "falff"]` | `[]` | Conditional |
| `voxelwise_maps.spreadsheet` | `string` | Path to a covariate spreadsheet for within-site group-level analysis. Used only when `"voxelwise_maps"` is in `aggregation_types`. | any valid path | `null` | No |
| `voxelwise_maps.covariates` | `list[string]` | Covariate column names to include in the within-site group-level design matrix. | list of strings | `[]` | No |
| `subject_csv_config.data_file` | `string` | Filename for the all-numeric per-subject parcel matrix written by `"subject_csv"`. Set nfc-combatdc's `"data_file"` parameter to the same name. | any filename | `"Data.csv"` | No |
| `subject_csv_config.covariate_file` | `string` | Filename for the per-subject covariate file written by `"subject_csv"`. Set nfc-combatdc's `"covariate_file"` parameter to the same name. | any filename | `"Covariate.csv"` | No |
| `min_subjects` | `int` | Minimum number of successfully preprocessed subjects required at a site before it contributes data to the aggregation. | any positive integer | `1` | No |
| `n_procs` | `int` | Number of parallel processes to use when running HALFpipe. | any positive integer | `1` | No |


**Note on `{bids_directory}` in `halfpipe_spec`**: HALFpipe normally expects absolute paths in `spec.json`. In this computation, use `{bids_directory}` as a placeholder wherever a path should be rooted at the site's BIDS directory. The computation substitutes `{bids_directory}` with each site's actual data directory at runtime, so a single shared `halfpipe_spec` in `parameters.json` works across all sites without per-site path configuration.

```json
"files": [
    {
        "datatype": "func",
        "suffix": "bold",
        "tags": { "task": "rest" },
        "path": "{bids_directory}/sub-{sub}/func/sub-{sub}_task-rest_bold.nii.gz"
    },
    {
        "datatype": "anat",
        "suffix": "T1w",
        "tags": {},
        "path": "{bids_directory}/sub-{sub}/anat/sub-{sub}_T1w.nii.gz"
    }
]
```

`{sub}` is a standard HALFpipe placeholder expanded per-subject by HALFpipe itself. `{bids_directory}` is expanded by this computation before passing the spec to HALFpipe.


#### Input Description

**BIDS data directory**: Each site's data directory — the directory the site administrator points to in the NeuroFLAME UI — must be the BIDS root for that site. The computation receives this path automatically and uses it as the input to HALFpipe. No `bids_directory` field is needed in `data.json`.

Each site may optionally provide a `data.json` file in its data directory:

```json
{
    "derivatives_directory": "/path/to/existing/halfpipe/derivatives"
}
```

| Field | Type | Description | Required |
|---|---|---|---|
| `derivatives_directory` | `string` | Path to an existing HALFpipe derivatives directory. When set and the directory exists, the computation skips the HALFpipe subprocess and reads real QC metrics and feature maps from this path — regardless of the `run_halfpipe` flag. | No |

HALFpipe does not require strict BIDS formatting; file paths can be specified using glob patterns in `halfpipe_spec.files`. Refer to the [HALFpipe documentation](https://github.com/HALFpipe/HALFpipe) for supported input formats.

**Four operating modes:**

| `run_halfpipe` | Derivatives present? | Behaviour |
|---|---|---|
| `true` | No existing derivatives | HALFpipe runs subject-level preprocessing and feature extraction on the site's BIDS data |
| `true` | `{halfpipe_workdir}/derivatives/halfpipe` exists | HALFpipe is skipped automatically; existing derivatives from the prior run are used. To force a re-run, delete `{halfpipe_workdir}/derivatives/` before starting. |
| `false` | `derivatives_directory` set in `data.json` | HALFpipe is skipped; real QC metrics and feature maps are read from the specified path |
| `false` | no `derivatives_directory` | Pure mock mode — all values are read from `mock_derivatives` in `data.json` (for development/testing without fMRI data) |

---

#### Algorithm Description

The computation runs in three phases:

**Phase 1 — Subject-Level Processing (all sites)**

Each site's executor operates in one of three modes depending on `run_halfpipe` and `derivatives_directory`:

- **Run mode** (`run_halfpipe=true`, no existing derivatives): Writes the provided `halfpipe_spec` to a local working directory and invokes HALFpipe. HALFpipe runs fMRIPrep preprocessing (including TOPUP-based susceptibility distortion correction when AP/PA fieldmaps are declared in the spec) followed by single-subject feature extraction (ReHo, fALFF, seed correlation, task contrasts, etc.) for every subject.
- **Auto-reuse mode** (`run_halfpipe=true`, prior derivatives found in workdir): If a `derivatives/halfpipe` tree already exists in the working directory from a completed prior run, HALFpipe is skipped and those results are used directly. This prevents redundant multi-hour re-runs when a container restarts mid-federation.
- **Explicit reuse mode** (`run_halfpipe=false`, `derivatives_directory` set in `data.json`): Skips HALFpipe and reads real QC metrics and feature maps from the specified path.
- **Mock mode** (`run_halfpipe=false`, no `derivatives_directory`): Uses pre-computed values from `mock_derivatives` in `data.json`. Intended for development and testing without fMRI data or a HALFpipe installation.

In all modes, motion QC statistics (mean framewise displacement, FD percentage above threshold) are extracted and sent to the server.

The server aggregates QC statistics from all sites using weighted means (weighted by each site's subject count).

**Phase 2a — ROI Value Extraction / Subject CSV** *(only when `"roi_values"` or `"subject_csv"` is in `aggregation_types`)*

**`roi_values`** — Each site's executor:
1. Loads each requested HALFpipe feature map (NIfTI) for every successfully preprocessed subject.
2. Applies the provided atlas parcellation: for each parcel, computes the mean signal value across voxels within the parcel and averages across subjects.
3. Sends the resulting `{feature → {parcel → mean_value}}` dictionary and subject count to the server.

The server computes a cross-site weighted mean for each feature × parcel combination.

**`subject_csv`** — Each site's executor writes two files locally (nothing is sent to the server):
1. **`Data.csv`**: all-numeric matrix with one row per subject and one column per `{feature}_{parcel}` combination. Column names follow the pattern `reho_parcel_001`, `falff_parcel_001`, etc.
2. **`Covariate.csv`**: per-subject covariate file, row-aligned with `Data.csv`, populated from:
   - BIDS `participants.tsv` — all demographic columns present at the site (age, sex, group, clinical scores, etc.)
   - HALFpipe per-subject QC metrics appended as the last three columns: `mean_fd`, `mean_fd_perc`, `mean_gm_tsnr`

   In mock mode (no real derivatives), `Covariate.csv` contains only a `subject_id` column.

These files are the direct inputs for nfc-combatdc. Set nfc-combatdc's `"data_file": "Data.csv"` and `"covariate_file": "Covariate.csv"` in its `parameters.json`, and point its data directory at this computation's output directory.

**Phase 2b — Voxelwise Meta-Analysis** *(only when `"voxelwise_maps"` is in `aggregation_types`)*

Each site's executor:
1. Runs `halfpipe group-level` locally using the site's subjects and optional covariate spreadsheet.
2. The resulting statistical maps (effect, variance, z-stat) are compressed and sent to the server.

The server performs a subject-count-weighted average across the site-level statistical maps to produce a federated group-level result. (Future versions will implement a proper fixed-effects or mixed-effects meta-analysis.)

**Phase 3 — Global Results Delivery (all sites)**

The server broadcasts the aggregated results (QC summary, global ROI values, and/or meta-analysis maps) back to all sites. Each site saves the global results to its output directory.


#### Assumptions

- HALFpipe and its neuroimaging dependencies (fmriprep, FSL, AFNI) are available in the Docker image used at each site when `run_halfpipe` is `true`. Use `ghcr.io/halfpipe/halfpipe:latest` as the base image.
- Each site's data directory (selected in the NeuroFLAME UI) is the BIDS root. File paths in `halfpipe_spec.files` use the `{bids_directory}` placeholder, which the computation substitutes with that path at runtime.
- The atlas NIfTI provided in `roi_extraction.atlas_path` uses the same MNI template space as the HALFpipe output (MNI152NLin2009cAsym by default).
- All sites have the atlas file at the same absolute path, or the path is mounted at a consistent location inside the container.
- The computation requires at least two participating sites.
- Sites with fewer than `min_subjects` successfully preprocessed subjects are excluded from aggregation.


#### Output Description

Results are written to each site's output directory at the end of the computation.

| File | Description |
|---|---|
| `qc_metadata.json` | Site-level QC summary (n_subjects, mean FD, FD percentage). Always produced. |
| `roi_values.json` | Site-level parcellated feature means per subject. Produced when `"roi_values"` is in `aggregation_types`. |
| `Data.csv` | Per-subject parcel value matrix. One row per subject, columns are `{feature}_{parcel_label}` — all-numeric, no subject_id column. Produced when `"subject_csv"` is in `aggregation_types`. |
| `Covariate.csv` | Per-subject covariate file, row-aligned with `Data.csv`. Columns: `subject_id`, all demographic columns from BIDS `participants.tsv`, then `mean_fd`, `mean_fd_perc`, `mean_gm_tsnr`. Produced when `"subject_csv"` is in `aggregation_types`. |
| `site_stats_summary.json` | Summary of voxelwise maps sent to the server (map count, n_subjects). Produced when `"voxelwise_maps"` is in `aggregation_types`. |
| `global_results.json` | Global aggregated results from the server, containing all active mode outputs. Always produced. |
| `index.html` | Self-contained interactive HTML report summarising QC metrics, ROI value tables with inline bar charts, and voxelwise map catalogue. Generated alongside `global_results.json`. Open in any browser. |

**`global_results.json` structure:**

```json
{
    "qc_metadata": {
        "total_subjects": 36,
        "n_sites": 3,
        "mean_mean_fd": 0.371,
        "mean_mean_fd_perc": 8.0,
        "site_summaries": {
            "site1": { "n_subjects": 12, "mean_fd": 0.38, "mean_fd_perc": 8.2 },
            "site2": { "n_subjects": 9,  "mean_fd": 0.45, "mean_fd_perc": 11.7 },
            "site3": { "n_subjects": 15, "mean_fd": 0.29, "mean_fd_perc": 4.8 }
        }
    },
    "roi_values": {
        "reho": { "parcel_001": 0.417, "parcel_002": 0.371, "..." : "..." },
        "alff": { "parcel_001": 0.626, "parcel_002": 0.589, "..." : "..." },
        "_n_sites": 3,
        "_total_subjects": 36
    }
}
```
