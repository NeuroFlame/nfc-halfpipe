#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_WORKSPACE="$SCRIPT_DIR"
REMOTE_WORKSPACE="/workspace"
IMAGE_NAME="nfc-halfpipe:dev"
CONTAINER_NAME="nfc-halfpipe-sim-$$"
DOCKERFILE_PATH="$LOCAL_WORKSPACE/Dockerfile-prod"
SIMULATOR_WORKSPACE="simulator_workspace"

usage() {
    cat <<EOF
Usage:
  ./run_local_simulation.sh site1,site2[,site3...] [OPTIONS]

Options:
  --no-build              Skip Docker image build (use existing nfc-halfpipe:dev)
  --params PARAMS_FILE    Parameters file relative to project root
                          (default: test_data/server/parameters.json)
  --license LICENSE_FILE  Host path to FreeSurfer license
                          (mounted read-only at /workspace/license.txt)

Examples:
  ./run_local_simulation.sh site1,site2
  ./run_local_simulation.sh site1 \\
      --params test_data/server/parameters_tier2test.json \\
      --license ~/license.txt
  ./run_local_simulation.sh site1,site2,site3 \\
      --params test_data/server/parameters_tier3test.json \\
      --no-build
EOF
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

join_by_comma() {
    local IFS=","
    echo "$*"
}

require_command docker

if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

SITES_ARG=""
BUILD_IMAGE=1
PARAMS_FILE=""
LICENSE_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-build)
            BUILD_IMAGE=0
            shift
            ;;
        --params)
            PARAMS_FILE="$2"
            shift 2
            ;;
        --license)
            LICENSE_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [[ -n "$SITES_ARG" ]]; then
                echo "Unexpected extra argument: $1" >&2
                usage
                exit 1
            fi
            SITES_ARG="$1"
            shift
            ;;
    esac
done

if [[ -z "$SITES_ARG" ]]; then
    echo "A comma-separated site list is required." >&2
    usage
    exit 1
fi

IFS=',' read -r -a RAW_SITES <<< "$SITES_ARG"
SITES=()
for site in "${RAW_SITES[@]}"; do
    site="${site// /}"
    if [[ -n "$site" ]]; then
        SITES+=("$site")
    fi
done

if [[ ${#SITES[@]} -eq 0 ]]; then
    echo "No valid site names were provided." >&2
    exit 1
fi

SITES_CSV="$(join_by_comma "${SITES[@]}")"
N_SITES="${#SITES[@]}"

echo "Selected sites: $SITES_CSV"
echo "Result root: $RESULT_ROOT"

rm -rf "$RESULT_ROOT"

if [[ $BUILD_IMAGE -eq 1 ]]; then
    echo
    echo "Building Docker image '$IMAGE_NAME' from $DOCKERFILE_PATH ..."
    docker build -t "$IMAGE_NAME" -f "$DOCKERFILE_PATH" "$LOCAL_WORKSPACE"
fi

# ── Assemble docker run arguments ────────────────────────────────────────────
# --platform linux/amd64: required on Apple Silicon (Rosetta 2 emulation) so
# that the linux/amd64 image runs correctly and FSL/HALFpipe work as expected.
DOCKER_ARGS=(
    --rm
    --platform linux/amd64
    --ipc=host --ulimit memlock=-1 --ulimit stack=67108864
    --name "$CONTAINER_NAME"
    -v "$LOCAL_WORKSPACE:$REMOTE_WORKSPACE"
    -w "$REMOTE_WORKSPACE"
)

if [[ -n "$PARAMS_FILE" ]]; then
    DOCKER_ARGS+=(-e "PARAMETERS_FILE_PATH=$REMOTE_WORKSPACE/$PARAMS_FILE")
    echo "Parameters: $PARAMS_FILE"
fi

LICENSE_COPY=""
if [[ -n "$LICENSE_FILE" ]]; then
    # Docker on macOS cannot bind-mount a file inside an already bind-mounted
    # directory (virtiofs nested mount restriction).  Copy the license to the
    # project root so the existing -v mount delivers it as /workspace/license.txt
    # inside the container (matches fs_license_path in the parameters files).
    # The copy is deleted after docker run returns.  If this script is killed
    # while Docker is still running the license stays on disk (it is gitignored)
    # so FreeSurfer can continue to access it inside the container.
    LICENSE_ABS="$(eval echo "$LICENSE_FILE")"
    LICENSE_ABS="$(cd "$(dirname "$LICENSE_ABS")" && pwd)/$(basename "$LICENSE_ABS")"
    LICENSE_COPY="$LOCAL_WORKSPACE/license.txt"
    cp "$LICENSE_ABS" "$LICENSE_COPY"
    echo "FreeSurfer license: $LICENSE_FILE → $LICENSE_COPY"
fi

echo
echo "Running NVFlare simulation..."
docker run "${DOCKER_ARGS[@]}" \
    "$IMAGE_NAME" \
    /bin/bash -lc "set -euo pipefail; rm -rf ./job ./$SIMULATOR_WORKSPACE; python makeJob.py '$SITES_CSV'; python debugger.py ./job -w ./$SIMULATOR_WORKSPACE -n $N_SITES -c '$SITES_CSV'"

[[ -n "$LICENSE_COPY" ]] && rm -f "$LICENSE_COPY"

OUTPUT_DIR="$LOCAL_WORKSPACE/output"
echo
echo "Simulation output ($OUTPUT_DIR):"
if [[ -d "$OUTPUT_DIR" ]]; then
    find "$OUTPUT_DIR" -maxdepth 2 -type f | sort
else
    echo "No output directory found at $OUTPUT_DIR" >&2
    exit 1
fi
