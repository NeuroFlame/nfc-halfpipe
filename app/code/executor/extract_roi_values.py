import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional


def extract_roi_values(
    derivatives_path: Optional[str],
    site_data: dict,
    params: dict,
) -> dict:
    """
    Extract atlas-parcellated mean values from HALFpipe feature maps.

    When derivatives_path is None (run_halfpipe=false), returns pre-computed
    mock values from site_data["mock_derivatives"]["roi_values"].

    For real data, requires nibabel and a parcellation atlas NIfTI. The atlas
    is expected to be an integer-labeled NIfTI where each unique nonzero integer
    is one parcel.

    Returns:
        {feature_name: {parcel_label: mean_value, ...}, ...}
    """
    if derivatives_path is None:
        mock = site_data.get("mock_derivatives", {})
        roi_values = mock.get("roi_values", {})
        logging.info(f"Using mock ROI values for features: {list(roi_values.keys())}")
        return roi_values

    roi_config = params.get("roi_extraction", {})
    features = roi_config.get("features", [])
    atlas_path = roi_config.get("atlas_path")

    if not features:
        logging.warning("No features specified in roi_extraction.features — returning empty ROI values")
        return {}

    if atlas_path is None:
        logging.warning("No atlas_path specified in roi_extraction — cannot extract ROI values")
        return {}

    try:
        import nibabel as nib
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "nibabel and numpy are required for ROI extraction. "
            "Install them via: pip install nibabel numpy"
        )

    atlas_img = nib.load(atlas_path)
    atlas_data = np.asarray(atlas_img.dataobj).astype(int)
    parcel_ids = [int(p) for p in np.unique(atlas_data) if p != 0]
    logging.info(f"Atlas loaded: {len(parcel_ids)} parcels from {atlas_path}")

    roi_values: dict = {}

    for feature in features:
        # HALFpipe 1.3.x writes feature maps as BIDS sidecars under sub-*/func/:
        #   *_feature-{feature}_{feature}.nii.gz  (or .nii)
        # The feature name appears as both the BIDS 'feature' entity and the suffix,
        # which distinguishes the primary map from masks (*_mask.nii.gz) and
        # companion maps (e.g. alff.nii.gz produced alongside falff).
        root = Path(derivatives_path)
        nifti_files = (
            list(root.rglob(f"*_feature-{feature}_{feature}.nii.gz")) +
            list(root.rglob(f"*_feature-{feature}_{feature}.nii"))
        )
        if not nifti_files:
            logging.warning(f"No NIfTI maps found for feature '{feature}' under {derivatives_path}")
            continue

        # Accumulate parcellated values across subjects
        parcel_sums: dict = {p: 0.0 for p in parcel_ids}
        parcel_counts: dict = {p: 0 for p in parcel_ids}

        for nifti_path in nifti_files:
            try:
                img = nib.load(str(nifti_path))
                data = np.asarray(img.dataobj)
                for parcel_id in parcel_ids:
                    mask = atlas_data == parcel_id
                    values_in_parcel = data[mask]
                    finite_values = values_in_parcel[np.isfinite(values_in_parcel)]
                    if len(finite_values) > 0:
                        parcel_sums[parcel_id] += float(np.mean(finite_values))
                        parcel_counts[parcel_id] += 1
            except Exception as e:
                logging.warning(f"Could not process {nifti_path}: {e}")

        roi_values[feature] = {
            f"parcel_{p:03d}": (parcel_sums[p] / parcel_counts[p] if parcel_counts[p] > 0 else None)
            for p in parcel_ids
        }
        logging.info(f"Extracted ROI values for feature '{feature}': {len(parcel_ids)} parcels from {len(nifti_files)} subjects")

    return roi_values


