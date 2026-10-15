"""
Export per-subject connectivity features for downstream Fed-LAMP analysis.

Writes two CSV files locally at each site (nothing is federated):

  data.csv
      One row per subject. Columns are the upper triangle of each subject's
      correlation matrix, one column per ordered parcel pair (i < j, 1-indexed).
      Column format: {parcel_i_label}_x_{parcel_j_label}  (FNC domain names)
      Row-aligned with labels.csv.

  labels.csv
      One row per subject. Contains subject_id, all columns from the BIDS
      participants.tsv, and HALFpipe per-subject QC metrics (mean_fd,
      mean_fd_perc, mean_gm_tsnr). Same schema as nfc-combatdc's Covariate.csv.

Set nfc-fedlamp's parameters.json:
    "data_file":      "data.csv"
    "covariate_file": "labels.csv"

When multiple atlases are present all their upper-triangle columns are
concatenated in the same row (atlas order is deterministic: sorted by key).
"""

import csv
import logging
import os
import re
from pathlib import Path
from typing import Optional

from executor.atlas_labels import column_label as _col_label
from executor.extract_roi_values import _build_covariate_rows  # reuse covariate logic


def write_fedlamp_connectivity_csv(
    derivatives_path: Optional[str],
    site_data: dict,
    params: dict,
    output_dir: str,
    bids_directory: Optional[str] = None,
) -> dict:
    """
    Write FedLAMP_connectivity_Data.csv and FedLAMP_Covariate.csv.

    Parameters
    ----------
    derivatives_path:
        Path to the HALFpipe derivatives directory. None → mock mode.
    site_data:
        Contents of the site's data.json.
    params:
        Computation parameters from parameters.json.
    output_dir:
        Directory to write the two CSV files into.
    bids_directory:
        BIDS root used to locate participants.tsv for covariate data.

    Returns
    -------
    dict with keys: data_path, covariate_path, n_subjects, n_columns
    """
    cfg = params.get("fedlamp_config", {})
    data_filename = cfg.get("connectivity_data_file", "data.csv")
    covariate_filename = cfg.get("covariate_file", "labels.csv")

    if derivatives_path is None:
        return _write_mock_fedlamp_csvs(
            site_data, params, output_dir, data_filename, covariate_filename,
            bids_directory=bids_directory,
        )

    try:
        import numpy as np
    except ImportError:
        raise RuntimeError("numpy is required for Fed-LAMP connectivity export.")

    root = Path(derivatives_path)
    tsv_files = sorted(root.rglob("*_desc-correlation_matrix.tsv"))

    if not tsv_files:
        logging.warning(
            f"No correlation_matrix.tsv files found under {derivatives_path}. "
            "Fed-LAMP export skipped — include 'atlas_based_connectivity' in halfpipe_spec."
        )
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    # subject_id → {atlas_key → list of matrices (one per run)}
    # We average multiple runs per subject per atlas before flattening.
    subject_atlas_matrices: dict = {}

    for tsv_path in tsv_files:
        m_sub = re.search(r"/sub-([^/]+)/", str(tsv_path))
        m_key = re.search(
            r"_feature-([^_]+)_atlas-([^_]+)_desc-correlation_matrix\.tsv$",
            tsv_path.name,
        )
        if not m_sub or not m_key:
            logging.debug(f"Skipping unrecognised path: {tsv_path}")
            continue

        subject_id = m_sub.group(1)
        atlas_key = f"{m_key.group(1)}_atlas-{m_key.group(2)}"

        try:
            matrix = np.loadtxt(str(tsv_path), delimiter="\t")
        except Exception as exc:
            logging.warning(f"Could not load {tsv_path}: {exc}")
            continue

        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            logging.warning(f"Unexpected shape {matrix.shape} in {tsv_path} — skipping")
            continue

        subject_atlas_matrices \
            .setdefault(subject_id, {}) \
            .setdefault(atlas_key, []) \
            .append(matrix)

    if not subject_atlas_matrices:
        logging.warning("No valid correlation matrices found — Fed-LAMP export skipped")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    # Stable ordering so Data.csv and Covariate.csv rows always align.
    # Restrict to subjects that appear in participants.tsv when it exists — subjects
    # that have derivatives but no demographic record (e.g. partial/failed runs from
    # a different pipeline pass) should not produce empty rows in the output.
    all_subjects = sorted(subject_atlas_matrices.keys())
    valid_participants = _participants_tsv_ids(bids_directory)
    if valid_participants:
        subject_order = [s for s in all_subjects if s in valid_participants]
        excluded = set(all_subjects) - set(subject_order)
        if excluded:
            logging.info(
                "FedLAMP export: excluded %d subject(s) not in participants.tsv: %s",
                len(excluded), sorted(excluded),
            )
    else:
        subject_order = all_subjects
    atlas_keys = sorted({k for mats in subject_atlas_matrices.values() for k in mats})

    # Determine n_parcels per atlas (from first valid matrix)
    atlas_n_parcels: dict = {}
    for key in atlas_keys:
        for sub_mats in subject_atlas_matrices.values():
            mats = sub_mats.get(key)
            if mats:
                atlas_n_parcels[key] = mats[0].shape[0]
                break

    # Build column names: upper triangle of each atlas in sorted key order
    columns: list = []
    for key in atlas_keys:
        n = atlas_n_parcels.get(key, 0)
        for i in range(1, n + 1):
            for j in range(i + 1, n + 1):
                columns.append(_col_label(key, i, j))

    os.makedirs(output_dir, exist_ok=True)
    data_path = os.path.join(output_dir, data_filename)

    with open(data_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", restval="")
        writer.writeheader()
        for subject_id in subject_order:
            row: dict = {}
            sub_mats = subject_atlas_matrices[subject_id]
            for key in atlas_keys:
                mats = sub_mats.get(key)
                if not mats:
                    continue
                n = atlas_n_parcels[key]
                # Average runs then extract upper triangle
                mean_matrix = np.mean(np.stack(mats, axis=0), axis=0)
                for i in range(n):
                    for j in range(i + 1, n):
                        row[_col_label(key, i + 1, j + 1)] = round(float(mean_matrix[i, j]), 6)
            writer.writerow(row)

    logging.info(
        f"FedLAMP Data.csv written: {len(subject_order)} subjects "
        f"× {len(columns)} columns → {data_path}"
    )

    covariate_rows, covariate_columns = _build_covariate_rows(
        subject_order=subject_order,
        bids_directory=bids_directory,
        derivatives_path=derivatives_path,
    )
    covariate_path = os.path.join(output_dir, covariate_filename)
    with open(covariate_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=covariate_columns, extrasaction="ignore", restval="")
        writer.writeheader()
        for covariate_row in covariate_rows:
            writer.writerow(covariate_row)

    logging.info(
        f"FedLAMP Covariate.csv written: {len(subject_order)} subjects "
        f"× {len(covariate_columns)} columns → {covariate_path}"
    )

    return {
        "data_path": data_path,
        "covariate_path": covariate_path,
        "n_subjects": len(subject_order),
        "n_columns": len(columns),
    }


def _write_mock_fedlamp_csvs(
    site_data: dict,
    params: dict,
    output_dir: str,
    data_filename: str,
    covariate_filename: str,
    bids_directory: Optional[str] = None,
) -> dict:
    """
    Write mock Fed-LAMP CSVs using synthetic per-subject connectivity data.

    Uses the mock connectivity means from site_data (or the block-diagonal
    synthesiser) and adds per-subject Gaussian noise so rows are not identical.
    """
    try:
        import numpy as np
    except ImportError:
        logging.warning("numpy unavailable — mock Fed-LAMP export skipped")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    from executor.extract_connectivity import _mock_connectivity

    mock = site_data.get("mock_derivatives", {})
    n_subjects = mock.get("n_subjects", 1)
    connectivity = _mock_connectivity(site_data, params)

    if not connectivity:
        logging.warning("No mock connectivity data available — Fed-LAMP export skipped")
        return {"data_path": None, "covariate_path": None, "n_subjects": 0, "n_columns": 0}

    atlas_keys = sorted(connectivity.keys())
    atlas_n_parcels = {k: connectivity[k]["n_parcels"] for k in atlas_keys}

    columns: list = []
    for key in atlas_keys:
        n = atlas_n_parcels[key]
        for i in range(1, n + 1):
            for j in range(i + 1, n + 1):
                columns.append(_col_label(key, i, j))

    # Subject IDs: read from participants.tsv if available, otherwise synthesise
    # with zero-padding to match BIDS convention (sub-01, sub-02, ...).
    subject_ids = _subject_ids_from_bids(bids_directory, n_subjects)
    # Bare IDs (strip "sub-" prefix) for _build_covariate_rows
    bare_ids = [s[4:] if s.startswith("sub-") else s for s in subject_ids]

    rng = np.random.default_rng(42)
    os.makedirs(output_dir, exist_ok=True)
    data_path = os.path.join(output_dir, data_filename)

    with open(data_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for sub_idx in range(n_subjects):
            row: dict = {}
            col_idx = 0
            for key in atlas_keys:
                n = atlas_n_parcels[key]
                mean_z = np.array(connectivity[key]["mean_fisher_z_matrix"])
                # Per-subject jitter in Fisher-z space then back-transform
                jitter = rng.normal(0, 0.05, mean_z.shape)
                jitter = (jitter + jitter.T) / 2
                subj_r = np.tanh(mean_z + jitter)
                np.fill_diagonal(subj_r, 1.0)
                for i in range(n):
                    for j in range(i + 1, n):
                        row[columns[col_idx]] = round(float(subj_r[i, j]), 6)
                        col_idx += 1
            writer.writerow(row)

    covariate_rows, covariate_columns = _build_covariate_rows(
        subject_order=bare_ids,
        bids_directory=bids_directory,
        derivatives_path=None,
    )
    covariate_path = os.path.join(output_dir, covariate_filename)
    with open(covariate_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=covariate_columns, extrasaction="ignore", restval="")
        writer.writeheader()
        for row in covariate_rows:
            writer.writerow(row)

    logging.info(
        f"Mock FedLAMP Data.csv written: {n_subjects} subjects "
        f"× {len(columns)} columns → {data_path}"
    )
    return {
        "data_path": data_path,
        "covariate_path": covariate_path,
        "n_subjects": n_subjects,
        "n_columns": len(columns),
    }


def _participants_tsv_ids(bids_directory: Optional[str]) -> set:
    """Return the set of bare subject IDs (without 'sub-' prefix) from participants.tsv.

    Returns an empty set when the file is absent or unreadable, which the caller
    interprets as "no filter" (include all subjects with derivatives).
    """
    if not bids_directory:
        return set()
    ptsp = os.path.join(bids_directory, "participants.tsv")
    if not os.path.exists(ptsp):
        return set()
    try:
        ids: set = set()
        with open(ptsp, newline="") as f:
            for record in csv.DictReader(f, delimiter="\t"):
                pid = record.get("participant_id", "").strip()
                if pid:
                    ids.add(pid[4:] if pid.startswith("sub-") else pid)
        return ids
    except Exception as exc:
        logging.warning("Could not read participants.tsv for subject filter: %s", exc)
        return set()


def _subject_ids_from_bids(bids_directory: Optional[str], n_subjects: int) -> list:
    """
    Return a list of BIDS-format subject IDs ('sub-01', 'sub-02', ...).

    Reads participant_id from participants.tsv when available so mock rows
    align with real subjects. Falls back to zero-padded sequential IDs.
    """
    if bids_directory:
        ptsp = os.path.join(bids_directory, "participants.tsv")
        if os.path.exists(ptsp):
            try:
                ids = []
                with open(ptsp, newline="") as f:
                    for record in csv.DictReader(f, delimiter="\t"):
                        pid = record.get("participant_id", "")
                        if pid:
                            ids.append(pid if pid.startswith("sub-") else f"sub-{pid}")
                if ids:
                    return ids
            except Exception:
                pass
    width = max(2, len(str(n_subjects)))
    return [f"sub-{i:0{width}d}" for i in range(1, n_subjects + 1)]
