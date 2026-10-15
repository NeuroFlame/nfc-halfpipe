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
from executor.write_fedlamp_export import write_fedlamp_connectivity_csv
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
        output_dir=output_dir,
    )

    # Copy HALFpipe's own QC report to the site output directory so the
    # site coordinator can open it alongside the federated index.html.
    halfpipe_reports_src = os.path.join(halfpipe_workdir, "reports")
    if not os.path.isdir(halfpipe_reports_src):
        # Fallback: look for reports alongside the derivatives directory.
        # HALFpipe writes {workdir}/reports/ and {workdir}/derivatives/halfpipe/.
        # When derivatives_directory points directly to the flat folder
        # (e.g. /workspace/data/halfpipe_derivatives), reports may live at
        # {data_dir}/reports or one/two levels above derivatives_path.
        deriv_path = halfpipe_result.get("derivatives_path") or ""
        for candidate_parent in [
            os.path.dirname(deriv_path),
            os.path.dirname(os.path.dirname(deriv_path)),
            os.path.dirname(os.path.dirname(os.path.dirname(deriv_path))),
        ]:
            candidate = os.path.join(candidate_parent, "reports")
            if os.path.isdir(candidate):
                halfpipe_reports_src = candidate
                break
    if os.path.isdir(halfpipe_reports_src):
        halfpipe_reports_dst = os.path.join(output_dir, "halfpipe_reports")
        shutil.copytree(halfpipe_reports_src, halfpipe_reports_dst, dirs_exist_ok=True)
        _repair_halfpipe_report_js(halfpipe_reports_dst)
        logging.info("HALFpipe QC report copied to %s/index.html", halfpipe_reports_dst)
    else:
        logging.debug("No HALFpipe reports directory found (mock or skipped run)")

    # When halfpipe ran (run_halfpipe=true) but produced no halfpipe/ derivatives
    # (all subjects failed on stub data, or fMRIPrep-only run), n_subjects=0 and
    # derivatives_path=None.  extract_roi_values and extract_connectivity_matrices
    # already fall back to mock data via derivatives_path=None; mirror that here
    # so QC also reports consistent subject counts.
    if (halfpipe_result.get("n_subjects", 0) == 0
            and halfpipe_result.get("derivatives_path") is None
            and halfpipe_result.get("status") != "skipped"):
        mock = site_data.get("mock_derivatives", {})
        if mock.get("n_subjects", 0) > 0:
            halfpipe_result = {
                **halfpipe_result,
                "n_subjects": mock["n_subjects"],
                "qc_summary": mock.get("qc_metadata", halfpipe_result.get("qc_summary", {})),
            }
            logging.info(
                "HALFpipe produced no halfpipe/ derivatives; "
                "using mock QC data (%d subjects)", mock["n_subjects"],
            )

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

    Returns None when run_federation is false (default) or neither aggregation type
    is requested, which the server treats as a no-op for this site.
    """
    if parameters.get("halfpipe_only"):
        return None
    if not parameters.get("run_federation", False):
        return None
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

def send_atlas_connectivity(_incoming, parameters: dict, state: dict, output_dir: str, data_dir: str):
    """Extract atlas-based connectivity matrices if atlas_connectivity is enabled.

    Also writes per-subject connectivity CSVs for Fed-LAMP when fedlamp_export
    is in aggregation_types. The two modes are independent — either or both can
    be requested.

    Returns None when run_federation is false (default), or neither atlas_connectivity
    nor fedlamp_export is requested.
    """
    if parameters.get("halfpipe_only"):
        return None
    aggregation_types = _as_list(parameters.get("aggregation_types", []))
    want_federation = parameters.get("run_federation", False) and "atlas_connectivity" in aggregation_types
    want_fedlamp = "fedlamp_export" in aggregation_types

    if not want_federation and not want_fedlamp:
        return None

    site_data = _read_site_data(data_dir)
    derivatives_path = state.get("derivatives_path")

    if want_fedlamp:
        write_fedlamp_connectivity_csv(
            derivatives_path=derivatives_path,
            site_data=site_data,
            params=parameters,
            output_dir=output_dir,
            bids_directory=site_data.get("bids_directory") or data_dir,
        )

    if not want_federation:
        return None

    connectivity = extract_connectivity_matrices(
        derivatives_path=derivatives_path,
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

    Returns None when run_regression is false (default) or voxelwise_maps is not requested.
    """
    if parameters.get("halfpipe_only"):
        return None
    if not parameters.get("run_federation", False):
        return None
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


