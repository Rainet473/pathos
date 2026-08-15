#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
FRONTEND_DIRECTORY="${REPOSITORY_ROOT}/frontend"

if [[ ! -f "${FRONTEND_DIRECTORY}/package.json" ]]; then
  echo "Frontend package not found at ${FRONTEND_DIRECTORY}" >&2
  exit 1
fi

if [[ ! -d "${FRONTEND_DIRECTORY}/node_modules" ]]; then
  echo "Frontend dependencies are missing. Activate the project conda environment, then run: cd '${FRONTEND_DIRECTORY}' && npm ci" >&2
  exit 1
fi

if [[ -z "${CONDA_PREFIX:-}" ]]; then
  echo "No active conda environment. Activate the project environment before running this script." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found in the active conda environment" >&2
  exit 1
fi

cd "${FRONTEND_DIRECTORY}"

exec npm run dev -- \
  "$@"
