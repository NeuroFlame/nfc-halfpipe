"""Site-side computation steps for HALFpipe federated analysis."""

import json
import logging
import os
import shutil

from framework import with_state

from executor.run_halfpipe import run_halfpipe_and_get_qc
from executor.extract_qc_metadata import extract_qc_metadata
from executor.extract_roi_values import extract_roi_values, write_subject_roi_csv
from executor.extract_connectivity import extract_connectivity_matrices
from executor.run_site_group_level import run_site_group_level


# ------------------------------------------------------------------ #
# Input loader                                                         #
# ------------------------------------------------------------------ #

def load_site_data(data_dir: str) -> dict:
    """Load site configuration from data.json; return {} when absent."""
    data_path = os.path.join(data_dir, "data.json")
    if not os.path.exists(data_path):
        return {}
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ #
# Phase 1 — Run HALFpipe                                              #
# ------------------------------------------------------------------ #

def run_halfpipe(site_data: dict, parameters: dict, output_dir: str, data_dir: str):
    """Run HALFpipe locally and return QC payload; persist halfpipe_result in state.

    ``site_data`` is provided by the ``load_site_data`` input loader.
    The halfpipe_result dict is stored as local state so subsequent steps
    (SEND_ROI_VALUES, SEND_ATLAS_CONNECTIVITY, SEND_SITE_STATS) can read
    ``derivatives_path`` and ``n_subjects`` without re-running the pipeline.
    """
    site_name = os.path.basename(output_dir)
    halfpipe_workdir = (
        site_data.get("halfpipe_workdir")
        or os.path.join(output_dir, f"halfpipe_workdir_{site_name}")
    )
    bids_directory = site_data.get("bids_directory") or data_dir

    halfpipe_result = run_halfpipe_and_get_qc(
        site_data=site_data,
        params=parameters,
        workdir=halfpipe_workdir,
        bids_directory=bids_directory,
    )

    # Copy HALFpipe's own QC report to the site output directory so the
    # site coordinator can open it alongside the federated index.html.
    halfpipe_reports_src = os.path.join(halfpipe_workdir, "reports")
    if os.path.isdir(halfpipe_reports_src):
        halfpipe_reports_dst = os.path.join(output_dir, "halfpipe_reports")
        shutil.copytree(halfpipe_reports_src, halfpipe_reports_dst, dirs_exist_ok=True)
        logging.info("HALFpipe QC report copied to %s/index.html", halfpipe_reports_dst)
    else:
        logging.debug("No HALFpipe reports directory found (mock or skipped run)")

    qc_payload = extract_qc_metadata(
        n_subjects=halfpipe_result["n_subjects"],
        qc_summary=halfpipe_result["qc_summary"],
    )
    # Store the full halfpipe_result as local state for downstream steps.
    return with_state(qc_payload, halfpipe_result)


# ------------------------------------------------------------------ #
# Phase 2a — ROI values                                               #
# ------------------------------------------------------------------ #

def send_roi_values(_incoming, parameters: dict, state: dict, output_dir: str, data_dir: str):
    """Extract atlas-parcellated feature values if roi_values / subject_csv is enabled.

    Returns None when neither aggregation type is requested, which the server
    treats as a no-op for this site in the ROI aggregation step.
    """
    aggregation_types = _as_list(parameters.get("aggregation_types", []))
    if "roi_values" not in aggregation_types and "subject_csv" not in aggregation_types:
        return None

    site_data = _read_site_data(data_dir)
    derivatives_path = state.get("derivatives_path")
    payload = {"n_subjects": state.get("n_subjects", 0)}

    if "roi_values" in aggregation_types:
        payload["roi_values"] = extract_roi_values(
            derivatives_path=derivatives_path,
            site_data=site_data,
            params=parameters,
        )

    if "subject_csv" in aggregation_types:
        write_subject_roi_csv(
            derivatives_path=derivatives_path,
            site_data=site_data,
            params=parameters,
            output_dir=output_dir,
            bids_directory=site_data.get("bids_directory") or data_dir,
        )

    return payload


# ------------------------------------------------------------------ #
# Phase 2b — Atlas connectivity                                        #
# ------------------------------------------------------------------ #

def send_atlas_connectivity(_incoming, parameters: dict, state: dict, data_dir: str):
    """Extract atlas-based connectivity matrices if atlas_connectivity is enabled.

    Returns None when the aggregation type is not requested.
    """
    aggregation_types = _as_list(parameters.get("aggregation_types", []))
    if "atlas_connectivity" not in aggregation_types:
        return None

    site_data = _read_site_data(data_dir)
    connectivity = extract_connectivity_matrices(
        derivatives_path=state.get("derivatives_path"),
        site_data=site_data,
        params=parameters,
    )
    return {
        "n_subjects": state.get("n_subjects", 0),
        "connectivity": connectivity,
    }


# ------------------------------------------------------------------ #
# Phase 2c — Site group-level / voxelwise                             #
# ------------------------------------------------------------------ #

def send_site_stats(_incoming, parameters: dict, state: dict, output_dir: str, data_dir: str):
    """Run within-site group-level analysis and return stat maps if enabled.

    Returns None when voxelwise_maps is not requested.
    """
    aggregation_types = _as_list(parameters.get("aggregation_types", []))
    if "voxelwise_maps" not in aggregation_types:
        return None

    site_data = _read_site_data(data_dir)
    return run_site_group_level(
        derivatives_path=state.get("derivatives_path"),
        site_data=site_data,
        params=parameters,
        output_dir=output_dir,
    )


# ------------------------------------------------------------------ #
# Final step — write output                                            #
# ------------------------------------------------------------------ #

def build_outputs(global_results: dict, output_dir: str):
    """Write the federated results and HTML report to the site output directory.

    ``global_results`` is the accumulated dict built by the remote steps:
    {qc_metadata, roi_values, connectivity, voxelwise_maps} (whichever
    aggregation types were enabled in parameters.json).
    """
    from executor.generate_report import generate_html_report

    site_name = os.path.basename(output_dir)
    html = generate_html_report(site_name, global_results)
    return {
        "global_results.json": global_results,
        "index.html": html,
    }


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _as_list(value) -> list:
    """Normalize a string-or-list parameter value to a plain list."""
    return [value] if isinstance(value, str) else list(value or [])


def _read_site_data(data_dir: str) -> dict:
    """Reload site_data from data.json; return {} when absent."""
    data_path = os.path.join(data_dir, "data.json")
    if not os.path.exists(data_path):
        return {}
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)
