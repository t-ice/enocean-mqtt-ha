# Configuration (devices.yaml)

Two things to configure: the **add-on options** (in the HA UI) and your **device list**
(`devices.yaml`).

## Add-on options

Set these on the add-on's **Configuration** tab:

| Option | Required | What it does |
|---|---|---|
| `device` | one of two | Local USB stick's serial path (e.g. `/dev/ttyUSB0`). The startup log lists the available serial devices. Leave empty when using `tcp`. |
| `tcp` | one of two | Remote ser2net as `host:port` (e.g. `192.168.1.50:3000`). If both set, TCP wins. |
| `device_file` | yes | Path to your device list. Default `/config/enocean2mqtt/devices.yaml`. |
| `send_interval_ms` | no | Min ms between transmitted telegrams so command bursts aren't dropped. Default `100`; `0` disables. |
| `repeater` | no | Transceiver repeater: `off` (default), or level `1`/`2` for extra range. |
| `secure_psk` | no | Pre-shared key (32 hex) for decrypting a device's **PSK-protected** secure teach-in. |
| `log_level` | no | `error`, `warning`, `info` (default) or `debug`. `debug` also logs every raw telegram (handy for finding addresses). |
| `log_file` | no | Daemon log path. |
| `mqtt_host` / `mqtt_port` / `mqtt_user` / `mqtt_pwd` | no | Explicit broker; leave **blank** to auto-use the Supervisor `mqtt` service. |
| `mqtt_ssl` / `mqtt_ssl_ca_certs` / `mqtt_ssl_certfile` / `mqtt_ssl_keyfile` / `mqtt_ssl_insecure` | no | TLS to the broker: set `mqtt_ssl` true and give the CA (and client cert/key for mutual TLS) as paths under `/ssl` or `/config`. `mqtt_ssl_insecure` skips verification (testing only). |

> **Device not decoded or mapped?** [Open a device support request](https://github.com/t-ice/enocean-mqtt-ha/issues/new/choose)
> so it's added to the shipped catalog and everyone benefits.

## devices.yaml

Lives at `/config/enocean2mqtt/devices.yaml`. Edit it with the **File editor** add-on or a Samba
share, then restart the add-on. One entry per device:

| Key | Means | When |
|---|---|---|
| `name` | A label you choose — **no spaces** (use `_` / `-` / `/`). | Always |
| `address` | The device's own EnOcean ID, e.g. `0x059ED79A`. | Always |
| `eep` | An EnOcean profile like `A5-13-01`. For sensors, handles, weather, contacts… | Sensors |
| `model` | An Eltako model like `eltako/fsb14`. | Eltako actuators |
| `sender` | Your stick's Base ID **+ a unique offset** per device. | With `model` |
| `shut_time` | Seconds for a full open→close. | Covers/blinds |
| `security` | `true` to decode this device's **secure** (AES/VAES) telegrams. Requires `key`. | Secure devices |
| `key` | The device's 16-byte AES key as **32 hex chars**. | With `security` |
| `rlc` / `slf` | Starting rolling code and Security-Level-Format byte (defaults to `0x8B` = 24-bit implicit RLC + 3-byte CMAC, what PTM215 switches use). | Optional, secure |
| `key_snd` / `rlc_snd` | Separate outbound key / rolling code for **sending** secure telegrams to the device. | Optional, secure TX |
| `publish_json` | MQTT state payload format (advanced). Default (`true` in the add-on) = one **JSON** object per telegram, which the HA entities read; `false` = one topic per field (`enocean2mqtt/<name>/<FIELD>`). Only set `false` if you consume MQTT yourself — it breaks the auto-created HA entities. | Optional |
| `ignore` | `true` to **drop** all telegrams from this address (e.g. suppress a device you don't want, or your own transmit echo). | Optional |

Every device needs `name` + `address` + **exactly one** of `eep` or `model`.

> 🔒 **Secure (AES/VAES) devices** are usually added hands-free: with the **LEARN** switch on, a
> secure teach-in (`SEC_TI`) is learned and the device is written into this file automatically (see
> [[Teach In]]). To add one by hand, set `security: true` + `key:` (the 32-hex AES key); `rlc`/`slf`
> and the `_snd` keys are optional. For a PSK-protected teach-in, set the add-on's `secure_psk` option.

```yaml
devices:
  - name: Wetterstation        # sensor by EEP — no pairing, no sender
    address: 0x059ED79A
    eep: A5-13-01

  - name: Licht_Kueche         # Eltako relay/light by model — needs a sender
    address: 0xFF94CEA0
    model: eltako/fsr14
    sender: 0xFFAE7C90

  - name: Rollo_Wohnzimmer     # Eltako blind — add shut_time for position
    address: 0xFF94CE9C
    model: eltako/fsb14
    sender: 0xFFAE7C81
    shut_time: 64

  - name: Taster_Flur          # secure (AES/VAES) rocker configured by hand
    address: 0x0512ABCD
    eep: F6-02-01
    security: true
    key: 0123456789ABCDEF0123456789ABCDEF   # the device's 32-hex AES key
```

> ⚠️ **Common mistakes:** spaces in `name`; setting **both** `eep` and `model`; a `model` with no
> `sender`; the **same** `sender` on two devices (each must be unique).

> 💡 **Find a device's address:** set **`log_level: debug`**, restart, trigger the device (press the
> switch, open the window). In the **Log**, a `received:` line shows the id, e.g. `05:9E:D7:9A` →
> write it as `0x059ED79A`. Turn it back off afterwards.

See [[supported devices|Supported Devices]] for the model list and
[[device examples|Examples]] for ready-made entries.
