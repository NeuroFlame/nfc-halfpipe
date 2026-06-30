import base64
import gzip
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional


def run_site_group_level(
    derivatives_path: Optional[str],
    site_data: dict,
    params: dict,
    output_dir: str,
) -> dict:
    """
    Run HALFpipe group-level analysis within a site and return compressed statistical maps.

    When derivatives_path is None (run_halfpipe=false), returns mock voxelwise stats
    from site_data["mock_derivatives"]["voxelwise_stats"].

    For real data, runs `halfpipe group-level` and returns base64-encoded gzip-compressed
    NIfTI bytes keyed by feature and contrast name.

    Returns:
        {
            "feature_contrast": <base64-encoded gzip-compressed NIfTI bytes>,
            ...
            "n_subjects": N,
        }
    """
    run_halfpipe = params.get("run_halfpipe", True)

    if not run_halfpipe or derivatives_path is None:
        mock = site_data.get("mock_derivatives", {})
        voxelwise = mock.get("voxelwise_stats", {})
        n_subjects = mock.get("n_subjects", 0)
        logging.info("Using mock voxelwise stats")
        return {"site_stats": voxelwise, "n_subjects": n_subjects}

    group_level_output = os.path.join(output_dir, "site_group_level")
    os.makedirs(group_level_output, exist_ok=True)

    cmd = [
        "halfpipe",
        "group-level",
        "--input-directory", derivatives_path,
        "--output-directory", group_level_output,
        "--verbose",
    ]

    voxelwise_config = params.get("voxelwise_maps", {})
    if "spreadsheet" in voxelwise_config:
        cmd += ["--spreadsheet", voxelwise_config["spreadsheet"]]
    if "covariates" in voxelwise_config:
        for covariate in voxelwise_config["covariates"]:
            cmd += ["--covariate", covariate]

    logging.info(f"Running HALFpipe group-level: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logging.error(f"HALFpipe group-level stderr:\n{result.stderr}")
        raise RuntimeError(f"HALFpipe group-level failed with return code {result.returncode}")

    logging.info("HALFpipe group-level completed")

    site_stats = {}
    for nifti_path in Path(group_level_output).rglob("*.nii.gz"):
        key = _make_stat_key(nifti_path, group_level_output)
        with open(nifti_path, "rb") as f:
            nifti_bytes = f.read()
        site_stats[key] = base64.b64encode(nifti_bytes).decode("ascii")
        logging.info(f"Packed {nifti_path.name} ({len(nifti_bytes)} bytes)")

    n_subjects = _count_subjects_in_derivatives(derivatives_path)

    return {"site_stats": site_stats, "n_subjects": n_subjects}


def _make_stat_key(nifti_path: Path, base_dir: str) -> str:
    relative = nifti_path.relative_to(base_dir)
    return str(relative).replace(os.sep, "__").replace(".nii.gz", "")


def _count_subjects_in_derivatives(derivatives_path: str) -> int:
    try:
        subject_dirs = [
            d for d in Path(derivatives_path).iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        ]
        return len(subject_dirs)
    except Exception:
        return 0
