"""
Aggregation functions for the three HALFpipe federated modes.
"""
from typing import Any, Dict, Optional


# ------------------------------------------------------------------ #
# QC metadata aggregation                                             #
# ------------------------------------------------------------------ #

def aggregate_qc_metadata(site_results: Dict[str, dict]) -> dict:
    """
    Combine QC statistics across sites using weighted means.

    Returns a dict with total_subjects, n_sites, weighted means for each
    QC metric, and per-site summaries.
    """
    total_subjects = 0
    qc_keys: set = set()

    for result in site_results.values():
        total_subjects += result.get("n_subjects", 0)
        qc_keys.update(result.get("qc_summary", {}).keys())

    weighted_qc: dict = {}
    for key in qc_keys:
        weighted_sum = 0.0
        total_n = 0
        for result in site_results.values():
            n = result.get("n_subjects", 0)
            val = result.get("qc_summary", {}).get(key)
            if val is not None and isinstance(val, (int, float)) and n > 0:
                weighted_sum += float(val) * n
                total_n += n
        if total_n > 0:
            weighted_qc[f"mean_{key}"] = round(weighted_sum / total_n, 6)

    return {
        "total_subjects": total_subjects,
        "n_sites": len(site_results),
        **weighted_qc,
        "site_summaries": {
            site: {
                "n_subjects": r.get("n_subjects", 0),
                **r.get("qc_summary", {}),
            }
            for site, r in site_results.items()
        },
    }


# ------------------------------------------------------------------ #
# ROI value aggregation                                               #
# ------------------------------------------------------------------ #

def aggregate_roi_values(site_results: Dict[str, dict]) -> dict:
    """
    Compute weighted cross-site mean for each feature × parcel combination.

    Each site provides:
        {"roi_values": {feature: {parcel: value}}, "n_subjects": N}

    Returns:
        {
            feature: {parcel: global_mean},
            ...
            "_n_sites": N,
            "_total_subjects": M,
        }
    """
    all_features: set = set()
    for result in site_results.values():
        all_features.update(result.get("roi_values", {}).keys())

    global_roi: dict = {}
    total_subjects = 0

    for feature in all_features:
        all_parcels: set = set()
        for result in site_results.values():
            all_parcels.update(result.get("roi_values", {}).get(feature, {}).keys())

        parcel_means: dict = {}
        for parcel in all_parcels:
            weighted_sum = 0.0
            total_n = 0
            for result in site_results.values():
                n = result.get("n_subjects", 0)
                val = result.get("roi_values", {}).get(feature, {}).get(parcel)
                if val is not None and isinstance(val, (int, float)) and n > 0:
                    weighted_sum += float(val) * n
                    total_n += n
            parcel_means[parcel] = round(weighted_sum / total_n, 6) if total_n > 0 else None

        global_roi[feature] = parcel_means

    for result in site_results.values():
        total_subjects += result.get("n_subjects", 0)

    global_roi["_n_sites"] = len(site_results)
    global_roi["_total_subjects"] = total_subjects
    return global_roi


# ------------------------------------------------------------------ #
# Voxelwise meta-analysis                                             #
# ------------------------------------------------------------------ #

def aggregate_voxelwise(site_results: Dict[str, dict]) -> dict:
    """
    Perform cross-site meta-analysis of site-level statistical maps.

    Currently implements a simple average of the base64-encoded NIfTI
    data via nibabel + numpy if available. Falls back to returning a
    catalogue of available maps when nibabel is not installed.

    Each site provides:
        {"site_stats": {map_key: <base64-nii.gz>}, "n_subjects": N}
    """
    all_map_keys: set = set()
    for result in site_results.values():
        all_map_keys.update(result.get("site_stats", {}).keys())

    n_sites = len(site_results)
    total_subjects = sum(r.get("n_subjects", 0) for r in site_results.values())

    try:
        import base64
        import io
        import nibabel as nib
        import numpy as np

        meta_maps: dict = {}
        for map_key in all_map_keys:
            stat_arrays = []
            weights = []
            affine = None
            header = None

            for result in site_results.values():
                encoded = result.get("site_stats", {}).get(map_key)
                n = result.get("n_subjects", 0)
                if encoded is None or n == 0:
                    continue
                nifti_bytes = base64.b64decode(encoded)
                img = nib.load(io.BytesIO(nifti_bytes))
                stat_arrays.append(np.asarray(img.dataobj))
                weights.append(n)
                if affine is None:
                    affine = img.affine
                    header = img.header

            if not stat_arrays:
                continue

            weights_arr = np.array(weights, dtype=float)
            weights_arr /= weights_arr.sum()
            combined = sum(w * arr for w, arr in zip(weights_arr, stat_arrays))

            combined_img = nib.Nifti1Image(combined.astype(np.float32), affine, header)
            buf = io.BytesIO()
            combined_img.to_file_map({"image": nib.FileHolder(fileobj=buf)})
            meta_maps[map_key] = base64.b64encode(buf.getvalue()).decode("ascii")

        return {
            "meta_maps": meta_maps,
            "n_sites": n_sites,
            "total_subjects": total_subjects,
        }

    except ImportError:
        return {
            "status": "nibabel_not_available",
            "available_map_keys": list(all_map_keys),
            "n_sites": n_sites,
            "total_subjects": total_subjects,
        }
