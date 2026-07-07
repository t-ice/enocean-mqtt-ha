# EnOcean MQTT for Home Assistant

[![CI](https://github.com/t-ice/enocean-mqtt-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/t-ice/enocean-mqtt-ha/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/t-ice/enocean-mqtt-ha?sort=semver)](https://github.com/t-ice/enocean-mqtt-ha/releases)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
![Architectures: aarch64 & amd64](https://img.shields.io/badge/arch-aarch64%20%7C%20amd64-informational)

A Home Assistant add-on that bridges **EnOcean** devices to **MQTT** — decoding the whole EnOcean
Equipment Profile (EEP) range (RPS `F6`, 1BS `D5`, 4BS `A5`, VLD `D2`) with a code-defined engine
validated against the official EnOcean certification vectors, and auto-creating entities via MQTT
discovery.

It talks to the transceiver over a **local USB stick** (`/dev/ttyUSB0`) or a **remote ser2net**
endpoint over TCP (e.g. a Raspberry Pi hosting the stick).

> ### ★ First-class Eltako support
> Beyond generic EnOcean, this add-on has a built-in **Eltako** catalog: one-line
> `model: eltako/…` entries for FSR14 relays/lights, FUD14 dimmers, FSB14 blinds/covers (with
> **cover-position tracking that survives restarts**) and their Series-61/TF61 siblings — no
> hand-written EEP templates. See **[Supported Eltako devices](#supported-eltako-devices)**.

> **New here?** Start with the **[Wiki](https://github.com/t-ice/enocean-mqtt-ha/wiki)** — a
> step-by-step [Getting Started](https://github.com/t-ice/enocean-mqtt-ha/wiki/Getting-Started) guide
> for non-technicians, plus configuration, Eltako setup, examples and troubleshooting.

> Consolidates and builds on four upstream projects; see the Credits and License sections below for
> attribution.

## Features

- **Decodes the whole EnOcean RORG range** (RPS `F6`, 1BS `D5`, 4BS `A5`, VLD `D2`) from a
  **code-defined EEP engine** (`protocol/profiles`) — no XML parsed at runtime — validated ≥95%
  against the official EnOcean certification test vectors.
- **Eltako actuators**: FSR14 lights and FSB14 blinds/covers, including **cover-position tracking
  that survives restarts** (persisted in SQLite).
- **Home Assistant MQTT discovery**: sensors, binary sensors, covers, switches auto-appear; every
  decodable profile is mapped (hand-curated where it matters, code-defined for the rest).
- **Local serial or remote ser2net (TCP)** transceiver — no `socat`/PTY bridge; the daemon self-heals
  connection drops (exponential-backoff reconnect for both the transceiver and MQTT).
- **Transmit / control**, not just decode: Eltako A5-38-08 switch/light + A5-3F-7F covers, D2-05
  blinds, D2-01 relays/dimmers, and F6 rocker emulation (incl. one-click AI/AO/BI/BO press buttons).
- **Secure telegrams (AES/VAES)** per *Security of EnOcean Radio Networks v3.02*: decode, teach-in
  (incl. the PSK path), transmit, and rolling-code (RLC) replay protection that **survives restarts**.
- **Teach-in auto-provisioning** via a Home Assistant LEARN button (auto-off timeout for safety):
  UTE and secure devices are added to `devices.yaml` hands-free (comments/formatting preserved).
- **Transceiver diagnostics**: firmware/chip-id, repeater level, available TX duty-cycle % and a
  transmit-failures counter, read from the stick and published as diagnostic sensors.
- **Availability (LWT)**, RSSI and last-seen per device, optional flat or JSON payloads.
- **YAML device list** with load-time validation.

## How it works — architecture

The code is organised as a **ports-and-adapters (hexagonal)** application; dependencies point inward
(adapters know the domain; the application depends only on ports; the domain has no I/O).

![Data flow: the EnOcean USB stick connects over serial or ser2net TCP to the transceiver adapter; the
application core decodes/encodes telegrams with the ESP3 + EEP engine; the HA bridge maps them and
publishes state and discovery to the MQTT broker and on to Home Assistant, with commands flowing back
the other way.](docs/img/architecture.png)

| Layer | What lives there |
|---|---|
| `domain/` | Sensor value object + the EnOcean protocol & EEP engine (pure, no I/O) |
| `ports/` | Protocols the application depends on: `TransceiverPort` · `MessageBusPort` · `DeviceStorePort` |
| `adapters/` | Concrete I/O implementing the ports: `SerialLink` / `Ser2netLink` (serial or TCP, one framing base) · `AiomqttBus` (aiomqtt) · `SqliteStore` (device + cover-position persistence) |
| `application/` | Orchestration: the async daemon + encode/decode/publish/inbound routing |
| `homeassistant/` | The HA overlay: MQTT discovery, device mapping, cover math, LEARN button |

Telegram flow: `transceiver → decode (EEP engine) → publish (MQTT)`, and inbound
`MQTT command → encode → transceiver`. A single asyncio event loop runs the transceiver reader and
the MQTT consumer; either side reconnecting does not tear down the other. See
[`docs/architecture.md`](docs/architecture.md), [`docs/spec-compliance.md`](docs/spec-compliance.md)
(the EEP engine) and [`docs/testing.md`](docs/testing.md) (the test tiers).

## Installation (Home Assistant add-on)

[![Add repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ft-ice%2Fenocean-mqtt-ha)

1. Add this repository (click the button above, or **Settings → Add-ons → ⋮ → Repositories** and paste
   the repo URL), then install **EnOcean MQTT for Home Assistant**.
2. Point the add-on at your transceiver with **one of two** options: `device` (the local serial path,
   e.g. `/dev/ttyUSB0` — the add-on lists the available serial devices in its startup log) **or** `tcp`
   (a ser2net endpoint like `192.168.x.y:3000`; TCP wins if both are set). See the
   [Raspberry Pi transceiver guide](https://github.com/t-ice/enocean-mqtt-ha/wiki/Raspberry-Pi-Transceiver)
   for the remote-stick setup.

   ![ser2net topology: the EnOcean USB stick on a Raspberry Pi is exposed by ser2net as a raw TCP port
   :3000; the add-on on the Home Assistant host connects to it over raw TCP on the LAN or VPN.](docs/img/ser2net-topology.png)
3. Provide your device list at `/config/enocean2mqtt/devices.yaml` (see below). MQTT is auto-detected
   from the Supervisor `mqtt` service, or configure a broker explicitly.
4. Start the add-on; entities appear in Home Assistant via MQTT discovery.

## Configuration

Add-on options (Configuration tab):

| Option | Required | Description |
|---|---|---|
| `device` | one of two | Local USB stick's serial path (e.g. `/dev/ttyUSB0`); the startup log lists the available serial devices. |
| `tcp` | one of two | Remote ser2net as `host:port` (e.g. `192.168.x.y:3000`). If both set, TCP wins. |
| `device_file` | yes | Path to the device list (default `/config/enocean2mqtt/devices.yaml`). |
| `repeater` | no | Transceiver repeater: `off` (default), or level `1`/`2` for extra range. |
| `secure_psk` | no | Pre-shared key (32 hex) for decrypting PSK-protected secure teach-ins. |
| `mqtt_host` / `mqtt_port` / `mqtt_user` / `mqtt_pwd` | no | Explicit broker; unset ⇒ Supervisor `mqtt` service. |
| `mqtt_ssl` / `mqtt_ssl_ca_certs` / `mqtt_ssl_certfile` / `mqtt_ssl_keyfile` / `mqtt_ssl_insecure` | no | TLS to the broker. Set `mqtt_ssl` true; give the CA (and, for mutual TLS, client cert/key) as paths under `/ssl` or `/config`. `mqtt_ssl_insecure` skips cert verification (testing only). |
| `log_level` | no | `error`, `warning`, `info` (default) or `debug`. `debug` also logs every raw telegram. |
| `log_file` | no | Daemon log path (default `/config/enocean2mqtt/enocean2mqtt.log`). |
| `send_interval_ms` | no | Min ms between transmitted telegrams so command bursts aren't dropped (default `100` ≈ the EnOcean RX maturity time; `0` disables). |

`devices.yaml` — a device needs `name` + `address` plus **either** an `eep` string **or** a `model`:

```yaml
devices:
  - name: Wetterstation           # EEP-based sensor
    address: 0x059ED79A
    eep: A5-13-01

  - name: Rollo_Wohnzimmer         # Eltako model actuator (needs a unique sender)
    address: 0xFF94CE9C
    model: eltako/fsb14
    sender: 0xFFAE7C81
    shut_time: 64                  # full travel time in seconds (for cover position)
```

## Supported Eltako devices

Set `model: eltako/<name>` for these actuators (all controlled over Eltako's A5-38-08 central command,
with A5-02-01 / A5-3F-7F feedback). Many names are aliases of a base profile — pick whichever matches
your hardware:

| `model: eltako/…` | Aliases (same profile) | HA entity | Notes |
|---|---|---|---|
| `fsr14` | `fsr61`, `f4sr14`, `ftn14`, `fmz14`, `fl62` | switch **+** light | relays / timers |
| `fud14` | `fud61`, `fdg14`, `fsg14`, `fd62`, `tf61d` | dimmable light | dimmers (+ dim speed) |
| `fsb14` | `fsb61`, `fsb61np` | cover | shutter/blind (set `shut_time`) |
| `fj62` | `tf61j` | cover | with end-position sensors |
| `tf61l` | — | switch **+** light | + unlock / feedback buttons |
| `fhd60sb` | — | brightness sensor | A5-06-01 lux |

> A relay actuator (`fsr14` and its aliases, `tf61l`) is published as **both** a `switch` and a
> `light` entity for the same channel — use whichever fits the load; the other can be hidden. Only one
> needs to be controlled, they track the same state.

Anything **not** in this list (other manufacturers, sensors, window handles, weather stations) is
configured by its **EEP** instead of a model — e.g. the Hoppe **FHF** window handle (`eep: F6-10-00`)
and the Eltako **FWG14MS** weather station (`eep: A5-13-01`). The full matrix, pairing steps (PCT14
function groups), and devices still needing test data are in the
[Supported Devices](https://github.com/t-ice/enocean-mqtt-ha/wiki/Supported-Devices) wiki page.

## Testing

Three tiers (details in [`docs/testing.md`](docs/testing.md)):

```bash
pytest                                    # unit/component (~540 tests, coverage floor 90%)
pytest -m integration                     # podman: mosquitto + ser2net/ESP3 emulator + the daemon
pytest -m ha                              # + a real Home Assistant container (slow)
tools/test-build.sh                       # build + smoke-test the add-on image locally (amd64 + aarch64)
```

The integration tier reproduces the ser2net (Raspberry-Pi) topology and includes resilience tests
(transceiver drop, broker drop, add-on power-cycle) asserting the daemon self-heals.

## Contributing

```bash
uv sync --extra dev                       # or: pip install -e ".[dev]"
pre-commit install                        # enforce the styleguide on every commit
pytest                                    # run the unit suite
ruff check . && ruff format --check && mypy   # lint + format + type-check (all must pass)
```

The full style guide (Python, HA YAML, Dockerfile, shell) and its tooling are documented in
[`STYLEGUIDE.md`](STYLEGUIDE.md); `pre-commit run --all-files` checks the whole tree. The
branching & release flow (GitHub Flow) is in [`docs/development.md`](docs/development.md).

- **Every change keeps `ruff`, `mypy`, and `pytest` green**, and the coverage floor at 90%
  (`pytest --cov=src/enocean2mqtt --cov-report=term-missing`).
- **Behaviour-preserving by default** — the byte-exact actuator tests
  (`tests/daemon/test_send_encode.py`, `tests/ha/test_cover_command.py`) must not change without a
  clear reason; add a test first for any risky path.
- **The EEP/profile + HA-mapping data lives as hand-maintained source** under
  `protocol/profiles/eep/` and `homeassistant/mapping/eep/`. Edit these fragment files directly —
  they're big dict literals; keep the shape. No XML is parsed at runtime.
- **Respect the layering** — put I/O behind an adapter and depend on the port; keep the domain pure.
- **Commits**: focused, imperative subject; explain the *why*; match the surrounding style (100-col
  lines, type hints, docstrings that say why not what).
- **Do not vendor EnOcean Alliance PDFs/spec text** — only derived Python + numeric certification
  vectors.

## Reporting issues

Please open an issue with:

1. **What happened vs. what you expected**, and how to reproduce it.
2. **Versions** — add-on version, Home Assistant version, and your transceiver setup (local USB stick
   vs. remote ser2net, and the model if known).
3. **Logs** — the relevant section of `enocean2mqtt.log` with `log_level: debug`. For a decode problem
   `debug` also logs every raw telegram, so include the raw telegram line(s).
4. **Device details** — the EEP (`RORG-FUNC-TYPE`) or Eltako model and the `devices.yaml` entry.
5. For a **decode/encode** issue, the exact EEP and, if possible, the `_RAW_DATA_` the device sent.

Report security-sensitive issues (e.g. broker/LAN exposure) privately rather than in a public issue.

## Credits / Acknowledgements

This project consolidates and builds on the work of these upstream authors — with thanks:

- [`kipe/enocean`](https://github.com/kipe/enocean) — Kimmo Huoman — the EnOcean protocol library
  (MIT) that `src/enocean2mqtt/protocol/` is based on.
- [`mak-gitdev`](https://github.com/mak-gitdev) — Marc Alexandre K. — the `enocean` fork plus the
  `HA_enoceanmqtt` MQTT overlay and `hidden-addon` add-on packaging.
- [`embyt/enocean-mqtt`](https://github.com/embyt/enocean-mqtt) — Roman Morawek / embyt GmbH — the
  original EnOcean↔MQTT daemon core (GPL-3.0).

## License

Copyright © 2024–2026 Christian Theis. **GPLv3** for the combined work (`LICENSE`); the folded
`src/enocean2mqtt/protocol` library retains its **MIT** notice (`src/enocean2mqtt/protocol/LICENSE`).
See [`THIRD-PARTY-LICENSES.md`](THIRD-PARTY-LICENSES.md) for third-party notices.
