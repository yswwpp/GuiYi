#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SERVER_DIR}/.." && pwd)"

PROD_DATA_DIR="${GUIYI_PROD_DATA_DIR:-/Users/yswwpp/dev/docker_file_sharing/GuiYi/data}"
DEV_DATA_DIR="${GUIYI_DEV_DATA_DIR:-${REPO_ROOT}/data-dev}"

resolved_prod="$(python3 - <<PY
from pathlib import Path
print(Path("${PROD_DATA_DIR}").expanduser().resolve())
PY
)"
resolved_dev="$(python3 - <<PY
from pathlib import Path
print(Path("${DEV_DATA_DIR}").expanduser().resolve())
PY
)"

if [[ ! -d "${resolved_prod}" ]]; then
  echo "Production data dir does not exist: ${resolved_prod}" >&2
  exit 1
fi

if [[ "${resolved_dev}" == "${resolved_prod}" || "${resolved_dev}" == "${resolved_prod}/"* ]]; then
  echo "Refusing to copy production data into itself: ${resolved_dev}" >&2
  exit 1
fi

if [[ "${resolved_dev}" != "${REPO_ROOT}/data-dev" && "${resolved_dev}" != "${REPO_ROOT}/data-dev/"* ]]; then
  echo "Refusing to write outside project dev data dir: ${resolved_dev}" >&2
  echo "Expected ${REPO_ROOT}/data-dev or a child directory." >&2
  exit 1
fi

echo "Snapshot production data to development data."
echo "Source: ${resolved_prod}"
echo "Target: ${resolved_dev}"
echo
echo "This will delete files in the target that do not exist in the source."
read -r -p "Continue? [y/N] " answer

case "${answer}" in
  y|Y|yes|YES)
    mkdir -p "${resolved_dev}"
    rsync -a --delete \
      --exclude='.DS_Store' \
      "${resolved_prod}/" \
      "${resolved_dev}/"
    echo "Development data snapshot complete."
    ;;
  *)
    echo "Cancelled."
    exit 0
    ;;
esac
