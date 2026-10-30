**Source code:** [https://github.com/NeuroFlame/nfc-halfpipe](https://github.com/NeuroFlame/nfc-halfpipe)

&nbsp;

### Computation Description

#### Overview

This computation implements federated fMRI preprocessing and connectivity export using [HALFpipe](https://github.com/HALFpipe/HALFpipe), a reproducible neuroimaging pipeline built on fmriprep and FSL. Each participating site runs HALFpipe's full subject-level preprocessing and feature extraction pipeline on its local fMRI data. Only QC summary statistics — never raw images or individual-level data — are shared with the central aggregator. Per-subject connectivity matrices are written locally at each site as CSV files, ready for downstream federated analysis.

Four atlases are baked into the Docker image and used automatically:

- **Schaefer 2018 200-parcel 17-network** — 200 cortical parcels (MNI152NLin2009cAsym, 2mm). Produces `data_Schaefer200.csv` (19,900 FC columns per subject).
- **Schaefer 2018 400-parcel 17-network** — 400 cortical parcels. Produces `data_Schaefer400.csv` (79,800 FC columns per subject).
- **NeuroMark fMRI 1.0** ([Du et al., 2020](https://doi.org/10.1016/j.nicl.2020.102375)) — 53 ICA-derived functional network components across 7 functional domains. Produces `data_NeuroMark1.csv` (1,378 FC columns per subject).
- **Brainnetome Atlas 246** ([Fan et al., 2016](https://doi.org/10.1093/cercor/bhw157)) — 246 parcels (210 cortical, 36 subcortical). Produces `data_Brainnetome246.csv` (30,135 FC columns per subject).

One aggregation mode is supported:

- **`qc_metadata`** — collect motion and data-quality statistics (mean framewise displacement, FD percentage) across sites, producing a federated QC report. Always included.


#### Example

```json
{
    "run_halfpipe": true,
    "fs_license_path": "/workspace/license.txt",
    "aggregation_types": ["qc_metadata"],
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
                "datatype": "ref",
                "suffix": "atlas",
                "tags": { "desc": "Schaefer200" },
                "path": "/atlases/Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz"
            },
            {
                "datatype": "ref",
                "suffix": "atlas",
                "tags": { "desc": "Schaefer400" },
                "path": "/atlases/Schaefer2018_400Parcels_17Networks_order_FSLMNI152_2mm.nii.gz"
            },
            {
                "datatype": "ref",
                "suffix": "atlas",
                "tags": { "desc": "NeuroMark1" },
                "path": "/atlases/NeuroMark_1.0_parcellation.nii.gz"
            },
            {
                "datatype": "ref",
                "suffix": "atlas",
                "tags": { "desc": "Brainnetome246" },
                "path": "/atlases/BNA_246.nii.gz"
            }
        ],
        "settings": [
            {
                "name": "default",
                "ica_aroma": true,
                "bandpass_filter": { "type": "gaussian", "lp_width": 125.0 },
                "smoothing": { "fwhm": 6.0 },
                "grand_mean_scaling": { "mean": 10000.0 }
            }
        ],
        "features": [
            { "name": "reho",  "type": "reho",  "setting": "default" },
            { "name": "alff",  "type": "alff",  "setting": "default" },
            { "name": "connectivity",    "type": "atlas_based_connectivity",
              "setting": "default", "atlases": ["Schaefer200"],    "min_region_coverage": 0.8 },
            { "name": "connectivity400", "type": "atlas_based_connectivity",
              "setting": "default", "atlases": ["Schaefer400"],    "min_region_coverage": 0.8 },
            { "name": "neuromark",       "type": "atlas_based_connectivity",
              "setting": "default", "atlases": ["NeuroMark1"],     "min_region_coverage": 0.5 },
            { "name": "brainnetome",     "type": "atlas_based_connectivity",
              "setting": "default", "atlases": ["Brainnetome246"], "min_region_coverage": 0.8 }
        ],
        "models": []
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
| `aggregation_types` | `list[string]` | Which aggregation modes to run. Currently only `"qc_metadata"` is supported. | `"qc_metadata"` | `["qc_metadata"]` | ✅ Yes |
| `halfpipe_spec` | `object` | HALFpipe `spec.json` content. Defines input files, preprocessing settings, and features. Required when `run_halfpipe` is `true`. See [HALFpipe documentation](https://github.com/HALFpipe/HALFpipe) for the full spec format. File paths must use the `{bids_directory}` placeholder — see note below. | valid HALFpipe spec | — | Conditional |
| `fs_license_path` | `string` | Absolute path to a FreeSurfer license file inside the container. Required when `run_halfpipe` is `true` (fMRIPrep uses FreeSurfer for surface reconstruction). | any valid path | `/workspace/license.txt` | Conditional |
| `min_subjects` | `int` | Minimum number of successfully preprocessed subjects required at a site before it contributes data to the aggregation. | any positive integer | `1` | No |
| `n_procs` | `int` | Number of parallel processes to use when running HALFpipe. | any positive integer | `1` | No |


**Note on `{bids_directory}` in `halfpipe_spec`**: HALFpipe normally expects absolute paths in `spec.json`. In this computation, use `{bids_directory}` as a placeholder wherever a path should be rooted at the site's BIDS directory. The computation substitutes `{bids_directory}` with each site's actual data directory at runtime, so a single shared `halfpipe_spec` in `parameters.json` works across all sites without per-site path configuration.

`{sub}` is a standard HALFpipe placeholder expanded per-subject by HALFpipe itself. `{bids_directory}` is expanded by this computation before passing the spec to HALFpipe.


#### Input Description

**BIDS data directory**: Each site's data directory — the directory the site administrator points to in the NeuroFLAME UI — must be the BIDS root for that site. The computation receives this path automatically and uses it as the input to HALFpipe.

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

Each site's executor operates in one of the four modes described above. In all modes, HALFpipe's `atlas_based_connectivity` feature extracts the mean BOLD time series for every parcel in each atlas and computes the full N×N correlation matrix per subject.

After HALFpipe completes (or derivatives are read), the executor:
1. Reads all per-subject `*_correlation_matrix.tsv` files from the HALFpipe derivatives.
2. For each atlas, writes one `data_{AtlasName}.csv` to the output directory. Each row is one subject. Columns are the upper triangle of the correlation matrix, named `{feature_key}_{i:03d}x{j:03d}` (i < j, 1-indexed). Multiple subjects produce multiple rows.
3. Writes `labels.csv`, row-aligned with all data CSVs. Columns are `subject_id`, all demographic columns from BIDS `participants.tsv`, and HALFpipe per-subject QC metrics (`mean_fd`, `mean_fd_perc`, `mean_gm_tsnr`).
4. Extracts motion QC statistics (mean FD, FD percentage above threshold) and sends them to the server.

The server aggregates QC statistics from all sites using subject-count-weighted means.

**Phase 2 — Global Results Delivery (all sites)**

The server broadcasts the aggregated QC summary back to all sites. Each site saves the results to its output directory as `global_results.json` and `index.html`.


#### Assumptions

- HALFpipe and its neuroimaging dependencies (fmriprep, FSL, AFNI) are available in the Docker image used at each site when `run_halfpipe` is `true`. The production image (`coinstacteam/nfc-halfpipe`) is built on `halfpipe/halfpipe:1.3.2`.
- Each site's data directory (selected in the NeuroFLAME UI) is the BIDS root. File paths in `halfpipe_spec.files` use the `{bids_directory}` placeholder, which the computation substitutes with that path at runtime.
- The computation requires at least two participating sites.
- Sites with fewer than `min_subjects` successfully preprocessed subjects are excluded from aggregation.
- A FreeSurfer license file must be available inside the container at the path given by `fs_license_path` (default `/workspace/license.txt`) when `run_halfpipe` is `true`. The license file must not be committed to the repository; it should be mounted at runtime or copied to each site's data directory.


#### Output Description

Results are written to each site's output directory at the end of the computation.

| File | Description |
|---|---|
| `data_Schaefer200.csv` | Per-subject functional connectivity rows for the Schaefer 200-parcel atlas. One row per subject, 19,900 columns (upper triangle of 200×200 matrix). Column names: `{feature_key}_{i:03d}x{j:03d}`. |
| `data_Schaefer400.csv` | Same format for Schaefer 400-parcel atlas (79,800 columns). |
| `data_NeuroMark1.csv` | Same format for NeuroMark 1.0 53-IC atlas (1,378 columns). |
| `data_Brainnetome246.csv` | Same format for Brainnetome 246-parcel atlas (30,135 columns). |
| `labels.csv` | Per-subject metadata, row-aligned with all data CSVs. Columns: `subject_id`, all demographic columns from BIDS `participants.tsv`, then `mean_fd`, `mean_fd_perc`, `mean_gm_tsnr`. |
| `global_results.json` | Federated QC summary from the server: total subjects, n_sites, weighted mean motion statistics, and per-site breakdown. Always produced. |
| `index.html` | Self-contained interactive HTML report summarising QC metrics across sites. Open in any browser. |
| `halfpipe_reports/index.html` | HALFpipe's own per-subject QC report (preprocessing details, motion traces, registration figures). |

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
    }
}
```
