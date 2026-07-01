import os
import subprocess
import time
import psutil
import sys

# The edge client mounts the site's BIDS directory at /workspace/data and
# the results directory at /workspace/output. Set these as env vars so that
# get_data_directory_path() and get_output_directory_path() resolve correctly
# inside the container. setdefault preserves any value already injected by
# the container runtime.
os.environ.setdefault("DATA_DIR", "/workspace/data")
os.environ.setdefault("OUTPUT_DIR", "/workspace/output")

print("Starting the shell script...")
subprocess.Popen(["/bin/bash", "/workspace/runKit/startup/start.sh"])


time.sleep(10)

print("Polling for nvflare process and printing process details for debugging...")
while True:
    process_found = False
    for proc in psutil.process_iter(attrs=['cmdline']):
        cmdline = ' '.join(proc.info['cmdline']
                           ) if proc.info['cmdline'] else ''
        if 'nvflare' in cmdline:
            process_found = True
            print("nvflare process is running...")
            break

    if process_found:
        time.sleep(10)
    else:
        print("nvflare process is not running anymore or not found. Exiting.")
        sys.exit(0)
