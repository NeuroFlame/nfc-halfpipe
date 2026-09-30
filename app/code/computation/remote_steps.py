"""Server-side aggregation steps for HALFpipe federated analysis.

Each function receives a dict of {site_name: payload} from the previous
local step, plus the accumulated remote_state from earlier rounds.

The remote_state grows across rounds:
  after aggregate_qc_step:          {"qc_metadata": {...}}
  after aggregate_roi_step:         {"qc_metadata": {...}, "roi_values": {...}}
  after aggregate_connectivity_step:{"qc_metadata": {...}, ..., "connectivity": {...}}
  after aggregate_voxelwise_step:   full global_results dict  ← sent to build_outputs

A step that is not enabled (its aggregation type is absent) passes the
accumulated state through unchanged, so disabled phases are transparent.
"""

from aggregator.aggregate_results import (
    aggregate_qc_metadata,
    aggregate_roi_values,
    aggregate_connectivity as _agg_connectivity,
    aggregate_voxelwise as _agg_voxelwise,
)
from framework import with_state


def aggregate_qc_step(site_results: dict, state: dict | None = None):
    """Aggregate QC metadata from all sites."""
    accumulated = dict(state or {})
    valid = {site: data for site, data in site_results.items() if data}
    if valid:
        accumulated["qc_metadata"] = aggregate_qc_metadata(valid)
    return with_state(accumulated, accumulated)


def aggregate_roi_step(site_results: dict, parameters: dict, state: dict | None = None):
    """Aggregate ROI values if roi_values is enabled; pass-through otherwise."""
    accumulated = dict(state or {})
    if "roi_values" in _aggregation_types(parameters):
        valid = {site: data for site, data in site_results.items() if data}
        if valid:
            accumulated["roi_values"] = aggregate_roi_values(valid)
    return with_state(accumulated, accumulated)


def aggregate_connectivity_step(site_results: dict, parameters: dict, state: dict | None = None):
    """Aggregate connectivity matrices if atlas_connectivity is enabled; pass-through otherwise."""
    accumulated = dict(state or {})
    if "atlas_connectivity" in _aggregation_types(parameters):
        valid = {site: data for site, data in site_results.items() if data}
        if valid:
            accumulated["connectivity"] = _agg_connectivity(valid)
    return with_state(accumulated, accumulated)


def aggregate_voxelwise_step(site_results: dict, parameters: dict, state: dict | None = None):
    """Aggregate voxelwise maps if enabled; return full accumulated global results."""
    accumulated = dict(state or {})
    if "voxelwise_maps" in _aggregation_types(parameters):
        valid = {site: data for site, data in site_results.items() if data}
        if valid:
            accumulated["voxelwise_maps"] = _agg_voxelwise(valid)
    # Both payload (→ sent to build_outputs) and remote_state are the full accumulated dict.
    return with_state(accumulated, accumulated)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _aggregation_types(parameters: dict) -> list:
    value = parameters.get("aggregation_types", [])
    return [value] if isinstance(value, str) else list(value or [])
