# Contributing

Thanks for helping improve **EnOcean MQTT for Home Assistant**! This guide covers the workflow; the
full coding standards live in **[`STYLEGUIDE.md`](STYLEGUIDE.md)**, and the branching & release flow
(GitHub Flow) in **[`docs/development.md`](docs/development.md)**.

## Development setup

```bash
uv sync --extra dev            # or: pip install -e ".[dev]"
pre-commit install             # runs the styleguide checks on every commit
```

## Before you open a pull request

Everything below is enforced by CI (`.github/workflows/ci.yml`) — run it locally first:

```bash
ruff check . && ruff format --check src/enocean2mqtt tests tools   # lint + format
uv run mypy                                                        # type-check
uv run pytest -q                                                   # unit/component suite
```

- **Keep the coverage floor at 90%** (`pytest --cov=src/enocean2mqtt --cov-report=term-missing`).
- **Add a test first** for any risky path. The byte-exact actuator tests
  (`tests/daemon/test_send_encode.py`, `tests/ha/test_cover_command.py`) must not change without a
  clear reason.
- **Respect the layering** (ports-and-adapters): put I/O behind an adapter and depend on the port;
  keep the domain pure. See [`docs/architecture.md`](docs/architecture.md).
- **EEP/profile + HA-mapping data** is hand-maintained source under `protocol/profiles/eep/` and
  `homeassistant/mapping/eep/` — edit these fragment files directly (no XML is parsed at runtime).
- **Do not vendor EnOcean Alliance PDFs/spec text** — only derived Python + numeric certification
  vectors.

Heavier test tiers (optional locally; need podman) are documented in
[`docs/testing.md`](docs/testing.md):

```bash
pytest -m integration          # mosquitto + ser2net/ESP3 emulator + the daemon
pytest -m ha                   # + a real Home Assistant container (slow)
tools/test-build.sh            # build + smoke-test the add-on image (amd64 / aarch64)
```

## Commits & pull requests

- Focused commits with an **imperative subject**; the body explains the *why*, not the *what*.
- Match the surrounding style (100-column lines, type hints, docstrings that say why).
- If your change is user-visible, add a note to **`addon/CHANGELOG.md`** under the next version.

## Adding a device / fixing a decode

The fastest way to get a device supported is a **telegram capture**: set `log_level: debug`, trigger
the device, and attach the `received:` / `_RAW_DATA_` lines to a
[device support request](https://github.com/t-ice/enocean-mqtt-ha/issues/new/choose) along with the
manufacturer, model, and EEP if known — new device support is added centrally so everyone benefits.

## Dependencies & keeping them updated

Runtime deps live in `pyproject.toml` (`aiomqtt`, `pyyaml`, `pyserial`, `pyserial-asyncio`; paho-mqtt
comes in transitively via aiomqtt), pinned to major-version ranges and frozen in `uv.lock`. Dev tools
(pytest, ruff, mypy, yamllint, …) are the `dev` optional group. The build uses `uv` (pinned in
`addon/Dockerfile`) on top of Home Assistant's `base-python` image (`addon/build.yaml`).

**Dependabot** (`.github/dependabot.yml`) keeps them current, weekly:

- **`uv`** — bumps `pyproject.toml` and relocks `uv.lock` in one PR (so the `--frozen` CI install stays green);
- **`github-actions`** — the actions used in `.github/workflows/`;
- **`docker`** — the pinned `uv` builder image in `addon/Dockerfile`.

The **one manual bump** is the HA base image (`ghcr.io/home-assistant/*-base-python:3.12-alpine3.24`):
it's referenced via `ARG BUILD_FROM`, not a `FROM` literal, so Dependabot can't see it. When Home
Assistant ships a newer base-python, update the tag in `addon/build.yaml` **and** the `ARG BUILD_FROM`
default in `addon/Dockerfile` together.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
