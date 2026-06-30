import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path


def run_halfpipe_and_get_qc(site_data: dict, params: dict, workdir: str) -> dict:
    """
    Run HALFpipe subject-level analysis and return QC summary.

    When params["run_halfpipe"] is False (or derivatives already exist),
    skips execution and returns mock/cached values from site_data.
    """
    run_halfpipe = params.get("run_halfpipe", True)
    mock = site_data.get("mock_derivatives", {})

    if not run_halfpipe:
        logging.info("Skipping HALFpipe execution (run_halfpipe=false); using mock derivatives")
        return {
            "status": "skipped",
            "n_subjects": mock.get("n_subjects", 0),
            "qc_summary": mock.get("qc_metadata", {}),
            "derivatives_path": site_data.get("derivatives_directory"),
        }

    halfpipe_spec = params.get("halfpipe_spec")
    if halfpipe_spec is None:
        raise ValueError("params must contain 'halfpipe_spec' when run_halfpipe=true")

    bids_directory = site_data.get("bids_directory")
    if bids_directory is None:
        raise ValueError("site data must contain 'bids_directory' when run_halfpipe=true")

    # Substitute {bids_directory} placeholder in file path patterns so the
    # shared server-side spec can reference each site's local BIDS root.
    spec = json.loads(json.dumps(halfpipe_spec))  # deep copy
    for file_entry in spec.get("files", []):
        if "path" in file_entry:
            file_entry["path"] = file_entry["path"].replace("{bids_directory}", bids_directory)

    os.makedirs(workdir, exist_ok=True)
    spec_path = os.path.join(workdir, "spec.json")
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    logging.info(f"Wrote HALFpipe spec to {spec_path}")

    cmd = [
        "halfpipe",
        "--workdir", workdir,
        "--spec-path", spec_path,
        "--skip-spec-ui",
        "--nipype-run-plugin", "Simple",
        "--verbose",
    ]

    n_procs = params.get("n_procs", 1)
    cmd += ["--nipype-n-procs", str(n_procs)]

    logging.info(f"Running HALFpipe: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logging.error(f"HALFpipe stderr:\n{result.stderr}")
        raise RuntimeError(f"HALFpipe failed with return code {result.returncode}")

    logging.info("HALFpipe completed successfully")

    derivatives_path = os.path.join(workdir, "derivatives", "halfpipe")
    qc_summary = _extract_qc_from_derivatives(derivatives_path)

    return {
        "status": "completed",
        "n_subjects": qc_summary.pop("n_subjects", 0),
        "qc_summary": qc_summary,
        "derivatives_path": derivatives_path if os.path.isdir(derivatives_path) else None,
    }


def _extract_qc_from_derivatives(derivatives_path: str) -> dict:
    """
    Parse HALFpipe-generated vals.json files to extract QC metrics.

    Returns a dict with n_subjects and per-subject motion stats averaged across subjects.
    """
    if not os.path.isdir(derivatives_path):
        logging.warning(f"Derivatives directory not found: {derivatives_path}")
        return {"n_subjects": 0}

    fd_values = []
    fd_perc_values = []
    subject_dirs = [
        d for d in Path(derivatives_path).iterdir()
        if d.is_dir() and d.name.startswith("sub-")
    ]

    for subject_dir in subject_dirs:
        for vals_file in subject_dir.rglob("*vals.json"):
            try:
                with open(vals_file) as f:
                    vals = json.load(f)
                if "fd_mean" in vals:
                    fd_values.append(float(vals["fd_mean"]))
                if "fd_perc" in vals:
                    fd_perc_values.append(float(vals["fd_perc"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

    summary = {"n_subjects": len(subject_dirs)}
    if fd_values:
        summary["mean_fd"] = round(sum(fd_values) / len(fd_values), 4)
    if fd_perc_values:
        summary["mean_fd_perc"] = round(sum(fd_perc_values) / len(fd_perc_values), 4)

    return summary
