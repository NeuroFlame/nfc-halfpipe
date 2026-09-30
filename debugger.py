"""Run an NVFlare simulation and surface recorded computation failures."""

import argparse
import json
import os
import subprocess
import sys

from framework.errors import raise_for_terminal_errors

_SIMULATOR_ALLOWED_CLASS_PREFIXES = ("nvflare.", "runtime.", "framework.")


def define_simulator_parser(simulator_parser):
    """Add supported simulation arguments to an argument parser."""
    simulator_parser.add_argument("job_folder")
    simulator_parser.add_argument(
        "-w", "--workspace", type=str, default="/tmp/nfc_sim",
        help="WORKSPACE folder (default: /tmp/nfc_sim — avoids NVFlare path-quoting issues with spaces)"
    )
    simulator_parser.add_argument(
        "-n", "--n_clients", type=int, help="number of clients"
    )
    simulator_parser.add_argument("-c", "--clients", type=str, help="client names list")
    simulator_parser.add_argument(
        "-t", "--threads", type=int, help="number of parallel running clients"
    )
    simulator_parser.add_argument(
        "-gpu", "--gpu", type=str, help="list of GPU Device Ids, comma separated"
    )
    simulator_parser.add_argument(
        "-m", "--max_clients", type=int, default=100, help="max number of clients"
    )
    simulator_parser.add_argument(
        "-l", "--log_config", type=str, help="NVFlare log configuration"
    )
    simulator_parser.add_argument("--end_run_for_all", action="store_true")


def build_simulator_command(simulator_args):
    """Build a supported NVFlare 2.8 simulator CLI command."""
    command = ["nvflare", "simulator", simulator_args.job_folder]
    optional_values = (
        ("-w", simulator_args.workspace),
        ("-n", simulator_args.n_clients),
        ("-c", simulator_args.clients),
        ("-t", simulator_args.threads),
        ("-gpu", simulator_args.gpu),
        ("-l", simulator_args.log_config),
        ("-m", simulator_args.max_clients),
    )
    for option, value in optional_values:
        if value is not None:
            command.extend((option, str(value)))
    if simulator_args.end_run_for_all:
        command.append("--end_run_for_all")
    return command


def configure_simulator_authorization(workspace):
    """Authorize framework-owned components in an NVFlare 2.8 simulator workspace."""
    workspace_path = os.path.abspath(workspace or "simulator_workspace")
    local_path = os.path.join(workspace_path, "local")
    resources_path = os.path.join(local_path, "resources.json")
    os.makedirs(local_path, exist_ok=True)

    if os.path.exists(resources_path):
        with open(resources_path, encoding="utf-8") as resources_file:
            resources = json.load(resources_file)
    else:
        resources = {"format_version": 2}

    allow_list = resources.setdefault("class_allow_list", [])
    if not isinstance(allow_list, list):
        raise TypeError(f"Invalid class_allow_list in '{resources_path}'")
    for class_prefix in _SIMULATOR_ALLOWED_CLASS_PREFIXES:
        if class_prefix not in allow_list:
            allow_list.append(class_prefix)

    with open(resources_path, "w", encoding="utf-8") as resources_file:
        json.dump(resources, resources_file, indent=2)
        resources_file.write("\n")


def run_simulator(simulator_args):
    """Run a simulation and raise any terminal computation failures.

    Uses the SimulatorRunner Python API directly rather than the 'nvflare simulator'
    CLI subprocess.  The CLI spawns worker processes by reconstructing the command
    line, which breaks on workspace paths containing spaces (a known issue in
    NVFlare 2.8 on macOS).  The Python API avoids this by communicating through
    in-process calls and avoids the CLI's Python-version gating entirely.
    """
    configure_simulator_authorization(simulator_args.workspace)
    return_code = _run_via_python_api(simulator_args)

    result_root = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "test_output",
        "simulate_job",
    )
    raise_for_terminal_errors(result_root)
    return return_code


def _run_via_python_api(simulator_args) -> int:
    """Run via SimulatorRunner Python API (bypasses CLI version and path-quoting issues)."""
    from nvflare.private.fed.app.simulator.simulator_runner import SimulatorRunner

    runner = SimulatorRunner(
        job_folder=simulator_args.job_folder,
        workspace=simulator_args.workspace,
        clients=simulator_args.clients,
        n_clients=simulator_args.n_clients,
        threads=getattr(simulator_args, "threads", None),
        gpu=getattr(simulator_args, "gpu", None),
        max_clients=getattr(simulator_args, "max_clients", 100),
    )
    return runner.run() or 0


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        raise RuntimeError("Please use Python 3.10 or above.")

    # Default workspace to /tmp to avoid NVFlare subprocess path-quoting issues
    # on macOS when the project is inside a directory whose name contains spaces
    # (e.g. "NeuroFLAME Computations/...").  The simulator spawns client workers
    # as subprocesses and doesn't quote the workspace path, so any space in the
    # absolute path causes argument-parsing failures in the worker.
    # Using /tmp/nfc_sim sidesteps this entirely without affecting test data
    # resolution (find_repo_root_path() searches from __file__ as a fallback).

    parser = argparse.ArgumentParser()
    define_simulator_parser(parser)
    args = parser.parse_args()
    status = run_simulator(args)
    sys.exit(status)
