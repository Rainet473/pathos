#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
ENV_FILE="${REPOSITORY_ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo ".env file not found at ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "${CONDA_PREFIX:-}" ]]; then
  echo "No active conda environment. Activate the project environment before running this script." >&2
  exit 1
fi

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "uvicorn was not found in the active conda environment" >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a

exec uvicorn voice_presentation.server.app:create_configured_app \
  --factory \
  --app-dir "${REPOSITORY_ROOT}/backend/src" \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  "$@"
