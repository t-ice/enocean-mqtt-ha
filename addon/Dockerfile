# EnOcean-MQTT-Eltako add-on image.
#
# IMPORTANT: build with the REPOSITORY ROOT as context (the package lives in ../src):
#   podman build -f addon/Dockerfile -t enocean-mqtt-ha:dev .
# The HA Supervisor build is wired up via addon/build.yaml + tools/package-addon.sh.
#
# The daemon is installed as a single wheel and connects to ser2net over TCP natively.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.24
FROM ghcr.io/astral-sh/uv:0.11.28 AS uv
FROM ${BUILD_FROM}

LABEL org.opencontainers.image.title="EnOcean MQTT for Home Assistant" \
      org.opencontainers.image.description="EnOcean to MQTT bridge for Home Assistant (whole EEP range; first-class Eltako support)" \
      org.opencontainers.image.source="https://github.com/t-ice/enocean-mqtt-ha" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

# uv gives us reproducible, frozen installs from uv.lock.
COPY --from=uv /uv /usr/local/bin/uv

# Install into the Python the base-python image already provides at /usr/local (built from source,
# HA-patched, pip included, no PEP 668 EXTERNALLY-MANAGED marker) — so we reuse the image's interpreter
# rather than apk-adding our own, and no venv/override is needed. Reproducibility comes from uv.lock.
ENV UV_PYTHON=python3 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# Install from PyPI (our uv.lock is resolved + hash-pinned against it). The HA Supervisor injects its
# musllinux wheel index above PyPI at build time; that index only carries wheels for HA's current Python
# (cp313/cp314) and lacks our cp312 pins, so uv's default first-match resolve fails there. --index-strategy
# unsafe-best-match makes uv consider all indexes and pick the cp312 wheel from PyPI (safe: every dep is
# hash-pinned from the lock). Our deps need no compilation (pure-Python + pyyaml musllinux wheels).
ENV UV_INDEX_URL=https://pypi.org/simple/
WORKDIR /src
# Dependency layer first (depends only on the lockfile) so editing src/ doesn't rebuild it.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
 && uv pip install --system --index-url https://pypi.org/simple/ --index-strategy unsafe-best-match \
      --no-deps -r /tmp/requirements.txt
# Then the package itself.
COPY README.md LICENSE ./
COPY src ./src
RUN uv pip install --system --index-url https://pypi.org/simple/ --index-strategy unsafe-best-match \
      --no-deps . \
 && rm -rf /src /tmp/requirements.txt /usr/local/bin/uv
WORKDIR /

# Add-on runtime files.
COPY addon/run.sh /run.sh
RUN chmod a+x /run.sh

# Healthcheck: the daemon process must be alive (busybox pgrep ships in the HA base image).
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f enocean2mqtt >/dev/null 2>&1 || exit 1

CMD [ "/run.sh" ]
