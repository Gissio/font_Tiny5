#!/usr/bin/env bash
#
# Builds the fonts in a copy of this repository on the WSL Linux filesystem,
# which is much faster than building on a Windows drive under /mnt, then
# copies the results back here.
#
# Usage, from WSL in the repository folder:
#   ./build-wsl.sh              # make build
#   ./build-wsl.sh test proof   # any make targets
#
# The copy lives in $BUILD_DIR (default: ~/.cache/wsl-build/<repository name>).
# It keeps its own venv and generated sources between runs, so make only
# redoes what changed. build.stamp and the generated sources/*.bdf and
# sources/*.designspace are copied back here; delete one of them here to make
# that step run again, as with make itself.
#
# gftools builder runs ninja with one job per CPU plus two, and a fontmake job
# can take about 3 GB, which runs WSL out of memory on a machine with many
# cores. The build is therefore limited to as many CPUs as the available memory
# allows (ninja's default job count follows the CPU affinity). Set $BUILD_CPUS
# to override.

set -euo pipefail
shopt -s nullglob

if [ "$(uname -s)" != "Linux" ]; then
    echo "Run this script from WSL, for example: wsl ./build-wsl.sh" >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-$HOME/.cache/wsl-build/$(basename "$REPO_DIR")}"

TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then
    TARGETS=(build)
fi

start=$(date +%s)

mkdir -p "$BUILD_DIR"

# make's state files (build.stamp and the generated sources) are copied back
# after each build. One missing here was deleted to force that step and the
# ones after it, so delete it in the build copy too.
for state_file in "$BUILD_DIR"/build.stamp "$BUILD_DIR"/sources/*.bdf "$BUILD_DIR"/sources/*.designspace; do
    relative_path="${state_file#"$BUILD_DIR"/}"
    if [ -e "$state_file" ] && [ ! -e "$REPO_DIR/$relative_path" ]; then
        echo "Removing $relative_path from the build copy"
        rm -f "$state_file"
    fi
done

# Copy the inputs. Generated files are excluded, so --delete leaves them in
# place in the build copy and make can tell what is out of date.
echo "Syncing $REPO_DIR -> $BUILD_DIR"
rsync -a --delete \
    --exclude=/.git \
    --exclude=/venv \
    --exclude=/venv-test \
    --exclude=/fonts \
    --exclude=/out \
    --exclude=/proof \
    --exclude=/build.stamp \
    --exclude=/build-wsl.sh \
    --exclude=/out.log \
    --exclude='/sources/*.bdf' \
    --exclude='/sources/*.ufo' \
    --exclude='/sources/*.designspace' \
    --exclude=instance_ufos \
    --exclude=build.ninja \
    --exclude='.ninja*' \
    --exclude=__pycache__ \
    --exclude='*.pyc' \
    "$REPO_DIR/" "$BUILD_DIR/"

if [ -z "${BUILD_CPUS:-}" ]; then
    available_mb=$(awk '/MemAvailable/ { print int($2 / 1024) }' /proc/meminfo)
    BUILD_CPUS=$(( available_mb / 3000 - 2 ))
fi
if [ "$BUILD_CPUS" -lt 1 ]; then
    BUILD_CPUS=1
fi
if [ "$BUILD_CPUS" -gt "$(nproc)" ]; then
    BUILD_CPUS=$(nproc)
fi

echo "Running make ${TARGETS[*]} in $BUILD_DIR on $BUILD_CPUS CPUs"
taskset -c "0-$(( BUILD_CPUS - 1 ))" make -C "$BUILD_DIR" "${TARGETS[@]}"

# Copy the results back: the fonts (make build recreates the folder), make's
# state files with their times, the glyph viewer page, reports and specimen
# images (build-specimen.py writes them next to itself, whatever make's target
# name says)
echo "Copying results back to $REPO_DIR"
if [ -d "$BUILD_DIR/fonts" ]; then
    rsync -a --delete "$BUILD_DIR/fonts/" "$REPO_DIR/fonts/"
fi
if [ -e "$BUILD_DIR/build.stamp" ]; then
    rsync -a "$BUILD_DIR/build.stamp" "$REPO_DIR/"
fi
source_files=("$BUILD_DIR"/sources/*.bdf "$BUILD_DIR"/sources/*.designspace)
if [ ${#source_files[@]} -gt 0 ]; then
    rsync -a "${source_files[@]}" "$REPO_DIR/sources/"
fi
if [ -e "$BUILD_DIR/index.html" ]; then
    rsync -a "$BUILD_DIR/index.html" "$REPO_DIR/"
fi
if [ -d "$BUILD_DIR/out" ]; then
    rsync -a "$BUILD_DIR/out/" "$REPO_DIR/out/"
fi
if [ -d "$BUILD_DIR/documentation" ]; then
    rsync -a --update --exclude='*.py' --exclude=__pycache__ \
        "$BUILD_DIR/documentation/" "$REPO_DIR/documentation/"
fi

echo "Done in $(( $(date +%s) - start )) s"
