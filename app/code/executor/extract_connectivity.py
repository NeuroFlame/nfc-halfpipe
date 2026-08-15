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
from typing import List, Optional


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

# Block sizes matching the real atlases used in parameters.json.
# These drive the synthetic block-diagonal mock matrices so that the
# annotated heatmap network bands appear even without real BIDS data.
#
# Schaefer 200 — 7 broad networks, LH then RH
#   LH: Vis×12, SMot×16, DorsAttn×11, SalVentAttn×11, Limbic×6, FP×18, Default×26
#   RH: Vis×12, SMot×18, DorsAttn×11, SalVentAttn×15, Limbic×8,  FP×19, Default×17
_SCHAEFER200_BLOCKS: List[int] = [12, 16, 11, 11, 6, 18, 26,   # LH
                                   12, 18, 11, 15, 8, 19, 17]   # RH

# NeuroMark fMRI 1.0 — 7 functional domains (Du et al. 2020)
#   SubCortical×5, Auditory×3, SensoriMotor×8, Visual×10,
#   CogCtrl×13, DMN×9, Cerebellar×5
_NEUROMARK53_BLOCKS: List[int] = [5, 3, 8, 10, 13, 9, 5]


def _synth_block_matrix(blocks: List[int],
                        high_r: float = 0.65,
                        low_r: float = 0.10,
                        noise_std: float = 0.04,
                        seed: int = 42) -> List[List[float]]:
    """
    Build a symmetric block-diagonal correlation matrix and return it as a
    Fisher-z (arctanh) nested list suitable for federation.

    Within each block:  mean r ≈ ``high_r``  (with small Gaussian jitter)
    Across blocks:      mean r ≈ ``low_r``   (uniform baseline)
    Diagonal:           always 1.0 before arctanh clip
    """
    try:
        import numpy as np
    except ImportError:
        raise

    rng = np.random.default_rng(seed)
    n = sum(blocks)
    mat = np.full((n, n), low_r, dtype=np.float64)

    idx = 0
    for b in blocks:
        block = np.full((b, b), high_r)
        noise = rng.normal(0, noise_std, (b, b))
        noise = (noise + noise.T) / 2          # keep symmetric
        block = np.clip(block + noise, 0.25, 0.90)
        mat[idx:idx + b, idx:idx + b] = block
        idx += b

    np.fill_diagonal(mat, 1.0)
    mat = (mat + mat.T) / 2                    # enforce exact symmetry
    np.fill_diagonal(mat, 1.0)

    z = np.arctanh(np.clip(mat, -0.9999, 0.9999))
    return z.tolist()


def _mock_connectivity(site_data: dict, params: dict) -> dict:
    """
    Return mock connectivity data for development / testing.

    Priority:
      1. ``site_data["mock_derivatives"]["connectivity"]`` — pre-stored override.
      2. Numpy available → synthesise realistic 200×200 Schaefer and 53×53
         NeuroMark block-diagonal matrices so the network annotation bands in
         the HTML report are exercised without real HALFpipe output.
      3. Numpy unavailable → tiny 5×5 fallback (no network labels).
    """
    mock = site_data.get("mock_derivatives", {})
    stored = mock.get("connectivity")
    if stored:
        logging.info(
            f"Mock connectivity: using pre-stored data for keys: {list(stored.keys())}"
        )
        return stored

    n_subjects = mock.get("n_subjects", 1)

    try:
        results: dict = {}

        # --- Schaefer 200-parcel ---
        z200 = _synth_block_matrix(
            _SCHAEFER200_BLOCKS, high_r=0.62, low_r=0.09, noise_std=0.04, seed=200
        )
        key200 = "connectivity_atlas-Schaefer200"
        results[key200] = {
            "mean_fisher_z_matrix": z200,
            "n_subjects": n_subjects,
            "n_parcels": 200,
        }
        logging.info(
            f"Mock connectivity: synthesised 200×200 Schaefer200 matrix for '{key200}' "
            f"({n_subjects} subjects)"
        )

        # --- NeuroMark fMRI 1.0  (53 components) ---
        z53 = _synth_block_matrix(
            _NEUROMARK53_BLOCKS, high_r=0.65, low_r=0.08, noise_std=0.05, seed=53
        )
        key53 = "neuromark_atlas-NeuroMark1"
        results[key53] = {
            "mean_fisher_z_matrix": z53,
            "n_subjects": n_subjects,
            "n_parcels": 53,
        }
        logging.info(
            f"Mock connectivity: synthesised 53×53 NeuroMark matrix for '{key53}' "
            f"({n_subjects} subjects)"
        )

        return results

    except ImportError:
        # numpy not installed in the host test environment — fall back to a
        # tiny pure-Python 5×5 matrix so federation still runs end-to-end.
        n = 5
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
            f"Mock connectivity: synthesised {n}×{n} fallback matrix for '{key}' "
            f"({n_subjects} subjects, numpy unavailable)"
        )
        return {
            key: {
                "mean_fisher_z_matrix": z,
                "n_subjects": n_subjects,
                "n_parcels": n,
            }
        }
