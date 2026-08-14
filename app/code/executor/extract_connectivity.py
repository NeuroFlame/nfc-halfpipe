"""
Extract atlas-based connectivity matrices from HALFpipe derivatives.

HALFpipe's ``atlas_based_connectivity`` feature produces per-subject
correlation matrix TSV files (one per atlas per run). This module:

  - Discovers those files under the derivatives tree
  - Applies a Fisher z-transformation to each subject's matrix
  - Averages across subjects at the site level
  - Returns the site-mean Fisher-z matrix ready for federation

Federation strategy (implemented in aggregator/aggregate_results.py):
  1. Each site sends its per-atlas mean Fisher-z matrix + subject count.
  2. The server computes a subject-count-weighted mean across sites.
  3. Back-transform via tanh() yields the federated correlation matrix.

This approach is numerically stable and produces results equivalent to
the well-known "average Fisher r-to-z" method used in FC meta-analysis.
"""

import logging
import math
import re
from pathlib import Path
from typing import Optional


def extract_connectivity_matrices(
    derivatives_path: Optional[str],
    site_data: dict,
    params: dict,
) -> dict:
    """
    Compute site-mean Fisher-z connectivity matrices per atlas.

    Parameters
    ----------
    derivatives_path:
        Path to the HALFpipe derivatives directory (``derivatives/halfpipe``).
        When ``None`` (mock mode), returns mock data from ``site_data``.
    site_data:
        Site-local configuration loaded from ``data.json``.
    params:
        Computation parameters from ``parameters.json``.

    Returns
    -------
    dict
        Keys are ``"{feature_name}_atlas-{atlas_name}"`` (e.g.
        ``"connectivity_atlas-Schaefer200"``). Values are::

            {
                "mean_fisher_z_matrix": list[list[float]],  # N×N
                "n_subjects": int,
                "n_parcels": int,
            }
    """
    if derivatives_path is None:
        return _mock_connectivity(site_data, params)

    try:
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "numpy is required for connectivity matrix extraction. "
            "Install via: pip install numpy"
        )

    root = Path(derivatives_path)
    corr_files = list(root.rglob("*_correlation_matrix.tsv"))

    if not corr_files:
        logging.warning(
            f"No correlation_matrix.tsv files found under {derivatives_path}. "
            "Did you include an 'atlas_based_connectivity' feature in halfpipe_spec?"
        )
        return {}

    # Group files by (feature, atlas) — one group → one federated matrix
    grouped: dict = {}
    for path in corr_files:
        m = re.search(
            r"_feature-([^_]+)_atlas-([^_]+)_correlation_matrix\.tsv$",
            path.name,
        )
        if not m:
            logging.debug(f"Skipping unrecognised filename: {path.name}")
            continue
        feature_name, atlas_name = m.group(1), m.group(2)
        key = f"{feature_name}_atlas-{atlas_name}"
        grouped.setdefault(key, []).append(path)

    if not grouped:
        logging.warning(
            "Found .tsv files but none matched the expected "
            "'*_feature-{feat}_atlas-{atlas}_correlation_matrix.tsv' pattern"
        )
        return {}

    results: dict = {}

    for key, file_list in grouped.items():
        z_sum = None
        n_subjects = 0
        n_parcels = None

        for tsv_path in file_list:
            try:
                matrix = np.loadtxt(str(tsv_path), delimiter="\t")
            except Exception as exc:
                logging.warning(f"Could not load {tsv_path}: {exc}")
                continue

            if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
                logging.warning(
                    f"Unexpected shape {matrix.shape} in {tsv_path} — skipping"
                )
                continue

            if n_parcels is None:
                n_parcels = matrix.shape[0]
            elif matrix.shape[0] != n_parcels:
                logging.warning(
                    f"Parcel count mismatch ({matrix.shape[0]} vs {n_parcels}) "
                    f"in {tsv_path} — skipping"
                )
                continue

            # Fisher z-transform: arctanh(r), clipped to avoid ±∞ on the diagonal
            z = np.arctanh(np.clip(matrix, -0.9999, 0.9999))

            z_sum = z if z_sum is None else z_sum + z
            n_subjects += 1

        if z_sum is None or n_subjects == 0:
            logging.warning(f"No valid correlation matrices for '{key}'")
            continue

        mean_z = (z_sum / n_subjects).tolist()
        results[key] = {
            "mean_fisher_z_matrix": mean_z,
            "n_subjects": n_subjects,
            "n_parcels": n_parcels,
        }
        logging.info(
            f"Atlas connectivity '{key}': "
            f"{n_subjects} subject(s), {n_parcels}×{n_parcels} parcels"
        )

    return results


# ------------------------------------------------------------------ #
# Mock mode                                                           #
# ------------------------------------------------------------------ #

def _mock_connectivity(site_data: dict, params: dict) -> dict:
    """
    Return mock connectivity data for development / testing.

    Reads ``site_data["mock_derivatives"]["connectivity"]`` when present;
    otherwise synthesises a small 5×5 block-diagonal correlation matrix
    so the end-to-end federation protocol can be tested without real data.
    """
    mock = site_data.get("mock_derivatives", {})
    stored = mock.get("connectivity")
    if stored:
        logging.info(
            f"Mock connectivity: using pre-stored data for keys: {list(stored.keys())}"
        )
        return stored

    # Synthesise a 5×5 block-diagonal-ish correlation matrix.
    # This is deterministic so aggregated output is reproducible.
    n = 5
    n_subjects = mock.get("n_subjects", 1)
    r = [
        [1.00, 0.65, 0.20, 0.10, 0.15],
        [0.65, 1.00, 0.18, 0.12, 0.08],
        [0.20, 0.18, 1.00, 0.55, 0.25],
        [0.10, 0.12, 0.55, 1.00, 0.60],
        [0.15, 0.08, 0.25, 0.60, 1.00],
    ]
    z = [[round(math.atanh(max(-0.9999, min(0.9999, r[i][j]))), 6)
          for j in range(n)] for i in range(n)]

    key = "connectivity_atlas-mock5"
    logging.info(
        f"Mock connectivity: synthesised {n}×{n} matrix for '{key}' "
        f"({n_subjects} subjects)"
    )
    return {
        key: {
            "mean_fisher_z_matrix": z,
            "n_subjects": n_subjects,
            "n_parcels": n,
        }
    }
