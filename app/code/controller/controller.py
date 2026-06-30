import json
import logging
from typing import Callable, Optional

from nvflare.apis.impl.controller import Controller, Task, ClientTask
from nvflare.apis.fl_context import FLContext
from nvflare.apis.signal import Signal
from nvflare.apis.shareable import Shareable

from _utils.utils import get_parameters_file_path

TASK_RUN_HALFPIPE = "RUN_HALFPIPE"
TASK_SEND_ROI_VALUES = "SEND_ROI_VALUES"
TASK_SEND_SITE_STATS = "SEND_SITE_STATS"
TASK_ACCEPT_GLOBAL_RESULTS = "ACCEPT_GLOBAL_RESULTS"

AGGREGATOR_ID = "aggregator"


class HALFpipeController(Controller):
    """
    NVFlare controller for federated HALFpipe analysis.

    Control flow:
      Phase 1  — broadcast RUN_HALFPIPE to all sites (runs subject-level, collects QC)
      Phase 2a — broadcast SEND_ROI_VALUES if "roi_values" in aggregation_types
      Phase 2b — broadcast SEND_SITE_STATS  if "voxelwise_maps" in aggregation_types
      Phase 3  — aggregate all collected data and broadcast ACCEPT_GLOBAL_RESULTS
    """

    def __init__(
        self,
        min_clients: int = 2,
        wait_time_after_min_received: int = 10,
        task_timeout: int = 0,
    ):
        super().__init__()
        self._min_clients = min_clients
        self._wait_time_after_min_received = wait_time_after_min_received
        self._task_timeout = task_timeout
        self._params: Optional[dict] = None

    # ------------------------------------------------------------------ #
    # Framework lifecycle methods                                          #
    # ------------------------------------------------------------------ #

    def start_controller(self, fl_ctx: FLContext) -> None:
        self.aggregator = self._engine.get_component(AGGREGATOR_ID)
        self._params = self._load_params(fl_ctx)

    def stop_controller(self, fl_ctx: FLContext) -> None:
        pass

    def process_result_of_unknown_task(self, task: Task, fl_ctx: FLContext) -> None:
        pass

    # ------------------------------------------------------------------ #
    # Main control flow                                                    #
    # ------------------------------------------------------------------ #

    def control_flow(self, abort_signal: Signal, fl_ctx: FLContext) -> None:
        aggregation_types = self._params.get("aggregation_types", ["qc_metadata"])
        if isinstance(aggregation_types, str):
            aggregation_types = [aggregation_types]

        logging.info(f"Aggregation types: {aggregation_types}")

        # Phase 1: Run HALFpipe + collect QC on every site
        logging.info("Phase 1: Running HALFpipe on all sites")
        self._broadcast_task(
            task_name=TASK_RUN_HALFPIPE,
            data=Shareable(),
            result_cb=self.aggregator.accept_halfpipe_result,
            fl_ctx=fl_ctx,
            abort_signal=abort_signal,
        )

        # Phase 2a: Collect parcellated ROI values
        if "roi_values" in aggregation_types:
            logging.info("Phase 2a: Collecting ROI values from all sites")
            self._broadcast_task(
                task_name=TASK_SEND_ROI_VALUES,
                data=Shareable(),
                result_cb=self.aggregator.accept_roi_result,
                fl_ctx=fl_ctx,
                abort_signal=abort_signal,
            )

        # Phase 2b: Collect within-site voxelwise stat maps
        if "voxelwise_maps" in aggregation_types:
            logging.info("Phase 2b: Collecting voxelwise stat maps from all sites")
            self._broadcast_task(
                task_name=TASK_SEND_SITE_STATS,
                data=Shareable(),
                result_cb=self.aggregator.accept_voxelwise_result,
                fl_ctx=fl_ctx,
                abort_signal=abort_signal,
            )

        # Phase 3: Aggregate and send global results back to all sites
        logging.info("Phase 3: Aggregating results and sending back to sites")
        global_results_shareable = self.aggregator.aggregate(fl_ctx)
        self._broadcast_task(
            task_name=TASK_ACCEPT_GLOBAL_RESULTS,
            data=global_results_shareable,
            result_cb=None,
            fl_ctx=fl_ctx,
            abort_signal=abort_signal,
        )

        logging.info("Federated HALFpipe computation complete")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _broadcast_task(
        self,
        task_name: str,
        data: Shareable,
        result_cb: Optional[Callable],
        fl_ctx: FLContext,
        abort_signal: Signal,
    ) -> None:
        self.broadcast_and_wait(
            task=Task(
                name=task_name,
                data=data,
                props={},
                timeout=self._task_timeout,
                result_received_cb=result_cb,
            ),
            min_responses=self._min_clients,
            wait_time_after_min_received=self._wait_time_after_min_received,
            fl_ctx=fl_ctx,
            abort_signal=abort_signal,
        )

    def _load_params(self, fl_ctx: FLContext) -> dict:
        params_path = get_parameters_file_path(fl_ctx)
        with open(params_path) as f:
            params = json.load(f)
        fl_ctx.set_prop(
            key="COMPUTATION_PARAMETERS",
            value=params,
            private=False,
            sticky=True,
        )
        logging.info(f"Loaded parameters from {params_path}")
        return params
