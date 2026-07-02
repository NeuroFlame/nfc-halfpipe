import logging
import os
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