def write_subject_roi_csv(
    derivatives_path: Optional[str],
    site_data: dict,
    params: dict,
    output_dir: str,
    bids_directory: Optional[str] = None,
) -> dict:
    """
    Write per-subject parcel values and a covariate file for nfc-combatdc.

    Produces two files in output_dir:

    Data.csv (configurable via subject_csv_config.data_file):
        All-numeric matrix — one row per subject, columns are
        {feature}_{parcel_label} for every feature × parcel combination.
        No subject_id column; nfc-combatdc reads this with pd.read_csv and
        casts every column to float.

    Covariate.csv (configurable via subject_csv_config.covariate_file):
        One row per subject, row-aligned with Data.csv. Populated from:
          1. BIDS participants.tsv at {bids_directory}/participants.tsv
             (all columns except participant_id, which becomes subject_id)
          2. Per-subject HALFpipe QC metrics from feature JSON sidecars
             (mean_fd, mean_fd_perc, mean_gm_tsnr)
        In mock mode or when bids_directory is absent, contains only a
        subject_id column as a template for the site administrator.

    Set nfc-combatdc's parameters.json:
        "data_file": "Data.csv"
        "covariate_file": "Covariate.csv"

    Returns: {"data_path": str, "covariate_path": str, "n_subjects": int, "n_columns": int}
    """
    csv_config = params.get("subject_csv_config", {})
    data_filename = csv_config.get("data_file", "Data.csv")
    covariate_filename = csv_config.get("covariate_file", "Covariate.csv")
    features = csv_config.get("features") or params.get("roi_extraction", {}).get("features", [])

    if not features:
        logging.warning("No features configured for subject_csv — skipping CSV write")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    if derivatives_path is None:
        return _write_mock_subject_csvs(site_data, features, output_dir, data_filename, covariate_filename)

    atlas_path = params.get("roi_extraction", {}).get("atlas_path")
    if not atlas_path:
        logging.warning("No atlas_path in roi_extraction — cannot write subject CSVs")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    try:
        import nibabel as nib
        import numpy as np
    except ImportError:
        raise RuntimeError("nibabel and numpy are required for subject CSV extraction")

    atlas_img = nib.load(atlas_path)
    atlas_data = np.asarray(atlas_img.dataobj).astype(int)
    parcel_ids = [int(p) for p in np.unique(atlas_data) if p != 0]

    # subject_id -> {column_name: value}
    subject_rows: dict = {}

    for feature in features:
        root = Path(derivatives_path)
        nifti_files = (
            list(root.rglob(f"*_feature-{feature}_{feature}.nii.gz")) +
            list(root.rglob(f"*_feature-{feature}_{feature}.nii"))
        )
        if not nifti_files:
            logging.warning(f"No NIfTI maps found for feature '{feature}' — skipping in subject CSV")
            continue

        for nifti_path in nifti_files:
            subject_id = _subject_id_from_path(nifti_path)
            try:
                img = nib.load(str(nifti_path))
                data = np.asarray(img.dataobj)
                row = subject_rows.setdefault(subject_id, {})
                for parcel_id in parcel_ids:
                    mask = atlas_data == parcel_id
                    values_in_parcel = data[mask]
                    finite_vals = values_in_parcel[np.isfinite(values_in_parcel)]
                    col = f"{feature}_parcel_{parcel_id:03d}"
                    row[col] = float(np.mean(finite_vals)) if len(finite_vals) > 0 else ""
            except Exception as e:
                logging.warning(f"Could not process {nifti_path}: {e}")

    if not subject_rows:
        logging.warning("No subject data extracted — subject CSVs not written")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    # Stable subject order used for both files so rows align
    subject_order = sorted(subject_rows.keys())

    # Column order: all features × all parcels in requested feature order
    data_columns = [
        f"{feature}_parcel_{p:03d}"
        for feature in features
        for p in parcel_ids
        if any(f"{feature}_parcel_{p:03d}" in row for row in subject_rows.values())
    ]

    os.makedirs(output_dir, exist_ok=True)

    # --- Data.csv (all-numeric, no subject_id) ---
    data_path = os.path.join(output_dir, data_filename)
    with open(data_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data_columns, extrasaction="ignore", restval="")
        writer.writeheader()
        for subject_id in subject_order:
            writer.writerow(subject_rows[subject_id])

    # --- Covariate.csv (subject_id + demographics + QC) ---
    covariate_rows, covariate_columns = _build_covariate_rows(
        subject_order=subject_order,
        bids_directory=bids_directory,
        derivatives_path=derivatives_path,
    )
    covariate_path = os.path.join(output_dir, covariate_filename)
    with open(covariate_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=covariate_columns, extrasaction="ignore", restval="")
        writer.writeheader()
        for row in covariate_rows:
            writer.writerow(row)

    logging.info(
        f"Data.csv written: {len(subject_order)} subjects × {len(data_columns)} columns → {data_path}"
    )
    logging.info(
        f"Covariate.csv written: {len(subject_order)} subjects × {len(covariate_columns)} columns → {covariate_path}"
    )
    return {
        "data_path": data_path,
        "covariate_path": covariate_path,
        "n_subjects": len(subject_order),
        "n_columns": len(data_columns),
    }


def _build_covariate_rows(
    subject_order: list,
    bids_directory: Optional[str],
    derivatives_path: Optional[str],
) -> tuple:
    """
    Build covariate rows by joining participants.tsv and per-subject QC metrics.

    Returns (rows, columns) where rows is a list of dicts aligned with
    subject_order and columns is the ordered list of fieldnames.
    """
    # Base: subject_id for each subject
    rows = {sub: {"subject_id": f"sub-{sub}"} for sub in subject_order}

    # Track column order: subject_id first, then participants.tsv cols, then QC
    participants_cols: list = []
    qc_cols: list = []

    # 1. participants.tsv — BIDS standard demographic file
    if bids_directory:
        ptsp = os.path.join(bids_directory, "participants.tsv")
        if os.path.exists(ptsp):
            try:
                with open(ptsp, newline="") as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    if reader.fieldnames:
                        participants_cols = [
                            col for col in reader.fieldnames
                            if col != "participant_id"
                        ]
                    for record in reader:
                        pid = record.get("participant_id", "")
                        # participant_id is "sub-B04"; strip prefix to get bare ID
                        sub = pid[4:] if pid.startswith("sub-") else pid
                        if sub in rows:
                            for col in participants_cols:
                                rows[sub][col] = record.get(col, "")
                logging.info(
                    f"Merged {len(participants_cols)} columns from participants.tsv"
                )
            except Exception as e:
                logging.warning(f"Could not read participants.tsv: {e}")

    # 2. Per-subject QC from HALFpipe feature JSON sidecars
    if derivatives_path:
        qc_per_sub = _extract_per_subject_qc(derivatives_path)
        for sub, qc in qc_per_sub.items():
            if sub in rows:
                rows[sub].update(qc)
        if qc_per_sub:
            # Collect QC column names from whichever subject had data
            seen = set()
            for qc in qc_per_sub.values():
                for k in qc:
                    if k not in seen:
                        qc_cols.append(k)
                        seen.add(k)
            logging.info(f"Merged per-subject QC columns: {qc_cols}")

    all_columns = ["subject_id"] + participants_cols + qc_cols
    return [rows[sub] for sub in subject_order], all_columns


