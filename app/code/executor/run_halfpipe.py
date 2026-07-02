import json
import logging
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

_HALFPIPE_SCHEMA_VERSION = "3.0"
_HALFPIPE_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M"


def _halfpipe_env() -> dict:
    # NVFlare's SimulatorRunner builds PYTHONPATH from the full sys.path, which
    # includes nfc-env site-packages (numpy 2.5). Halfpipe's conda Python then
    # finds numpy 2.5 via PYTHONPATH before its own conda numpy, causing numba
    # to fail ("Numba needs NumPy 2.3 or less"). Strip nfc-env paths so
    # halfpipe sees only its own conda environment.
    env = os.environ.copy()
    raw = env.get("PYTHONPATH", "")
    if raw:
        clean = ":".join(
            p for p in raw.split(":") if p and "nfc-env" not in p and "/opt/conda/lib/python" not in p
        )
        if clean:
            env["PYTHONPATH"] = clean
        else:
            env.pop("PYTHONPATH", None)
    return env


def run_halfpipe_and_get_qc(site_data: dict, params: dict, workdir: str, bids_directory: str) -> dict:
    """
    Run HALFpipe subject-level analysis and return QC summary.

    bids_directory is the path to the site's BIDS root. In production this
    comes from the directory the user points to in the NeuroFLAME UI (DATA_DIR);
    in simulation it is test_data/siteN/.

    When params["run_halfpipe"] is False, skips execution and returns mock
    values from site_data["mock_derivatives"].
    """
    run_halfpipe = params.get("run_halfpipe", True)

    # Per-site early exit: if a derivatives_directory is set and exists, skip
    # halfpipe regardless of run_halfpipe. This lets a site contribute real
    # results from a prior run without re-running the full pipeline.
    derivatives_directory = site_data.get("derivatives_directory")
    if derivatives_directory and os.path.isdir(str(derivatives_directory)):
        logging.info(f"Using existing derivatives at {derivatives_directory}")
        qc_summary = _extract_qc_from_derivatives(str(derivatives_directory))
        n_subjects = qc_summary.pop("n_subjects", 0)
        return {
            "status": "skipped",
            "n_subjects": n_subjects,
            "qc_summary": qc_summary,
            "derivatives_path": str(derivatives_directory),
        }

    if not run_halfpipe:
        logging.info("Skipping HALFpipe execution (run_halfpipe=false); using mock derivatives")
        mock = site_data.get("mock_derivatives", {})
        return {
            "status": "skipped",
            "n_subjects": mock.get("n_subjects", 0),
            "qc_summary": mock.get("qc_metadata", {}),
            "derivatives_path": None,
        }

    if platform.machine() == "aarch64":
        logging.warning(
            "Running on linux/aarch64 without native FSL support. "
            "fMRIPrep's FSL-dependent steps (BET, FAST) will fail. "
            "Use the linux/amd64 image under Rosetta on Apple Silicon until "
            "a native arm64 image with ANTs-only brain extraction is available. "
            "See README — Platform Support."
        )

    halfpipe_spec = params.get("halfpipe_spec")
    if halfpipe_spec is None:
        raise ValueError("params must contain 'halfpipe_spec' when run_halfpipe=true")

    # Substitute {bids_directory} placeholder in file path patterns so the
    # shared server-side spec can reference each site's local BIDS root.
    spec = json.loads(json.dumps(halfpipe_spec))  # deep copy
    for file_entry in spec.get("files", []):
        if "path" in file_entry:
            file_entry["path"] = file_entry["path"].replace("{bids_directory}", bids_directory)

    # Promote to HALFpipe schema 3.0 (1.3.x).  Our internal halfpipe_spec uses
    # a "version" key that is not part of the halfpipe schema; remove it and
    # inject the required schema_version and timestamp.
    spec.pop("version", None)
    spec.setdefault("schema_version", _HALFPIPE_SCHEMA_VERSION)
    spec.setdefault("timestamp", datetime.now().strftime(_HALFPIPE_TIMESTAMP_FORMAT))
    spec.setdefault("models", [])
    # An empty global_settings dict triggers GlobalSettingsSchema.@pre_load,
    # which fills in all required defaults (slice_timing, run_fmriprep, etc.).
    spec.setdefault("global_settings", {})

    os.makedirs(workdir, exist_ok=True)
    spec_path = os.path.join(workdir, "spec.json")
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    logging.info(f"Wrote HALFpipe spec to {spec_path}")

    n_procs = params.get("n_procs", 1)
    workflow_only = params.get("workflow_only", False)

    # FreeSurfer license: check params, then env var, then well-known mount point.
    fs_license = (
        params.get("fs_license_path")
        or os.environ.get("FS_LICENSE")
        or ("/workspace/license.txt" if os.path.isfile("/workspace/license.txt") else None)
    )

    cmd = [
        "halfpipe",
        "--workdir", workdir,
        "--spec-path", spec_path,
        "--skip-spec-ui",
        "--nipype-run-plugin", "Simple",
        "--nipype-n-procs", str(n_procs),
        "--verbose",
    ]
    if fs_license:
        cmd += ["--fs-license-file", fs_license]
    if workflow_only:
        cmd += ["--only-workflow"]
    for sub in params.get("subject_include", []):
        cmd += ["--subject-include", sub]

    logging.info(f"Running HALFpipe: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=_halfpipe_env())

    if result.returncode != 0:
        logging.error(f"HALFpipe stdout:\n{result.stdout}")
        logging.error(f"HALFpipe stderr:\n{result.stderr}")
        raise RuntimeError(f"HALFpipe failed with return code {result.returncode}")

    if workflow_only:
        logging.info("HALFpipe workflow construction completed (--only-workflow; no derivatives produced)")
        return {"status": "workflow_only", "n_subjects": 0, "qc_summary": {}, "derivatives_path": None}

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
    Parse HALFpipe 1.3.x BIDS JSON sidecar files to extract QC metrics.

    HALFpipe 1.3.x embeds QC stats (FDMean, FDPerc, MeanGMTSNR) directly in
    the feature JSON sidecars (*_feature-*_*.json) using PascalCase keys.
    We de-duplicate per subject (each subject's runs share the same FD values
    across features) and average across subjects.
    """
    if not os.path.isdir(derivatives_path):
        logging.warning(f"Derivatives directory not found: {derivatives_path}")
        return {"n_subjects": 0}

    subject_dirs = [
        d for d in Path(derivatives_path).iterdir()
        if d.is_dir() and d.name.startswith("sub-")
    ]

    fd_values = []
    fd_perc_values = []
    tsnr_values = []

    for subject_dir in subject_dirs:
        seen_runs = set()
        for sidecar in subject_dir.rglob("*_feature-*_*.json"):
            # Key on (task, run) so we only count each run's QC once per subject.
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
                fd_values.append(float(vals["FDMean"]))
                if "FDPerc" in vals:
                    fd_perc_values.append(float(vals["FDPerc"]))
                if "MeanGMTSNR" in vals:
                    tsnr_values.append(float(vals["MeanGMTSNR"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

    summary = {"n_subjects": len(subject_dirs)}
    if fd_values:
        summary["mean_fd"] = round(sum(fd_values) / len(fd_values), 4)
    if fd_perc_values:
        summary["mean_fd_perc"] = round(sum(fd_perc_values) / len(fd_perc_values), 4)
    if tsnr_values:
        summary["mean_gm_tsnr"] = round(sum(tsnr_values) / len(tsnr_values), 4)

    return summary
