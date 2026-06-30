import logging
from typing import Any, Dict

from nvflare.apis.fl_context import FLContext
from nvflare.apis.fl_constant import ReservedKey
from nvflare.apis.shareable import Shareable
from nvflare.app_common.abstract.aggregator import Aggregator

from .aggregate_results import aggregate_qc_metadata, aggregate_roi_values, aggregate_voxelwise


class HALFpipeAggregator(Aggregator):
    """
    Collects per-site results from each computation phase and aggregates them.

    Three storage buckets correspond to the three task types:
      halfpipe_results  — from RUN_HALFPIPE  (QC metadata)
      roi_results       — from SEND_ROI_VALUES
      voxelwise_results — from SEND_SITE_STATS
    """

    def __init__(self):
        super().__init__()
        self._halfpipe_results: Dict[str, dict] = {}
        self._roi_results: Dict[str, dict] = {}
        self._voxelwise_results: Dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    # Phase-specific accept methods                                        #
    # ------------------------------------------------------------------ #

    def accept_halfpipe_result(self, client_task, fl_ctx: FLContext) -> bool:
        site_name = _get_site_name(client_task.result)
        result_data = client_task.result.get("result", {})
        self._halfpipe_results[site_name] = result_data
        logging.info(f"Accepted HALFpipe QC result from {site_name}: n_subjects={result_data.get('n_subjects')}")
        return True

    def accept_roi_result(self, client_task, fl_ctx: FLContext) -> bool:
        site_name = _get_site_name(client_task.result)
        result_data = client_task.result.get("result", {})
        self._roi_results[site_name] = result_data
        features = list(result_data.get("roi_values", {}).keys())
        logging.info(f"Accepted ROI values from {site_name}: features={features}")
        return True

    def accept_voxelwise_result(self, client_task, fl_ctx: FLContext) -> bool:
        site_name = _get_site_name(client_task.result)
        result_data = client_task.result.get("result", {})
        self._voxelwise_results[site_name] = result_data
        n_maps = len(result_data.get("site_stats", {}))
        logging.info(f"Accepted voxelwise stats from {site_name}: {n_maps} maps")
        return True

    # ------------------------------------------------------------------ #
    # Required Aggregator interface method                                 #
    # ------------------------------------------------------------------ #

    def accept(self, site_result: Shareable, fl_ctx: FLContext) -> bool:
        """Fallback accept — routes by task type tag if present."""
        task_type = site_result.get("task_type")
        if task_type == "roi":
            self._roi_results[_get_site_name(site_result)] = site_result.get("result", {})
        elif task_type == "voxelwise":
            self._voxelwise_results[_get_site_name(site_result)] = site_result.get("result", {})
        else:
            self._halfpipe_results[_get_site_name(site_result)] = site_result.get("result", {})
        return True

    # ------------------------------------------------------------------ #
    # Aggregation                                                          #
    # ------------------------------------------------------------------ #

    def aggregate(self, fl_ctx: FLContext) -> Shareable:
        """
        Aggregate all collected results and return a Shareable containing
        the global results to be broadcast back to all sites.
        """
        global_results: Dict[str, Any] = {}

        if self._halfpipe_results:
            logging.info(f"Aggregating QC metadata from {len(self._halfpipe_results)} sites")
            global_results["qc_metadata"] = aggregate_qc_metadata(self._halfpipe_results)

        if self._roi_results:
            logging.info(f"Aggregating ROI values from {len(self._roi_results)} sites")
            global_results["roi_values"] = aggregate_roi_values(self._roi_results)

        if self._voxelwise_results:
            logging.info(f"Aggregating voxelwise maps from {len(self._voxelwise_results)} sites")
            global_results["voxelwise_maps"] = aggregate_voxelwise(self._voxelwise_results)

        outgoing = Shareable()
        outgoing["global_results"] = global_results
        return outgoing


def _get_site_name(shareable: Shareable) -> str:
    return shareable.get_peer_prop(key=ReservedKey.IDENTITY_NAME, default="unknown_site")
