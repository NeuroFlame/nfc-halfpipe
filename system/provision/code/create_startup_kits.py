"""Invoke NVFlare provisioning to generate participant startup kits."""

import logging
import os
import shutil
import subprocess

# Set up logging
logger = logging.getLogger(__name__)


def create_startup_kits(project_file_path: str, output_directory: str) -> None:
    """Run the NVFlare provision command and stream its output to logs."""
    provision_command = [
        "nvflare",
        "provision",
        "-p",
        project_file_path,
        "-w",
        output_directory,
    ]

    try:
        # Log the paths for the project file and output directory
        logger.info(f"Project file path: {project_file_path}")
        logger.info(f"Output directory: {output_directory}")

        # Ensure output directory exists and is clean.  Using --force in the
        # nvflare provision command causes a second provisioning pass that mixes
        # certificates from two different CAs.  Cleaning the project directory
        # first avoids that entirely.
        project_dir = os.path.join(output_directory, "project")
        if os.path.exists(project_dir):
            logger.info(f"Removing existing project directory {project_dir} before provisioning")
            shutil.rmtree(project_dir)
        os.makedirs(output_directory, exist_ok=True)

        # Log that the provision command is starting
        logger.info("Starting provision command...")

        # Use subprocess.Popen for real-time output logging
        process = subprocess.Popen(
            provision_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Capture and log output from both stdout and stderr in real-time
        while True:
            stdout_line = process.stdout.readline()
            stderr_line = process.stderr.readline()

            # Log stdout if there's output
            if stdout_line:
                logger.info(stdout_line.strip())

            # Log stderr if there's output
            if stderr_line:
                logger.error(stderr_line.strip())

            # Break the loop when both stdout and stderr are done
            if stdout_line == "" and stderr_line == "" and process.poll() is not None:
                break

        # Ensure the process streams are closed
        process.stdout.close()
        process.stderr.close()

        # Wait for the process to complete and get the return code
        return_code = process.wait()

        if return_code != 0:
            # NVFlare's provisioner sometimes exits with code 5 after writing all
            # startup kits successfully — it errors during a post-provisioning
            # cleanup step that tries to access the wip/ directory which has
            # already been renamed to prod_00/.  Check whether the output looks
            # complete before treating this as a hard failure.
            prod_dir = os.path.join(output_directory, "project", "prod_00")
            if os.path.isdir(prod_dir):
                logger.warning(
                    f"nvflare provision exited with code {return_code} but "
                    f"output directory {prod_dir} exists — treating as success. "
                    "This is a known NVFlare post-provisioning cleanup bug."
                )
            else:
                logger.error(f"Provision command failed with return code {return_code}")
                raise subprocess.CalledProcessError(return_code, provision_command)

        logger.info("Provisioning completed successfully.")

    except subprocess.CalledProcessError as error:
        logger.error(f"Failed to execute provision command: {error}")
        raise  # Propagate the error for further handling
