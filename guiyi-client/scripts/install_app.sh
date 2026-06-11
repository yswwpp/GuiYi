#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT="${CLIENT_DIR}/GuiYi.xcodeproj"
SCHEME="GuiYi"
CONFIGURATION="Release"
APP_NAME="GuiYi.app"
BUNDLE_ID="com.guiyi.GuiYi"
INSTALL_DIR="${HOME}/Applications"
OPEN_AFTER_INSTALL=1
CLEAN=0

usage() {
  cat <<'EOF'
Usage: scripts/install_app.sh [options]

Build and install GuiYi.app locally.

Options:
  --debug                 Build Debug instead of Release.
  --release               Build Release. This is the default.
  --clean                 Clean before building.
  --install-dir PATH      Install to PATH. Default: ~/Applications.
  --system                Install to /Applications.
  --no-open               Do not open the app after installation.
  -h, --help              Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      CONFIGURATION="Debug"
      shift
      ;;
    --release)
      CONFIGURATION="Release"
      shift
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    --install-dir)
      if [[ $# -lt 2 ]]; then
        echo "--install-dir requires a path" >&2
        exit 1
      fi
      INSTALL_DIR="$2"
      shift 2
      ;;
    --system)
      INSTALL_DIR="/Applications"
      shift
      ;;
    --no-open)
      OPEN_AFTER_INSTALL=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "xcodebuild not found. Install Xcode or select it with xcode-select." >&2
  exit 1
fi

ARCH="$(uname -m)"
BUILD_ROOT="${CLIENT_DIR}/build"
DERIVED_DATA="${BUILD_ROOT}/DerivedData"
DEST_APP="${INSTALL_DIR}/${APP_NAME}"

mkdir -p "${BUILD_ROOT}" "${INSTALL_DIR}"

if [[ "${CLEAN}" -eq 1 ]]; then
  xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration "${CONFIGURATION}" \
    -destination "platform=macOS,arch=${ARCH}" \
    -derivedDataPath "${DERIVED_DATA}" \
    clean
fi

xcodebuild \
  -project "${PROJECT}" \
  -scheme "${SCHEME}" \
  -configuration "${CONFIGURATION}" \
  -destination "platform=macOS,arch=${ARCH}" \
  -derivedDataPath "${DERIVED_DATA}" \
  build

BUILT_APP="${DERIVED_DATA}/Build/Products/${CONFIGURATION}/${APP_NAME}"
if [[ ! -d "${BUILT_APP}" ]]; then
  echo "Built app not found: ${BUILT_APP}" >&2
  exit 1
fi

if pgrep -x "GuiYi" >/dev/null 2>&1; then
  osascript -e "tell application id \"${BUNDLE_ID}\" to quit" >/dev/null 2>&1 || true
  for _ in {1..20}; do
    if ! pgrep -x "GuiYi" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

if [[ -d "${DEST_APP}" ]]; then
  rm -rf "${DEST_APP}"
fi

ditto "${BUILT_APP}" "${DEST_APP}"

codesign --verify --deep --strict "${DEST_APP}"

echo "Installed: ${DEST_APP}"

if [[ "${OPEN_AFTER_INSTALL}" -eq 1 ]]; then
  open "${DEST_APP}"
fi