def _extract_per_subject_qc(derivatives_path: str) -> dict:
    """
    Return {bare_subject_id: {"mean_fd": ..., "mean_fd_perc": ..., "mean_gm_tsnr": ...}}
    by reading HALFpipe 1.3.x feature JSON sidecars for each subject directory.
    Mirrors the logic in run_halfpipe._extract_qc_from_derivatives but per-subject.
    """
    result: dict = {}
    if not os.path.isdir(derivatives_path):
        return result

    for subject_dir in Path(derivatives_path).iterdir():
        if not subject_dir.is_dir() or not subject_dir.name.startswith("sub-"):
            continue
        subject_id = subject_dir.name[4:]  # strip "sub-"

        fd_vals, fd_perc_vals, tsnr_vals = [], [], []
        seen_runs: set = set()

        for sidecar in subject_dir.rglob("*_feature-*_*.json"):
            parts = sidecar.stem.split("_")
            run_key = tuple(p for p in parts if p.startswith(("task-", "run-", "ses-")))
            if run_key in seen_runs:
                continue
            try:
                with open(sidecar) as f:
                    vals = json.load(f)
                if "FDMean" not in vals:
                    continue
                seen_runs.add(run_key)
                fd_vals.append(float(vals["FDMean"]))
                if "FDPerc" in vals:
                    fd_perc_vals.append(float(vals["FDPerc"]))
                if "MeanGMTSNR" in vals:
                    tsnr_vals.append(float(vals["MeanGMTSNR"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        sub_qc: dict = {}
        if fd_vals:
            sub_qc["mean_fd"] = round(sum(fd_vals) / len(fd_vals), 4)
        if fd_perc_vals:
            sub_qc["mean_fd_perc"] = round(sum(fd_perc_vals) / len(fd_perc_vals), 4)
        if tsnr_vals:
            sub_qc["mean_gm_tsnr"] = round(sum(tsnr_vals) / len(tsnr_vals), 4)

        if sub_qc:
            result[subject_id] = sub_qc

    return result


def _write_mock_subject_csvs(
    site_data: dict,
    features: list,
    output_dir: str,
    data_filename: str,
    covariate_filename: str,
) -> dict:
    mock = site_data.get("mock_derivatives", {})
    n_subjects = mock.get("n_subjects", 1)
    roi_values = mock.get("roi_values", {})

    # Columns: {feature}_{parcel_label} — parcel_label already includes "parcel_" prefix
    columns = []
    row_template: dict = {}
    for feature in features:
        parcels = roi_values.get(feature, {})
        for parcel_label, value in parcels.items():
            col = f"{feature}_{parcel_label}"
            columns.append(col)
            row_template[col] = value if value is not None else ""

    if not columns:
        logging.warning("No mock ROI values found for subject CSV features")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    # subject_ids as sub-001 … sub-NNN, zero-padded to match n_subjects width
    width = len(str(n_subjects))
    subject_ids = [f"sub-{i:0{width}d}" for i in range(1, n_subjects + 1)]

    os.makedirs(output_dir, exist_ok=True)

    data_path = os.path.join(output_dir, data_filename)
    with open(data_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for _ in subject_ids:
            writer.writerow(row_template)

    # Mock Covariate.csv: subject_id only — no real demographics available
    covariate_path = os.path.join(output_dir, covariate_filename)
    with open(covariate_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["subject_id"])
        writer.writeheader()
        for subject_id in subject_ids:
            writer.writerow({"subject_id": subject_id})

    logging.info(
        f"Mock Data.csv written: {n_subjects} subjects × {len(columns)} columns → {data_path}"
    )
    logging.info(
        f"Mock Covariate.csv written: {n_subjects} subjects (subject_id only — no real demographics in mock mode) → {covariate_path}"
    )
    return {
        "data_path": data_path,
        "covariate_path": covariate_path,
        "n_subjects": n_subjects,
        "n_columns": len(columns),
    }


def _subject_id_from_path(nifti_path) -> str:
    m = re.search(r"/sub-([^/]+)/", str(nifti_path))
    return m.group(1) if m else Path(nifti_path).stem
