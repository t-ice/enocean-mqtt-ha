# Architecture

`enocean-mqtt-ha` is an MQTT-bridge add-on: it reads EnOcean telegrams from a transceiver,
decodes them via EEP profiles, and publishes to Home Assistant using MQTT Discovery. It is **not**
a native HA integration.

## Components (one repo, one wheel — ports & adapters)

The daemon is a **hexagonal (ports-and-adapters)** application: the domain + application core depend
only on abstract *ports*; concrete I/O lives in *adapters*, so the transceiver, MQTT bus and store are
each swappable without touching the core.

![Architecture data flow: the EnOcean USB stick connects (serial or ser2net TCP) to the adapters
layer; the application layer decodes/encodes telegrams using the protocol (ESP3 + EEP) engine and the
homeassistant bridge; state is published as JSON + discovery to the MQTT broker and on to Home
Assistant, and command topics flow back the other way.](img/architecture.png)

<!-- Diagram source: img/architecture.svg — regenerate all diagrams with docs/img/render.sh -->


- **`protocol/`** — the EnOcean protocol library (MIT; see Credits / `THIRD-PARTY-LICENSES.md`): ESP3
  framing (`packet.py`, `crc8.py`, `constants.py`, `utils.py`) and the code-defined EEP decode/encode
  engine (`eep_codec.py`, `profiles/engine.py` + a hand-maintained `PROFILES` registry — no XML at runtime).
- **`domain/`** — pure value objects: `Sensor` (a device + its per-send scratch) and `Config`.
- **`ports/`** — the Protocols the application depends on: `TransceiverPort`, `MessageBusPort`,
  `DeviceStorePort`.
- **`adapters/`** — concrete I/O implementing the ports: `transceiver/` (`SerialLink` via
  pyserial-asyncio, `Ser2netLink` via `asyncio.open_connection`, over a shared ESP3 framing base;
  `factory.py` chooses by the `enocean_port` value (serial path vs `host:port`) — **no socat**),
  `mqtt/aiomqtt_bus.py`, `store/sqlite_store.py`.
- **`application/`** — orchestration on one asyncio loop: `daemon.py` (`EnoceanDaemon`, the run loop with
  reconnect/backoff), `bootstrap.py` (composition root), and `decoder`/`encoder`/`publisher`/`inbound`.
- **`homeassistant/`** — the HA overlay: `ha_bridge.py` (`HomeAssistantBridge`), `discovery/`
  (MQTT-discovery payloads + per-device config), `mapping/` (the code-defined `MAPPING`),
  `sensor_expander.py`, `cover.py` (absolute-position maths).
- **`cli.py`** — entry point (`enocean2mqtt` console script); **`devices.py`** — devices.yaml loader;
  **`transport.py`** — connection-string helpers.
- **`addon/`** — the HA add-on (Dockerfile, config.yaml, run.sh, AppArmor, translations, docs).
- **`catalog/`** — the Eltako device catalog, validated against `MAPPING` by `tests/test_catalog.py`
  ([`coverage.md`](coverage.md) is a static snapshot of catalogued Eltako coverage).
- **`pi/`** — Raspberry Pi transceiver setup. See the [Raspberry Pi transceiver](https://github.com/t-ice/enocean-mqtt-ha/wiki/Raspberry-Pi-Transceiver) wiki page.

## Data flow

1. `run.sh` generates `/data/enocean2mqtt.conf` (`[CONFIG]`) from the add-on options — resolving the
   `device`/`tcp` options into the transceiver `enocean_port` (TCP wins if both set); MQTT creds come
   from the Supervisor `mqtt` service unless overridden; the device list is `devices.yaml` (passed as
   a separate arg). It then `exec`s the daemon — no restart loop, because the daemon self-heals
   connection drops.
2. The daemon runs one asyncio loop that connects to the transceiver (serial or ser2net TCP, one
   framing base — no socat) and the broker; on first connect it publishes retained MQTT-discovery
   configs for every device and marks the bridge `online`. A dropped transceiver or broker reconnects
   with exponential backoff. At startup it also reads the stick's firmware/chip-id, repeater level and
   TX duty-cycle via ESP3 common commands and publishes them as diagnostics.
3. Incoming telegrams are decoded per EEP and published as JSON; FSB covers get a persisted `POS`, and
   secure devices persist their rolling code (RLC) so they survive a restart.
4. HA command topics (`<device>/req/…`) are translated back into EnOcean telegrams (Eltako A5-38-08,
   D2-01/D2-05, F6 rocker), secure-wrapped (VAES + CMAC) for a `security:` device.

## Key design decisions

- Single wheel, one import namespace (`enocean2mqtt`, with the folded `enocean2mqtt.protocol` lib).
- Asyncio I/O core (single event loop, `aiomqtt` + async serial/TCP) — reconnect/backoff is
  first-class, so there is no external supervision loop.
- Reproducible image via `uv sync --frozen` from `uv.lock`; no build-time `git clone`/`cp` overlay.
- Slug is `enocean_mqtt_ha`.