def _repair_halfpipe_report_js(reports_dir: str) -> None:
    """Populate stub report*.js files from reportvals.txt and SVG figures.

    HALFpipe writes placeholder ``report('[]\n');`` stubs into each .js data
    file and is supposed to fill them at the end of the run.  When that final
    collect step is skipped (e.g. an interrupted container), the stubs remain
    and the report renders blank.  This function regenerates them from the data
    that HALFpipe *did* write: reportvals.txt and per-subject SVG figures.
    """
    import glob
    import hashlib
    import re

    STUB = b"report('[]"  # first 10 bytes of every placeholder

    def _is_stub(path: str) -> bool:
        try:
            with open(path, "rb") as fh:
                return fh.read(10) == STUB
        except OSError:
            return False

    def _write_js(path: str, records: list) -> None:
        payload = json.dumps(records, indent=4, ensure_ascii=False)
        # HALFpipe escapes newlines inside the JS string literal
        payload_escaped = payload.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\\n")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("report('" + payload_escaped + "\\\n');\n")

    # ---- helpers for reportvals.txt (space-padded tabulate format) ----
    # These HALFpipe fields must stay as strings even when they look numeric
    _STR_KEYS = {"sub", "task", "run", "halfpipe_version"}

    def _parse_vals_txt(path: str) -> list:
        records = []
        with open(path) as fh:
            lines = fh.readlines()
        # First non-blank line is the header; skip separator lines (start with -)
        header: list = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("-"):
                continue
            tokens = stripped.split()
            if not header:
                header = tokens
                continue
            if len(tokens) < len(header):
                tokens += [""] * (len(header) - len(tokens))
            rec: dict = {}
            for key, raw in zip(header, tokens):
                raw = raw.strip()
                if key in _STR_KEYS:
                    rec[key] = raw
                elif raw.startswith("[") and raw.endswith("]"):
                    try:
                        rec[key] = json.loads(raw)
                    except Exception:
                        rec[key] = raw
                elif raw.lower() in ("true", "false"):
                    rec[key] = raw.lower() == "true"
                else:
                    try:
                        rec[key] = int(raw)
                    except ValueError:
                        try:
                            rec[key] = float(raw)
                        except ValueError:
                            rec[key] = raw
            if rec:
                records.append(rec)
        return records

    # ---- reportvals.js -----------------------------------------------
    vals_txt = os.path.join(reports_dir, "reportvals.txt")
    vals_js  = os.path.join(reports_dir, "reportvals.js")
    if _is_stub(vals_js) and os.path.exists(vals_txt):
        try:
            records = _parse_vals_txt(vals_txt)
            _write_js(vals_js, records)
            logging.info("Repaired %s (%d subjects)", vals_js, len(records))
        except Exception as exc:
            logging.warning("Could not repair reportvals.js: %s", exc)

    # ---- reportimgs.js -----------------------------------------------
    imgs_js = os.path.join(reports_dir, "reportimgs.js")
    if _is_stub(imgs_js):
        # Pattern: sub-<ID>[_task-<task>_run-<run>]_<desc>.svg
        pat = re.compile(
            r"sub-(?P<sub>[^_/]+)"
            r"(?:_task-(?P<task>[^_]+)_run-(?P<run>[^_]+))?"
            r"_(?P<desc>.+)\.svg$"
        )
        img_records = []
        for svg_path in sorted(glob.glob(os.path.join(reports_dir, "sub-*/figures/*.svg"))):
            fname = os.path.basename(svg_path)
            m = pat.match(fname)
            if not m:
                continue
            rel_path = os.path.relpath(svg_path, reports_dir)
            try:
                with open(svg_path, "rb") as fh:
                    file_hash = hashlib.md5(fh.read()).hexdigest()
            except OSError:
                file_hash = ""
            rec: dict = {
                "desc": m.group("desc"),
                "hash": file_hash,
                "path": rel_path.replace(os.sep, "/"),
                "sourcefiles": [],
                "sub": m.group("sub"),
            }
            if m.group("task"):
                rec["task"] = m.group("task")
            if m.group("run"):
                rec["run"] = m.group("run")
            img_records.append(rec)
        if img_records:
            try:
                _write_js(imgs_js, img_records)
                logging.info("Repaired %s (%d figures)", imgs_js, len(img_records))
            except Exception as exc:
                logging.warning("Could not repair reportimgs.js: %s", exc)

    # ---- reportpreproc.js --------------------------------------------
    preproc_js = os.path.join(reports_dir, "reportpreproc.js")
    if _is_stub(preproc_js) and os.path.exists(vals_txt):
        try:
            rows = _parse_vals_txt(vals_txt)
            preproc_records = []
            seen: set = set()
            for row in rows:
                sub  = str(row.get("sub", "")).strip()
                task = str(row.get("task", "rest")).strip()
                run  = str(row.get("run", "1")).strip()
                key  = (sub, task, run)
                if key in seen or not sub:
                    continue
                seen.add(key)
                preproc_records.append({"run": run, "status": "done", "sub": sub, "task": task})
            if preproc_records:
                _write_js(preproc_js, preproc_records)
                logging.info("Repaired %s (%d runs)", preproc_js, len(preproc_records))
        except Exception as exc:
            logging.warning("Could not repair reportpreproc.js: %s", exc)
