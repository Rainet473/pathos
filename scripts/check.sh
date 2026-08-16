#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
FRONTEND_DIRECTORY="${REPOSITORY_ROOT}/frontend"

if [[ -z "${CONDA_PREFIX:-}" ]]; then
  echo "No active conda environment. Activate the project environment before running this script." >&2
  exit 1
fi

for command in python npm; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "${command} was not found in the active conda environment" >&2
    exit 1
  fi
done

if [[ ! -d "${FRONTEND_DIRECTORY}/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run: cd '${FRONTEND_DIRECTORY}' && npm ci" >&2
  exit 1
fi

cd "${REPOSITORY_ROOT}"

python -m compileall -q backend/src
python -m pytest -q
python -m pip check

cd "${FRONTEND_DIRECTORY}"
npm test
npm run build
