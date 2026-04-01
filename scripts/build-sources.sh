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
  $PYTHON_CMD -m scripts.bdf2ufo.cli -v -c "$configfile" "$bdffile" sources || {
    err "bdf2ufo conversion failed"
    return 1
  }

  info "Copying $bdffile to fonts/bdf"
  mkdir -p fonts/bdf
  cp -v $bdffile fonts/bdf || warn "No .bdf files copied"

  info "Build finished"
}

main() {
  if [ $# -ge 2 ]; then
    build_font "$1" "$2"
  else
    err "Usage: $0 <bdf-file> <config-file>"
    exit 1
  fi
}

main "$@"
