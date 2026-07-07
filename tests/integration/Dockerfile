# Integration-test image: the SAME daemon package as the add-on, on a plain, pullable base.
#
# The shipped add-on image (addon/Dockerfile) uses the Home Assistant Alpine base, which isn't
# pullable without auth on ghcr. The integration tests drive the daemon via its console script
# directly (bashio/run.sh aren't exercised), so the base image is irrelevant to what's tested — we
# install the identical `enocean2mqtt` package here and get the same `enocean2mqtt` entry point.
FROM docker.io/library/python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# Both the daemon (`enocean2mqtt …`) and the emulator (`python /emulator.py`) run from this image.
CMD ["enocean2mqtt", "--help"]
