# Migration to computation-nvflare-boilerplate

This computation runs on
[`computation-nvflare-boilerplate`](https://github.com/NeuroFlame/computation-nvflare-boilerplate)
`0.1.0` (NVFlare 2.8). The migration happened in two steps:

1. Commit `af46527` moved the computation onto the boilerplate's
   `framework/`, `runtime/` and `computation/` layout.
2. This follow-up applied the rest of the boilerplate with
   `scripts/migrate_computation.py --in-place --force` at boilerplate commit
   `dbc9503`: the `system/` entrypoints and provisioning code, `app/config/`,
   the image publishing script behind `dockerPush.sh`, `.dockerignore`, and the
   `.neuroflame.json` manifest (image `coinstacteam/nfc-halfpipe`).

## Deviations from the boilerplate

`migrate_computation.py --check` reports five differing paths. Each is
deliberate. All five are migration-managed, so the next `--in-place` migration
overwrites them and they have to be re-applied afterwards.

- **`Dockerfile-prod` and `Dockerfile-dev`** are HALFpipe-specific: the
  production image is built on `halfpipe/halfpipe:1.3.2` and bakes in the
  Schaefer and NeuroMark atlases; the dev image is a native arm64 build for
  Apple Silicon. The boilerplate's generic Python images cannot run HALFpipe.
- **`app/config/config_fed_server.json`** sets `heart_beat_timeout` to `3600`
  instead of the boilerplate's `600`, so sites are not dropped during long
  HALFpipe runs.
- **`app/code/framework/paths.py`** also searches for the repository root from
  the file's own location, not only from the working directory. `debugger.py`
  needs this when the simulator workspace is outside the repository.
- **`debugger.py`** runs the simulator through NVFlare's Python API and
  defaults the workspace to `/tmp/nfc_sim`, because the NVFlare CLI fails on
  macOS when the project path contains spaces.

## NVFlare environment in the images

`requirements.txt` now carries the boilerplate's exact dependency pins in
addition to this computation's own packages (`nibabel`, `templateflow`). The
boilerplate pins target Python 3.11, while HALFpipe's own environment is
Python 3.12 (3.13 in the dev image), so both Dockerfiles now build the NVFlare
venv at `/opt/nfc-env` from a separate Python 3.11 interpreter. HALFpipe itself
still runs from its own conda environment.

Before this change the requirements were unpinned and the venv used Python
3.12, which installed gRPC 1.84 and protobuf 7. In a two-site run on a local
NeuroFLAME platform, one site's gRPC connection failed with TLS corruption
errors and the run hung. With the pinned environment (gRPC 1.62.1, protobuf
4.24.4) the same run completes.

## Other changes

- `system/entry_edge.py` no longer sets `DATA_DIR`/`OUTPUT_DIR` defaults; it is
  the boilerplate's file. `Dockerfile-prod` sets both variables, so behaviour
  in the image is the same.
- `dockerPush.sh` now runs the boilerplate's publishing script, which builds
  `Dockerfile-prod`, validates the manifest and labels, and pushes
  `coinstacteam/nfc-halfpipe` with `latest`, version and Git-revision tags. The
  previous script pushed to a placeholder repository.
- `dockerPush.sh`, `dockerRun.sh` and `run_local_simulation.sh` are marked
  executable.

## Verification

- **Mock simulation**: the three-site mock run (`run_halfpipe: false`) gives
  the same values before and after applying the boilerplate's `system/`,
  provisioning and config files.
- **Production image**: `./dockerPush.sh --no-push` builds and validates the
  image. In it, NVFlare 2.8.0, the atlases under `/atlases`, and `halfpipe
  1.3.2` are present, and the computation spec imports.
- **Local NeuroFLAME platform**: a two-site run of the production image with
  the mock test data completes; both sites receive `global_results.json` and
  `index.html` with QC, ROI and connectivity results.

**Not verified**:

- A run with `run_halfpipe: true` on real BIDS data. Only the mock path was
  exercised.
- The `Dockerfile-dev` change. That image compiles ANTs from source and was not
  rebuilt.
- `make check`. The repository does not yet meet the boilerplate's lint and
  format rules (existing code under `app/code/executor/`, `aggregator/` and
  `_utils/`), so the boilerplate's CI workflow was not added.
