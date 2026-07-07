# Testing

Three tiers, fastest first. Plain `pytest` runs only the unit tier; the container tiers are opt-in
via markers and skip automatically when podman is unavailable.

## 1. Unit / component (default, no containers)

```bash
pytest                                             # ~540 tests, ~1.5s
pytest --cov=src/enocean2mqtt --cov-report=term-missing   # enforces the 90% floor
```

Covers the protocol/EEP engine, decode/encode, the daemon run loop (reconnect backoff, sensor
matching, learn-filtering, UTE/base-id), the HA overlay (discovery sync, LEARN/teach-in, cover),
the sqlite store, transport `connect()` paths, config loading, and the
`Sensor` value object. Coverage is enforced (`fail_under = 90`) only when run with `--cov`.

## 2. Container integration (`-m integration`, needs podman)

```bash
pytest -m integration          # ~20s after the first image build
```

Stands up the **real stack** with podman and tears it down after:

- **mosquitto** — the MQTT broker.
- **ser2net/ESP3 emulator** (`tests/integration/emulator.py`) — a fake Raspberry-Pi ser2net endpoint
  over raw TCP. It answers the base-id handshake, replays captured telegrams as ESP3 frames, and
  captures every frame the daemon transmits. This is exactly the user's Pi-hosts-the-USB-stick
  topology (`Ser2netLink` over TCP).
- **daemon** — the `enocean2mqtt` package (same code as the add-on) on a plain `python:3.12-slim`
  base (`tests/integration/Dockerfile`), run via its console script.

Asserts, over the wire: the bridge announces `online`, HA MQTT-discovery configs are published, a
replayed telegram becomes an MQTT state publish, and an inbound `req/send` command produces the
expected ESP3 frame on the transceiver link.

**Resilience** (`test_resilience.py`) injects failures by stopping/restarting containers and asserts
the daemon self-heals:

- *Network failure — transceiver*: restart the emulator (the Pi/ser2net link drops and returns) →
  the daemon reconnects, re-runs the base-id handshake, and resumes decoding.
- *Network failure — broker*: restart mosquitto → the daemon reconnects and re-announces `online`.
- *Power failure — add-on/host*: restart the daemon container → it reloads `devices.yaml`,
  reconnects to both broker and transceiver, resumes publishing, and its sqlite state (on `/data`)
  survives (cover positions / discovery bookkeeping intact).

> The shipped add-on image (`addon/Dockerfile`) uses the Home Assistant Alpine base, which isn't
> pullable without ghcr auth. The tests drive the daemon via its console script (bashio/run.sh
> aren't exercised), so the base image is irrelevant to what's verified — the daemon package is
> identical.

## 3. Full Home Assistant (`-m ha`, needs podman; slow)

```bash
pytest -m ha                   # ~1-2 min (boots a real HA container)
```

The integration stack **plus a real Home Assistant container**, pre-seeded with an MQTT config entry
pointing at the broker so it auto-connects and ingests the daemon's discovery. Asserts HA actually
registered the resulting entities (read from the mounted `.storage/core.entity_registry` — no API
auth needed). HA is pinned to a known version; the pre-seeded storage schema is version-sensitive,
so treat this tier as best-effort and bump `HA_IMAGE` in `test_home_assistant.py` when upgrading.

## Add-on image build (local — no HA rebuild)

The pytest tiers exercise the *daemon*; this checks the *add-on image* builds and starts, so you catch
Dockerfile/dependency/base-image problems locally instead of rebuilding in Home Assistant and reading
the Supervisor log.

```bash
brew install colima docker docker-buildx      # one-time (macOS)
# link buildx as a docker CLI plugin (brew installs the binary but doesn't wire it):
mkdir -p ~/.docker/cli-plugins && \
  ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
colima start                                  # start a Docker-compatible daemon (installs QEMU/binfmt)
tools/test-build.sh                           # build + smoke-test amd64 AND aarch64
tools/test-build.sh aarch64                   # just one arch (native = fastest on Apple Silicon)
```

`tools/test-build.sh` builds `addon/Dockerfile` for each shipped arch (bases mirror `addon/build.yaml`)
and runs `enocean2mqtt --help` in the result — validating the base-python image, the frozen PyPI
dependency install, the package build, and the entrypoint. It mirrors the CI `addon-build` matrix, so
green locally ⇒ green in CI.

One caveat: the HA Supervisor injects its own musllinux wheel index *above* PyPI at build time, which a
plain local build does not reproduce. The Dockerfile uses `uv … --index-strategy unsafe-best-match`, which
resolves correctly with or without that index, so a green local build is a strong signal — but the
Supervisor rebuild stays the final check for that one wrinkle.

## Notes

- **podman on macOS**: the tests resolve the podman binary even when it's off `PATH`, and place the
  per-test workspace under the repo (only `$HOME` is mounted into the podman VM).
- **No live hardware**: the emulator stands in for the EnOcean stick and the Pi; no real actuators
  are driven. To point at real hardware, run the add-on with the `device` option set to the stick or
  `tcp` set to the Pi's `host:port` — a manual smoke, not part of the automated suite.

## CI & releases (GitHub)

- **On every push/PR** (`.github/workflows/ci.yml`): ruff + mypy + pytest (with the 90% coverage gate)
  on Python 3.12/3.13, shellcheck + bats, AppArmor + Dockerfile + add-on-config lint, and a native image
  build + `enocean2mqtt --help` smoke on **both** arches (amd64 on `ubuntu-latest`, aarch64 on the free
  public `ubuntu-24.04-arm` runner). `.github/workflows/codeql.yml` runs CodeQL; Dependabot keeps Actions
  + Python deps current.
- **On a published release** (`.github/workflows/release.yml`): the tag must be `v<x.y.z>` matching
  `addon/config.yaml` `version`; it then builds each arch natively, pushes
  `ghcr.io/t-ice/{arch}-enocean-mqtt-ha:<version>` (+ `latest`) to GHCR, and attaches a signed
  build-provenance attestation. Auth is the built-in `GITHUB_TOKEN` — no secrets needed.
- **Cut a release**: bump `addon/config.yaml` `version` + add a `CHANGELOG` entry, commit, then create a
  GitHub Release tagged `v<x.y.z>`. Once images are published, set `image:` in `config.yaml` so store
  installs pull the prebuilt image instead of building on-device.
