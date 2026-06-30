def extract_qc_metadata(
    n_subjects: int,
    qc_summary: dict,
) -> dict:
    return {
        "n_subjects": n_subjects,
        "qc_summary": qc_summary,
    }
