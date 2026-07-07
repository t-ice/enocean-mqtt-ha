# Troubleshooting

## No feedback from actuators / "Data CRC error"

Home Assistant's **built-in `enocean` integration** opens the same USB transceiver this add-on uses.
Two processes on one serial device cause garbled reads ("Data CRC error!", missing feedback).

Fix — make sure only **one** thing owns the stick:

- **Remove the built-in `enocean` integration** (Settings → Devices & services), or
- Use the **remote ser2net topology**: keep the USB stick on a Raspberry Pi running ser2net and set
  the `tcp` option to `host:3000`. The add-on then never touches the HA host's serial port, so the two
  can't collide. See [[Raspberry Pi Transceiver]].

The daemon itself is resilient to occasional CRC errors — it logs and skips the bad frame, then
resyncs — so a few under heavy RF traffic are harmless; a *continuous* stream means contention.

![CRC-error diagnosis flowchart: for continuous 'Data CRC error' or no actuator feedback — first
check whether HA's built-in 'enocean' integration is installed (if so, remove it, as it fights the
add-on for the USB stick); otherwise check for another add-on/process on the same serial device (stop
it, or move the stick to a Pi + ser2net); otherwise check whether bridge/stats shows telegrams
arriving — if not, verify 'connection' and RF range; occasional errors are harmless as the daemon
resyncs.](https://raw.githubusercontent.com/t-ice/enocean-mqtt-ha/master/docs/img/crc-diagnosis.png)


## Add-on won't start: "Waiting for device base ID" loops / "Serial port exception"

The daemon asks the transceiver for its Base ID at startup; the loop means it never got a valid
reply. Usual causes:

- **Another process holds the port** — see the section above (built-in `enocean` integration, or a
  second add-on). "Serial port exception (multiple access on port)" is the giveaway.
- **Wrong transceiver setting** — check the `device` path (`/dev/ttyUSB0`) or the `tcp` `host:port`.
  See "Which serial device do I use?" below.
- **Transient after a host reboot** — the add-on now self-heals (bounded Base-ID wait + exponential
  backoff reconnect), so it should recover on its own without needing manual stop/start cycles.

The Base-ID parse also accepts transceivers that append a "remaining write cycles" byte — see
[esp3-compliance.md](https://github.com/t-ice/enocean-mqtt-ha/blob/master/docs/esp3-compliance.md).

## Which serial device do I use? / "Serial device '…' not found"

For a **local** stick (no `tcp` set), the add-on lists the serial devices it can see at startup:

```
Available serial devices:
  - /dev/serial/by-id/usb-EnOcean_GmbH_EnOcean_USB_300_DA...-if00-port0
  - /dev/ttyUSB0
```

Copy one of those paths into the **Device** option. Prefer the `/dev/serial/by-id/…` form — it's
stable across reboots and re-plugging, unlike `/dev/ttyUSB0` (whose number can change).

- **"Serial device '…' not found"** at startup means the `Device` value isn't one of the listed paths
  (a typo, or the stick isn't plugged into the Home Assistant host). Fix the path, or plug the stick in.
- **"Available serial devices: none found"** means no EnOcean stick is attached to the HA host — plug
  one in, or if the stick is on a Raspberry Pi, use the `tcp` (ser2net) option instead
  (see [[Raspberry Pi Transceiver]]).
- When `tcp` is set, the add-on uses that and skips the serial list entirely.

## A device doesn't appear, or an entity stays *unknown*

EnOcean is **not** plug-and-play like Zigbee/Z-Wave — there is no automatic discovery of the device
itself. Work through this in order:

1. **Is the telegram arriving at all?** Set `log_level: debug`, restart, and trigger the device. A
   `received:` line with its address means the radio path works. Nothing at all → RF range, the wrong
   transceiver setting, or the device simply isn't transmitting.
2. **Is it declared?** An address not in `devices.yaml` (or with the wrong `eep`/`model`) logs
   *"message not interpretable"* / *"unknown sender"* and creates **no** entity. Add it with the right
   profile — see the *How to find your device's EEP* note in [[Supported Devices]].
3. **Teach-in telegrams are not turned into entities.** A brand-new device often first sends only a
   **teach-in** frame, which is filtered — nothing appears until a *data* telegram arrives. For
   self-describing devices (UTE, secure `SEC_TI`) turn on the **LEARN** switch first (see [[Teach In]]);
   plain rockers / contacts you must add by hand.
4. **A new entity reads *unknown* until its first real telegram.** Most EnOcean devices report only *on
   change*, so a freshly added entity has no state until you actually press the button / open the
   window / move the blind. That is expected — not a configuration error.

## Some commands are ignored when triggering many devices at once

Firing e.g. `cover.close_cover` at many covers in one automation can drop telegrams: an EnOcean ERP1
telegram is sent as up to 3 subtelegrams over a ~40 ms TX window and receivers collect them over a
100 ms RX maturity time, so back-to-back writes overrun the transceiver.

The add-on paces transmitted telegrams by `send_interval_ms` (default **100 ms**), which fixes this
out of the box. If your setup is reliable and you want snappier bursts, lower it (e.g. `50`); `0`
disables pacing entirely.

## Wrong or inverted values (temperature, set point, on/off swapped)

A decoded value that's consistently off usually means the **wrong EEP type** is configured. Within a
family the field layout differs by type — e.g. `A5-10-03` vs `A5-10-06` invert the temperature scale,
and several `A5-10-xx` types differ only in which fields they carry. Double-check the device's exact
EEP (datasheet / label), then set the matching `eep:`. If it still looks wrong, capture a telegram
(procedure in [[Supported Devices]]) and open an issue with the raw bytes.

## Diagnostics

- `enocean2mqtt/bridge/state` — retained `online` / `offline` availability.
- `enocean2mqtt/bridge/stats` — retained JSON: uptime, telegrams/min, unknown-sender count, reconnect
  counts, and the transceiver's `base_id` + firmware version (handy to confirm the stick is talking).
- `log_level: debug` logs every raw telegram (see the capture procedure in
  [[Supported Devices]]).
