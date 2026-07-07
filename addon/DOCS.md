# EnOcean MQTT for Home Assistant

Bridges an EnOcean transceiver to Home Assistant via MQTT Discovery — the whole EEP range, with
**first-class Eltako support** (FSR14, FSB14, FUD14, …). New here? See the
[Wiki](https://github.com/t-ice/enocean-mqtt-ha/wiki) — step-by-step setup, Eltako pairing,
configuration, examples and troubleshooting.

## Configuration

| Option | Required | Description |
|---|---|---|
| `device` | one of two | Local EnOcean USB stick's serial path (e.g. `/dev/ttyUSB0`), for a stick plugged into the HA machine. The add-on lists the available serial devices in its startup log — copy the right one. Opened at a fixed **57600 baud, 8N1** (the USB300 / FAM-USB / FT232R standard); not configurable. Leave empty when using `tcp`. |
| `tcp` | one of two | Remote transceiver over ser2net as `host:port` (e.g. `192.168.10.31:3000`) — for a stick on a Raspberry Pi. Connected natively (no socat). If both are set, TCP wins. |
| `device_file` | yes | Path to your device list. Default `/config/enocean2mqtt/devices.yaml`. |
| `send_interval_ms` | no | Min ms between transmitted telegrams so command bursts aren't dropped. Default `100`; `0` disables. |
| `log_file` | no | Daemon log path. Default `/config/enocean2mqtt/enocean2mqtt.log`. |
| `log_level` | no | `error`, `warning`, `info` (default) or `debug`. `debug` also logs every raw telegram. |
| `repeater` | no | Transceiver repeater: `off` (default), or level `1`/`2` to re-broadcast telegrams for extra range. Applied at startup; the active level shows as a diagnostic sensor. |
| `secure_psk` | no (advanced) | Pre-shared key (32 hex chars) for decrypting a device's PSK-protected secure teach-in. |
| `mqtt_host` / `mqtt_port` / `mqtt_user` / `mqtt_pwd` | no (advanced) | Explicit broker settings. Leave unset to auto-use the Supervisor `mqtt` service. |
| `mqtt_ssl` / `mqtt_ssl_ca_certs` / `mqtt_ssl_certfile` / `mqtt_ssl_keyfile` / `mqtt_ssl_insecure` | no (advanced) | TLS to the broker. Set `mqtt_ssl` true; give the CA (and, for mutual TLS, client cert/key) as paths under `/ssl` or `/config`. `mqtt_ssl_insecure` skips cert verification (testing only). |

> **Device not decoded or mapped?** Please [open a device support request](https://github.com/t-ice/enocean-mqtt-ha/issues/new/choose)
> so it's added to the shipped catalog and everyone benefits.

### Device list format

`device_file` points at a **`devices.yaml`** — a device needs only `name` + `address` + (`eep`
**or** `model`); `rorg`/`func`/`type`, command encodings and entity types are resolved from the EEP
string or the Eltako catalog. See `devices.yaml.sample`.

### Remote transceiver (Raspberry Pi + USB stick)

Run `ser2net` on the Pi that holds the EnOcean USB stick and point the `tcp` option at it
(`<pi-ip>:3000`). See the [Raspberry Pi transceiver](https://github.com/t-ice/enocean-mqtt-ha/wiki/Raspberry-Pi-Transceiver)
wiki page for a ready-made ser2net + systemd + udev setup (`pi/install.sh`).

## Teach-in & secure devices

Turn on the **LEARN** switch (published by the add-on) to accept teach-ins; it auto-disables after
5 minutes. A **UTE** device (e.g. NodOn/D2-05 blinds) and a **secure** device (`SEC_TI`, e.g. a PTM
switch) are then auto-provisioned — synthesized from the teach-in, published via MQTT discovery, and
appended to your `devices.yaml` (comments preserved). Plain RPS rockers / 1BS contacts carry no EEP,
so add those by hand.

Secure (AES/VAES) devices can also be configured manually in `devices.yaml` with `security: true` +
`key:` (32 hex), and optionally `rlc:` / `slf:` (defaults to `0x8B`) and `key_snd:` / `rlc_snd:` for
secure transmit. If a device sends a **PSK-encrypted** teach-in, set the `secure_psk` option.

## Diagnostics

The bridge device exposes the transceiver's firmware/chip-id, repeater level, available TX
duty-cycle %, and a transmit-failures counter as diagnostic sensors, plus `bridge/state` (online/
offline) and `bridge/stats` (uptime, Base ID, reconnects).

> **Chip ID vs Base ID — they are not the same.** The **Chip ID** is the transceiver's immutable,
> unique factory identity (shown as `chip-id`). The **Base ID** is a *separate*, (re-)writable address
> range the stick may **transmit** from — its Base ID plus an offset of 1–127 (128 addresses total).
> A device's `sender` is always **Base ID + offset**; it is never the Chip ID, never the actuator's own
> address, and never the ID a wall switch broadcasts. When you pair an actuator you teach it that
> `sender` address to obey.

## MQTT topics & payloads

You normally never touch these — Home Assistant entities are created automatically via MQTT discovery
(`homeassistant/<component>/…/config`). They're here for templating or driving a device from your own
automations. The base prefix is `enocean2mqtt/`.

| Topic | Direction | Content |
|---|---|---|
| `enocean2mqtt/<device>` | ← state | Decoded telegram as one **retained JSON** object; read fields with `value_json.<FIELD>`. Also carries `_RSSI_` and `_DATE_`. |
| `enocean2mqtt/<device>/req/<FIELD>` | → command | Set one field of the next telegram to send. |
| `enocean2mqtt/<device>/req/send` | → command | Transmit (`send` value e.g. `clear` / `clear+raw_data`). You can also publish one JSON to `enocean2mqtt/<device>/req` that includes a `"send"` key. |
| `enocean2mqtt/bridge/state` | ← state | Bridge availability, `online` / `offline` (LWT). |
| `enocean2mqtt/bridge/stats` | ← state | JSON diagnostics: uptime, Base ID, firmware, telegrams/min, reconnects, … |
| `enocean2mqtt/__system/learn` | ←/→ | LEARN switch state; publish to `enocean2mqtt/__system/learn/req` to toggle it. |

`<device>` is the `name` from your `devices.yaml`. Per-device state is published as **retained JSON**
by default (`publish_json`, forced on in the add-on so discovery templates work). Set `publish_json:
false` on a device **only** if you consume MQTT yourself and prefer one scalar per topic
(`enocean2mqtt/<device>/<FIELD>`) — that breaks the auto-created HA entities.

## Security (AppArmor)

The add-on ships an AppArmor profile (`apparmor.txt`) that the Supervisor enforces on the container —
defense-in-depth confining it to what it actually needs (the EnOcean serial device, MQTT/ser2net
network, `/config` + `/data`). If a future base-image change ever causes an AppArmor denial that
blocks startup, you can toggle **Protection mode** off for the add-on (its info page) as a stopgap
while the profile is updated — note the standard warning that this removes the confinement.
