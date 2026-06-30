import logging
from typing import Optional


def extract_qc_metadata(
    site_data: dict,
    n_subjects: int,
    qc_summary: dict,
    params: dict,
) -> dict:
    """
    Package QC metadata for transmission to the central server.

    When run_halfpipe=false, augments the qc_summary from site_data mock values.
    """
    run_halfpipe = params.get("run_halfpipe", True)

    if not run_halfpipe:
        mock = site_data.get("mock_derivatives", {})
        qc_from_mock = mock.get("qc_metadata", {})
        n_subjects = mock.get("n_subjects", n_subjects)
        qc_summary = {**qc_from_mock, **qc_summary}

    return {
        "n_subjects": n_subjects,
        "qc_summary": qc_summary,
    }
