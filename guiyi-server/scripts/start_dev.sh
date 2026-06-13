#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SERVER_DIR}/.." && pwd)"
VENV_DIR="${SERVER_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

ENV_FILE="${GUIYI_DEV_ENV_FILE:-}"
if [[ -z "${ENV_FILE}" ]]; then
  if [[ -f "${REPO_ROOT}/guiyi-server.dev.env" ]]; then
    ENV_FILE="${REPO_ROOT}/guiyi-server.dev.env"
  elif [[ -f "${REPO_ROOT}/.env.dev" ]]; then
    ENV_FILE="${REPO_ROOT}/.env.dev"
  fi
fi

if [[ -n "${ENV_FILE}" ]]; then
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Development env file does not exist: ${ENV_FILE}" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

export GUIYI_ENV="${GUIYI_ENV:-dev}"
export API_HOST="${API_HOST:-127.0.0.1}"
export API_PORT="${API_PORT:-8766}"
export API_DEBUG="${API_DEBUG:-true}"
export GUIYI_DATA_DIR="${GUIYI_DATA_DIR:-${REPO_ROOT}/data-dev}"
export GUIYI_EMBEDDING_MODEL_PATH="${GUIYI_EMBEDDING_MODEL_PATH:-${REPO_ROOT}/models-dev/BAAI/bge-m3}"
export GUIYI_IMAGE_VLM_MODEL="${GUIYI_IMAGE_VLM_MODEL:-${REPO_ROOT}/models-dev/mlx-community/Qwen2.5-VL-7B-Instruct-4bit}"
export GUIYI_SKIP_STARTUP_ACCOUNT_LOAD="${GUIYI_SKIP_STARTUP_ACCOUNT_LOAD:-true}"
export GUIYI_SCHEDULER_ENABLED="${GUIYI_SCHEDULER_ENABLED:-false}"

PROD_DATA_DIR="/Users/yswwpp/dev/docker_file_sharing/GuiYi/data"
PROD_MODELS_DIR="/Users/yswwpp/dev/docker_file_sharing/GuiYi/models"

resolved_data_dir="$(python3 - <<PY
from pathlib import Path
print(Path("${GUIYI_DATA_DIR}").expanduser().resolve())
PY
)"

if [[ "${resolved_data_dir}" == "${PROD_DATA_DIR}" || "${resolved_data_dir}" == "${PROD_DATA_DIR}/"* ]]; then
  echo "Refusing to start dev backend with production data dir: ${resolved_data_dir}" >&2
  exit 1
fi

if [[ "${API_PORT}" == "8765" ]]; then
  echo "Refusing to start dev backend on production port 8765. Use 8766." >&2
  exit 1
fi

if [[ "${GUIYI_EMBEDDING_MODEL_PATH}" == "${PROD_MODELS_DIR}"* ]]; then
  echo "Refusing to start dev backend with production model dir: ${GUIYI_EMBEDDING_MODEL_PATH}" >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Missing virtual environment: ${VENV_DIR}" >&2
  echo "Create it with: cd ${SERVER_DIR} && uv venv && source .venv/bin/activate && uv pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing Python executable: ${PYTHON_BIN}" >&2
  exit 1
fi

mkdir -p "${GUIYI_DATA_DIR}"

"${PYTHON_BIN}" - <<'PY'
import json
import os
import sys
from pathlib import Path

config_path = Path(os.environ["GUIYI_DATA_DIR"]).expanduser().resolve() / "db_config.json"
if not config_path.exists():
    print(f"Missing development database config: {config_path}", file=sys.stderr)
    print("Create it with database.database set to guiyi_dev before starting dev backend.", file=sys.stderr)
    sys.exit(1)

try:
    database = json.loads(config_path.read_text(encoding="utf-8")).get("database", {})
except Exception as exc:
    print(f"Failed to read development database config: {exc}", file=sys.stderr)
    sys.exit(1)

schema = database.get("database")
if schema != "guiyi_dev":
    print(f"Refusing to start dev backend with database schema {schema!r}; expected 'guiyi_dev'.", file=sys.stderr)
    sys.exit(1)
PY

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${API_PORT} is already in use." >&2
  lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >&2
  exit 1
fi

export VIRTUAL_ENV="${VENV_DIR}"
export PATH="${VENV_DIR}/bin:${PATH}"

echo "Starting GuiYi development backend..."
echo "Env file: ${ENV_FILE:-<none; using script defaults>}"
echo "API: http://${API_HOST}:${API_PORT}"
echo "Data: ${resolved_data_dir}"
echo "Scheduler: ${GUIYI_SCHEDULER_ENABLED}"

cd "${SERVER_DIR}"
exec "${PYTHON_BIN}" -m uvicorn guiyi_server.app:app --reload --host "${API_HOST}" --port "${API_PORT}"
