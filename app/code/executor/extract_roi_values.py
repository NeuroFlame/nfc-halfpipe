import csv
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
) -> dict:
    """
    Write per-subject parcel values to a CSV compatible with nfc-combatdc.

    Each row is one subject; columns are {feature}_{parcel_label} for every
    feature × parcel combination. No subject_id column — nfc-combatdc expects
    an all-numeric data matrix (pd.read_csv with all columns cast to float).

    The output filename is configurable via params["subject_csv_config"]["data_file"];
    defaults to "subject_data.csv". Set nfc-combatdc's "data_file" parameter to
    this same filename so it reads the file nfc-halfpipe produces.

    Returns: {"path": str, "n_subjects": int, "n_columns": int}
    """
    csv_config = params.get("subject_csv_config", {})
    data_filename = csv_config.get("data_file", "subject_data.csv")
    features = csv_config.get("features") or params.get("roi_extraction", {}).get("features", [])

    if not features:
        logging.warning("No features configured for subject_csv — skipping CSV write")
        return {"path": None, "n_subjects": 0, "n_columns": 0}

    if derivatives_path is None:
        return _write_mock_subject_csv(site_data, features, output_dir, data_filename)

    atlas_path = params.get("roi_extraction", {}).get("atlas_path")
    if not atlas_path:
        logging.warning("No atlas_path in roi_extraction — cannot write subject CSV")
        return {"path": None, "n_subjects": 0, "n_columns": 0}

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
        logging.warning("No subject data extracted — subject CSV not written")
        return {"path": None, "n_subjects": 0, "n_columns": 0}

    # Column order: all features × all parcels, in the order features were requested
    columns = [
        f"{feature}_parcel_{p:03d}"
        for feature in features
        for p in parcel_ids
        if any(f"{feature}_parcel_{p:03d}" in row for row in subject_rows.values())
    ]

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, data_filename)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", restval="")
        writer.writeheader()
        for subject_id in sorted(subject_rows.keys()):
            writer.writerow(subject_rows[subject_id])

    logging.info(
        f"Subject CSV written: {len(subject_rows)} subjects × {len(columns)} columns → {output_path}"
    )
    return {"path": output_path, "n_subjects": len(subject_rows), "n_columns": len(columns)}


def _write_mock_subject_csv(
    site_data: dict,
    features: list,
    output_dir: str,
    data_filename: str,
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
        return {"path": None, "n_subjects": 0, "n_columns": 0}

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, data_filename)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for _ in range(n_subjects):
            writer.writerow(row_template)

    logging.info(
        f"Mock subject CSV written: {n_subjects} subjects × {len(columns)} columns → {output_path}"
    )
    return {"path": output_path, "n_subjects": n_subjects, "n_columns": len(columns)}


def _subject_id_from_path(nifti_path) -> str:
    m = re.search(r"/sub-([^/]+)/", str(nifti_path))
    return m.group(1) if m else Path(nifti_path).stem
