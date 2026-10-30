"""Declare the HALFpipe preprocessing-only workflow.

Task sequence:

  RUN_HALFPIPE          — site runs HALFpipe and writes per-atlas FedLAMP CSVs
                          (data_Schaefer*.csv, data_NeuroMark1.csv, labels.csv);
                          server collects QC metadata
  ACCEPT_GLOBAL_RESULTS — server returns QC summary; site writes HTML report
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
)
from .remote_steps import aggregate_qc_step

SPEC = ComputationSpec(
    workflow=stepped_workflow(
        local_step(fn=run_halfpipe, input_fn=load_site_data, name="RUN_HALFPIPE"),
        remote_step(fn=aggregate_qc_step),
        site_output_step(fn=build_outputs, name="ACCEPT_GLOBAL_RESULTS"),
    ),
)
