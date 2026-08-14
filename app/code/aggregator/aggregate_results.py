"""
Aggregation functions for the HALFpipe federated modes.
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


# ------------------------------------------------------------------ #
# Atlas connectivity aggregation                                       #
# ------------------------------------------------------------------ #

def aggregate_connectivity(site_results: Dict[str, dict]) -> dict:
    """
    Federate per-atlas connectivity matrices across sites.

    Each site provides (from ``SEND_ATLAS_CONNECTIVITY``)::

        {
            "n_subjects": int,
            "connectivity": {
                "{feature}_atlas-{atlas}": {
                    "mean_fisher_z_matrix": list[list[float]],  # N×N
                    "n_subjects": int,
                    "n_parcels": int,
                }
            }
        }

    Federation strategy:
        1. Each site already sent its within-site mean Fisher-z matrix.
        2. Compute cross-site weighted mean (weight = n_subjects per site per atlas).
        3. Back-transform with tanh() → federated mean correlation matrix.

    Returns::

        {
            "matrices": {
                "{feature}_atlas-{atlas}": {
                    "mean_correlation_matrix": list[list[float]],
                    "n_parcels": int,
                    "n_sites": int,
                    "total_subjects": int,
                }
            },
            "n_sites": int,
            "total_subjects": int,
        }
    """
    try:
        import numpy as np
    except ImportError:
        return {"status": "numpy_not_available", "n_sites": len(site_results)}

    n_sites = len(site_results)

    # Collect all atlas keys present across any site
    all_keys: set = set()
    for result in site_results.values():
        all_keys.update(result.get("connectivity", {}).keys())

    global_connectivity: dict = {}
    grand_total_subjects = 0

    for key in sorted(all_keys):
        z_weighted_sum: Optional[Any] = None
        total_n = 0
        n_parcels = None

        for site_result in site_results.values():
            entry = site_result.get("connectivity", {}).get(key)
            if entry is None:
                continue
            n = entry.get("n_subjects", 0)
            z_matrix = entry.get("mean_fisher_z_matrix")
            if not z_matrix or n == 0:
                continue

            z_arr = np.array(z_matrix, dtype=float)
            if n_parcels is None:
                n_parcels = z_arr.shape[0]
            elif z_arr.shape[0] != n_parcels:
                import logging
                logging.warning(
                    f"Parcel count mismatch for '{key}' across sites "
                    f"({z_arr.shape[0]} vs {n_parcels}) — skipping site"
                )
                continue

            z_weighted_sum = (z_arr * n) if z_weighted_sum is None else z_weighted_sum + z_arr * n
            total_n += n

        if z_weighted_sum is None or total_n == 0 or n_parcels is None:
            continue

        mean_z = z_weighted_sum / total_n
        mean_r = np.tanh(mean_z)

        # Enforce unit diagonal (tanh(arctanh(1)) may drift slightly)
        np.fill_diagonal(mean_r, 1.0)

        global_connectivity[key] = {
            "mean_correlation_matrix": mean_r.tolist(),
            "n_parcels": n_parcels,
            "n_sites": n_sites,
            "total_subjects": total_n,
        }
        grand_total_subjects = max(grand_total_subjects, total_n)

    return {
        "matrices": global_connectivity,
        "n_sites": n_sites,
        "total_subjects": grand_total_subjects,
    }
