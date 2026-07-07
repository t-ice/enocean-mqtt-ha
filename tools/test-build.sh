#!/usr/bin/env bash
# Local add-on build test — reproduces the HA Supervisor image build so build/install/startup errors are
# caught locally in ~1-2 min instead of via a rebuild-in-HA round-trip.
#
# Requires a Docker-compatible engine. With Colima:  colima start   (then re-run this).
#
# Usage:
#   tools/test-build.sh            # build + smoke-test both shipped arches (amd64, aarch64)
#   tools/test-build.sh aarch64    # just one arch (native = fastest on Apple Silicon)
#
# What it validates: the base-python image, the frozen PyPI dependency install, the package build, and
# that the `enocean2mqtt` entrypoint imports and runs. Bases mirror addon/build.yaml.
#
# LIMITATION: a plain local build resolves against PyPI only — the HA Supervisor injects its own musllinux
# wheel index above PyPI, which this does not reproduce. Our Dockerfile uses
# `--index-strategy unsafe-best-match`, which resolves correctly with or without that index, so a green
# build here is a strong signal; the Supervisor rebuild remains the final check for that one wrinkle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

base_for() {
  case "$1" in
    amd64)   echo "linux/amd64 ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.24" ;;
    aarch64) echo "linux/arm64 ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.24" ;;
    *) echo "unknown arch: $1 (expected amd64 or aarch64)" >&2; return 1 ;;
  esac
}

if ! docker info >/dev/null 2>&1; then
  echo "No Docker daemon reachable. Start one first, e.g.:  colima start" >&2
  exit 1
fi

arches=("$@")
[ "${#arches[@]}" -eq 0 ] && arches=(amd64 aarch64)

for arch in "${arches[@]}"; do
  read -r platform base <<<"$(base_for "$arch")"
  tag="enocean2mqtt:test-${arch}"
  echo "==> build ${arch} (${platform}) FROM ${base}"
  # Plain buildkit build (no buildx plugin needed); loads into the local image store automatically.
  # Cross-arch (amd64 on an arm64 host) uses QEMU/binfmt.
  DOCKER_BUILDKIT=1 docker build --platform "$platform" \
    --build-arg BUILD_FROM="$base" \
    -f addon/Dockerfile -t "$tag" .
  echo "==> smoke-test entrypoint: ${tag}"
  docker run --rm "$tag" enocean2mqtt --help >/dev/null
  echo "==> OK ${arch}"
  echo
done

echo "Build + smoke-test passed for: ${arches[*]}"
