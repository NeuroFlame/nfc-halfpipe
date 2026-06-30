import json
import logging
import os

from nvflare.apis.executor import Executor
from nvflare.apis.fl_constant import FLContextKey
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import Shareable
from nvflare.apis.signal import Signal

from _utils.utils import (
    get_data_directory_path,
    get_output_directory_path,
    get_parameters_file_path,
)
from .run_halfpipe import run_halfpipe_and_get_qc
from .extract_qc_metadata import extract_qc_metadata
from .extract_roi_values import extract_roi_values
from .run_site_group_level import run_site_group_level
from .generate_report import generate_html_report

TASK_RUN_HALFPIPE = "RUN_HALFPIPE"
TASK_SEND_ROI_VALUES = "SEND_ROI_VALUES"
TASK_SEND_SITE_STATS = "SEND_SITE_STATS"
TASK_ACCEPT_GLOBAL_RESULTS = "ACCEPT_GLOBAL_RESULTS"


class HALFpipeExecutor(Executor):
    """
    NVFlare executor for federated HALFpipe analysis.

    Handles four tasks:
      RUN_HALFPIPE          — run HALFpipe subject-level on local data
      SEND_ROI_VALUES       — extract and send parcellated feature values
      SEND_SITE_STATS       — run within-site group-level and send stat maps
      ACCEPT_GLOBAL_RESULTS — save the federated results sent from the server
    """

    def __init__(self):
        super().__init__()
        self._params = None
        self._site_data = None
        self._halfpipe_result = None

    def execute(
        self,
        task_name: str,
        shareable: Shareable,
        fl_ctx: FLContext,
        abort_signal: Signal,
    ) -> Shareable:
        logging.info(f"Task: {task_name}")

        if self._params is None:
            self._params = self._load_params(fl_ctx)

        if self._site_data is None:
            self._site_data = self._load_site_data(fl_ctx)

        if task_name == TASK_RUN_HALFPIPE:
            return self._handle_run_halfpipe(fl_ctx)

        if task_name == TASK_SEND_ROI_VALUES:
            return self._handle_send_roi_values(fl_ctx)

        if task_name == TASK_SEND_SITE_STATS:
            return self._handle_send_site_stats(fl_ctx)

        if task_name == TASK_ACCEPT_GLOBAL_RESULTS:
            return self._handle_accept_global_results(shareable, fl_ctx)

        logging.warning(f"Unknown task: {task_name}")
        return Shareable()

    # ------------------------------------------------------------------ #
    # Task handlers                                                        #
    # ------------------------------------------------------------------ #

    def _handle_run_halfpipe(self, fl_ctx: FLContext) -> Shareable:
        output_dir = get_output_directory_path(fl_ctx)
        halfpipe_workdir = os.path.join(output_dir, "halfpipe_workdir")

        # In production, DATA_DIR is the BIDS root the user selected in the
        # NeuroFLAME UI. In simulation it resolves to test_data/siteN/.
        bids_directory = get_data_directory_path(fl_ctx)

        halfpipe_result = run_halfpipe_and_get_qc(
            site_data=self._site_data,
            params=self._params,
            workdir=halfpipe_workdir,
            bids_directory=bids_directory,
        )
        self._halfpipe_result = halfpipe_result
        # Persist so subsequent tasks (run in separate subprocesses by the simulator) can load it.
        _save_json(halfpipe_result, "halfpipe_result.json", fl_ctx)

        qc_payload = extract_qc_metadata(
            n_subjects=halfpipe_result["n_subjects"],
            qc_summary=halfpipe_result["qc_summary"],
        )

        _save_json(qc_payload, "qc_metadata.json", fl_ctx)

        result = Shareable()
        result["result"] = qc_payload
        return result

    def _handle_send_roi_values(self, fl_ctx: FLContext) -> Shareable:
        if self._halfpipe_result is None:
            self._halfpipe_result = self._load_halfpipe_result(fl_ctx)
        if self._halfpipe_result is None:
            raise RuntimeError("RUN_HALFPIPE must complete before SEND_ROI_VALUES")

        roi_values = extract_roi_values(
            derivatives_path=self._halfpipe_result.get("derivatives_path"),
            site_data=self._site_data,
            params=self._params,
        )

        payload = {
            "roi_values": roi_values,
            "n_subjects": self._halfpipe_result.get("n_subjects", 0),
        }
        _save_json(payload, "roi_values.json", fl_ctx)

        result = Shareable()
        result["result"] = payload
        return result

    def _handle_send_site_stats(self, fl_ctx: FLContext) -> Shareable:
        if self._halfpipe_result is None:
            self._halfpipe_result = self._load_halfpipe_result(fl_ctx)
        if self._halfpipe_result is None:
            raise RuntimeError("RUN_HALFPIPE must complete before SEND_SITE_STATS")

        output_dir = get_output_directory_path(fl_ctx)
        site_stats_payload = run_site_group_level(
            derivatives_path=self._halfpipe_result.get("derivatives_path"),
            site_data=self._site_data,
            params=self._params,
            output_dir=output_dir,
        )
        _save_json(
            {"n_subjects": site_stats_payload["n_subjects"], "n_maps": len(site_stats_payload.get("site_stats", {}))},
            "site_stats_summary.json",
            fl_ctx,
        )

        result = Shareable()
        result["result"] = site_stats_payload
        return result

    def _handle_accept_global_results(self, shareable: Shareable, fl_ctx: FLContext) -> Shareable:
        global_results = shareable.get("global_results", {})
        _save_json(global_results, "global_results.json", fl_ctx)

        site_name = fl_ctx.get_prop(FLContextKey.CLIENT_NAME, "site")
        output_dir = get_output_directory_path(fl_ctx)
        html = generate_html_report(site_name, global_results)
        report_path = os.path.join(output_dir, "index.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)
        logging.info(f"HTML report written to {report_path}")

        return Shareable()

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _load_halfpipe_result(self, fl_ctx: FLContext) -> dict | None:
        output_dir = get_output_directory_path(fl_ctx)
        path = os.path.join(output_dir, "halfpipe_result.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def _load_params(self, fl_ctx: FLContext) -> dict:
        params_path = get_parameters_file_path(fl_ctx)
        with open(params_path) as f:
            params = json.load(f)
        logging.info(f"Loaded parameters from {params_path}")
        return params

    def _load_site_data(self, fl_ctx: FLContext) -> dict:
        data_dir = get_data_directory_path(fl_ctx)
        data_path = os.path.join(data_dir, "data.json")
        if not os.path.exists(data_path):
            logging.warning(f"No data.json found at {data_path}; using empty site data")
            return {}
        with open(data_path) as f:
            site_data = json.load(f)
        logging.info(f"Loaded site data from {data_path}")
        return site_data


def _save_json(data: dict, filename: str, fl_ctx: FLContext) -> None:
    output_dir = get_output_directory_path(fl_ctx)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logging.info(f"Saved {filename} to {output_dir}")
