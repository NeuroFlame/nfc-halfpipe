### Computation Description

#### Overview

This computation implements federated fMRI analysis using [HALFpipe](https://github.com/HALFpipe/HALFpipe), a reproducible neuroimaging pipeline built on fmriprep and FSL. Each participating site runs HALFpipe's full subject-level preprocessing and feature extraction pipeline on its local fMRI data. Only summary statistics — never raw images or individual-level data — are shared with the central aggregator.

Three aggregation modes are supported and can be combined:

- **`qc_metadata`** — collect motion and data-quality statistics (mean framewise displacement, FD percentage) across sites, producing a federated QC report. Always runs as part of the first phase.
- **`roi_values`** — extract atlas-parcellated mean values from HALFpipe feature maps (e.g., ReHo, ALFF, seed-based connectivity) at each site, then compute weighted cross-site means per parcel.
- **`voxelwise_maps`** — each site runs a within-site group-level analysis using HALFpipe's `group-level` command, and the resulting statistical maps are combined at the server via a weighted meta-analysis.


#### Example

```json
{
    "run_halfpipe": true,
    "aggregation_types": ["qc_metadata", "roi_values"],
    "halfpipe_spec": {
        "version": "1.0.0",
        "files": [
            {
                "datatype": "func",
                "suffix": "bold",
                "tags": { "task": "rest" },
                "path": "/data/{subject}/func/{subject}_task-rest_bold.nii.gz"
            }
        ],
        "settings": [
            {
                "name": "default",
                "ica_aroma": true,
                "bandpass_filter": { "type": "gaussian", "lp_width": 125.0 }
            }
        ],
        "features": [
            { "name": "reho", "type": "reho", "setting": "default" },
            { "name": "alff", "type": "alff", "setting": "default" }
        ],
        "models": []
    },
    "roi_extraction": {
        "atlas_path": "/atlases/Schaefer2018_200Parcels_17Networks_order.nii.gz",
        "features": ["reho", "alff"]
    },
    "min_subjects": 5,
    "n_procs": 4
}
```


#### Settings Specification

| Variable Name | Type | Description | Allowed Options | Default | Required |
|---|---|---|---|---|---|
| `run_halfpipe` | `bool` | Whether to run HALFpipe on local data. Set to `false` to use pre-computed derivatives. | `true`, `false` | `true` | ✅ Yes |
| `aggregation_types` | `list[string]` | Which aggregation modes to run. Can be a single string or a list. | `"qc_metadata"`, `"roi_values"`, `"voxelwise_maps"` | `["qc_metadata"]` | ✅ Yes |
| `halfpipe_spec` | `object` | Full HALFpipe `spec.json` content. Defines input files, preprocessing settings, and features. Required when `run_halfpipe` is `true`. | valid HALFpipe spec | — | Conditional |
| `roi_extraction.atlas_path` | `string` | Absolute path to an integer-labeled parcellation atlas NIfTI file (`.nii` or `.nii.gz`). Each unique nonzero integer is treated as one parcel. Required when `"roi_values"` is in `aggregation_types`. | any valid path | — | Conditional |
| `roi_extraction.features` | `list[string]` | HALFpipe feature names to extract ROI values from. Must match feature names defined in `halfpipe_spec`. | e.g. `["reho", "alff"]` | `[]` | Conditional |
| `voxelwise_maps.spreadsheet` | `string` | Path to a covariate spreadsheet for within-site group-level analysis. Used only when `"voxelwise_maps"` is in `aggregation_types`. | any valid path | `null` | No |
| `voxelwise_maps.covariates` | `list[string]` | Covariate column names to include in the within-site group-level design matrix. | list of strings | `[]` | No |
| `min_subjects` | `int` | Minimum number of successfully preprocessed subjects required at a site before it contributes data to the aggregation. | any positive integer | `1` | No |
| `n_procs` | `int` | Number of parallel processes to use when running HALFpipe. | any positive integer | `1` | No |


#### Input Description

Each site requires a `data.json` file in its data directory.

```json
{
    "bids_directory": "/path/to/site/bids",
    "derivatives_directory": "/path/to/existing/halfpipe/derivatives"
}
```

| Field | Type | Description | Required |
|---|---|---|---|
| `bids_directory` | `string` | Absolute path to the site's BIDS-formatted (or HALFpipe-compatible) fMRI data directory. Required when `run_halfpipe` is `true`. | Conditional |
| `derivatives_directory` | `string` | Absolute path to an existing HALFpipe derivatives directory (`derivatives/halfpipe/`). Overrides automatic derivative discovery when provided. | No |

HALFpipe does not require strict BIDS formatting; file paths can be specified using glob patterns in `halfpipe_spec.files`. Refer to the [HALFpipe documentation](https://github.com/HALFpipe/HALFpipe) for supported input formats.

**Note for simulation / development**: Set `"run_halfpipe": false` in `parameters.json` and add a `"mock_derivatives"` key to `data.json` with pre-computed values (see the `test_data/` directory for examples). This allows the full federated workflow to be tested without a HALFpipe installation or fMRI data.

---

#### Algorithm Description

The computation runs in three phases:

**Phase 1 — Subject-Level Processing (all sites)**

Each site's executor:
1. Writes the provided `halfpipe_spec` to a local working directory and invokes HALFpipe (skipped when `run_halfpipe` is `false`).
2. HALFpipe runs fmriprep preprocessing followed by single-subject feature extraction (ReHo, ALFF, seed correlation, task contrasts, etc.) for every subject.
3. Motion QC statistics (mean framewise displacement, FD percentage above threshold) are extracted from the HALFpipe derivatives and sent to the server.

The server aggregates QC statistics from all sites using weighted means (weighted by each site's subject count).

**Phase 2a — ROI Value Extraction** *(only when `"roi_values"` is in `aggregation_types`)*

Each site's executor:
1. Loads each requested HALFpipe feature map (NIfTI) for every successfully preprocessed subject.
2. Applies the provided atlas parcellation: for each parcel, computes the mean signal value across voxels within the parcel and averages across subjects.
3. Sends the resulting `{feature → {parcel → mean_value}}` dictionary and subject count to the server.

The server computes a cross-site weighted mean for each feature × parcel combination.

**Phase 2b — Voxelwise Meta-Analysis** *(only when `"voxelwise_maps"` is in `aggregation_types`)*

Each site's executor:
1. Runs `halfpipe group-level` locally using the site's subjects and optional covariate spreadsheet.
2. The resulting statistical maps (effect, variance, z-stat) are compressed and sent to the server.

The server performs a subject-count-weighted average across the site-level statistical maps to produce a federated group-level result. (Future versions will implement a proper fixed-effects or mixed-effects meta-analysis.)

**Phase 3 — Global Results Delivery (all sites)**

The server broadcasts the aggregated results (QC summary, global ROI values, and/or meta-analysis maps) back to all sites. Each site saves the global results to its output directory.


#### Assumptions

- HALFpipe and its neuroimaging dependencies (fmriprep, FSL, AFNI) are available in the Docker image used at each site when `run_halfpipe` is `true`. Use `ghcr.io/halfpipe/halfpipe:latest` as the base image.
- Each site's fMRI data is organized according to the path patterns specified in `halfpipe_spec.files`.
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
