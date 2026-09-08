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
#
# The two base-image lines are READ OUT of addon/Dockerfile instead of repeated here. Dependabot
# bumps the uv pin there (docker ecosystem, /addon) and the HA base image is bumped by hand — and
# neither can see this heredoc, so copies drift silently: the uv pin sat on 0.11.27 while the
# published image already built with 0.12.10.
ARG_LINE="$(sed -nE 's|^(ARG BUILD_FROM=.+)$|\1|p' "$ROOT/addon/Dockerfile" | head -1)"
UV_LINE="$(sed -nE 's|^(FROM ghcr\.io/astral-sh/uv:.+ AS uv)$|\1|p' "$ROOT/addon/Dockerfile" | head -1)"
if [ -z "$ARG_LINE" ] || [ -z "$UV_LINE" ]; then
  echo "package-addon.sh: cannot read the ARG BUILD_FROM / uv builder lines from addon/Dockerfile" >&2
  exit 1
fi

{
printf '%s\n%s\n' "$ARG_LINE" "$UV_LINE"
cat <<'DOCKER'
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
# Healthcheck: the daemon process must be alive. Exec form (DL3025); the bracket in '[e]nocean2mqtt'
# keeps the check from matching its own `sh -c pgrep -f …` command line. Keep in step with
# addon/Dockerfile — a local Supervisor build should report health like the published image does.
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["/bin/sh", "-c", "pgrep -f '[e]nocean2mqtt' >/dev/null 2>&1"]
CMD [ "/run.sh" ]
DOCKER
} > "$OUT/Dockerfile"

echo "Staged self-contained add-on in: $OUT"
