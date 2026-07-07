#!/usr/bin/env bash
# Stage a SELF-CONTAINED Home Assistant add-on directory in dist/addon/.
#
# The dev/CI image (addon/Dockerfile) builds with the repo root as context. The HA Supervisor,
# however, builds a *local add-on* with the add-on folder itself as context and cannot reach
# ../src. This script assembles a folder that Supervisor can build directly: it copies the add-on
# files plus the package source + lockfile and writes a context-local Dockerfile.
#
#   tools/package-addon.sh          # -> dist/addon/
# Then copy dist/addon/ into your HA /addons/enocean_mqtt_ha and (re)build in the UI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist/addon"

rm -rf "$OUT"
mkdir -p "$OUT"

# Add-on metadata + runtime.
cp "$ROOT"/addon/{config.yaml,build.yaml,run.sh,apparmor.txt,CHANGELOG.md,DOCS.md} "$OUT/"
cp "$ROOT"/addon/devices.yaml.sample "$OUT/" 2>/dev/null || true
# Add-on icon + logo (HA auto-detects icon.png / logo.png by filename).
cp "$ROOT"/addon/icon.png "$OUT/" 2>/dev/null || true
cp "$ROOT"/addon/logo.png "$OUT/" 2>/dev/null || true
[ -d "$ROOT/addon/translations" ] && cp -R "$ROOT/addon/translations" "$OUT/translations"

# Package source + reproducible lock + license/attribution (ship the third-party notices with the add-on).
cp "$ROOT"/{pyproject.toml,uv.lock,README.md,LICENSE,THIRD-PARTY-LICENSES.md} "$OUT/"
cp -R "$ROOT/src" "$OUT/src"
find "$OUT/src" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Context-local Dockerfile (COPY paths relative to the add-on dir; no ../).
cat > "$OUT/Dockerfile" <<'DOCKER'
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.24
FROM ghcr.io/astral-sh/uv:0.11.27 AS uv
FROM ${BUILD_FROM}
LABEL org.opencontainers.image.title="EnOcean MQTT for Home Assistant" \
      org.opencontainers.image.description="EnOcean to MQTT bridge for Home Assistant (whole EEP range; first-class Eltako support)" \
      org.opencontainers.image.source="https://github.com/t-ice/enocean-mqtt-ha" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
COPY --from=uv /uv /usr/local/bin/uv
# Install into base-python's source-built /usr/local Python (pip present, no PEP 668 marker) — reuse the
# image's interpreter, no apk/venv/override. Install from PyPI (our uv.lock is hash-pinned against it;
# base-python's HA musllinux index lacks our pinned versions for cp312). Reproducible via uv.lock.
ENV UV_PYTHON=python3 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_INDEX_URL=https://pypi.org/simple/
WORKDIR /src
# Dependency layer first (lockfile only) so editing src/ doesn't rebuild it. --index-strategy
# unsafe-best-match: the Supervisor injects HA's wheel index above PyPI, but it lacks our cp312 pins;
# considering all indexes picks the cp312 PyPI wheel (safe — hash-pinned from the lock).
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
 && uv pip install --system --index-url https://pypi.org/simple/ --index-strategy unsafe-best-match \
      --no-deps -r /tmp/requirements.txt
COPY README.md LICENSE ./
COPY src ./src
RUN uv pip install --system --index-url https://pypi.org/simple/ --index-strategy unsafe-best-match \
      --no-deps . \
 && rm -rf /src /tmp/requirements.txt /usr/local/bin/uv
WORKDIR /
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
DOCKER

echo "Staged self-contained add-on in: $OUT"
