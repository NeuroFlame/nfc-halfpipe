"""Declare the HALFpipe federated computation workflow.

Task sequence (NVFlare task names map directly to step names):

  RUN_HALFPIPE            — site runs HALFpipe; server aggregates QC metadata
  SEND_ROI_VALUES         — site sends parcellated feature means; server aggregates
  SEND_ATLAS_CONNECTIVITY — site sends Fisher-z FC matrices; server federates
  SEND_SITE_STATS         — site sends within-site stat maps; server meta-analyses
  ACCEPT_GLOBAL_RESULTS   — server sends accumulated results; site writes report

Steps 2–4 are conditional: each local step returns None when its aggregation
type is absent from parameters.json, and the server passes accumulated state
through unchanged. The final server payload contains only the enabled modes.
"""

from framework import (
    ComputationSpec,
    local_step,
    remote_step,
    site_output_step,
    stepped_workflow,
)

from .local_steps import (
    build_outputs,
    load_site_data,
    run_halfpipe,
    send_atlas_connectivity,
    send_roi_values,
    send_site_stats,
)
from .remote_steps import (
    aggregate_connectivity_step,
    aggregate_qc_step,
    aggregate_roi_step,
    aggregate_voxelwise_step,
)

SPEC = ComputationSpec(
    workflow=stepped_workflow(
        local_step(fn=run_halfpipe, input_fn=load_site_data, name="RUN_HALFPIPE"),
        remote_step(fn=aggregate_qc_step),
        local_step(fn=send_roi_values, name="SEND_ROI_VALUES"),
        remote_step(fn=aggregate_roi_step),
        local_step(fn=send_atlas_connectivity, name="SEND_ATLAS_CONNECTIVITY"),
        remote_step(fn=aggregate_connectivity_step),
        local_step(fn=send_site_stats, name="SEND_SITE_STATS"),
        remote_step(fn=aggregate_voxelwise_step),
        site_output_step(fn=build_outputs, name="ACCEPT_GLOBAL_RESULTS"),
    ),
)
