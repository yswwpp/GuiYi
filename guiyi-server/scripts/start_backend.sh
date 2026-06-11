#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${SERVER_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

HOST="${API_HOST:-127.0.0.1}"
PORT="${API_PORT:-8765}"

cd "${SERVER_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Missing virtual environment: ${VENV_DIR}" >&2
  echo "Create it under guiyi-server, then install dependencies with uv." >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing Python executable: ${PYTHON_BIN}" >&2
  exit 1
fi

export VIRTUAL_ENV="${VENV_DIR}"
export PATH="${VENV_DIR}/bin:${PATH}"

"${PYTHON_BIN}" - <<'PY'
import importlib.util
import sys

missing = [
    module
    for module in ("fastapi", "uvicorn")
    if importlib.util.find_spec(module) is None
]

if missing:
    print("Missing required packages: " + ", ".join(missing), file=sys.stderr)
    print("Install backend dependencies before starting the service.", file=sys.stderr)
    sys.exit(1)
PY

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT} is already in use." >&2
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >&2
  exit 1
fi

echo "Starting GuiYi Backend..."
echo "API: http://${HOST}:${PORT}"
echo "Docs: http://${HOST}:${PORT}/docs"

exec "${PYTHON_BIN}" -m guiyi_server
