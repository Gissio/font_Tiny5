#!/usr/bin/env bash
set -euo pipefail

# Small helper functions
info() { printf "[INFO] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
err() { printf "[ERROR] %s\n" "$*" >&2; }

# Ensure python is available
if ! command -v python >/dev/null 2>&1; then
  err "python not found in PATH"
  exit 2
fi

PYTHON_CMD=python

# Activate the venv
if [ -f venv/bin/activate ]; then
  # POSIX
  # shellcheck source=/dev/null
  . venv/bin/activate
else
  err "Could not find standard activate script in venv/; continuing without activation"
  exit 3
fi

build_font() {
  local bdffile="$1"
  local configfile="$2"
  if [ ! -f "$bdffile" ]; then
    err "Source BDF not found: $bdffile"
    return 5
  fi
  info "Building UFO from $bdffile with bdf2ufo config $configfile"
  python -m scripts.bdf2ufo.cli -v -c "$configfile" "$bdffile" sources
}

main() {
  build_font sources/Tiny5-Regular.bdf sources/Tiny5-Regular-generator.yaml
  build_font sources/Tiny5Duo-Regular.bdf sources/Tiny5Duo-Regular-generator.yaml

  info "Copying BDF sources to fonts/bdf"
  mkdir -p fonts/bdf
  cp -v sources/*.bdf fonts/bdf || warn "No .bdf files copied"

  info "Build finished"
}

main "$@"
