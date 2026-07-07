# EnOcean MQTT for Home Assistant

A Home Assistant add-on that bridges **EnOcean** devices to **MQTT** — the whole EnOcean Equipment
Profile (EEP) range — and auto-creates entities via MQTT discovery. It talks to the transceiver over
a local USB stick or a remote ser2net endpoint (e.g. a Raspberry Pi). It doesn't just *read* devices —
it **controls** them (Eltako, D2 relays/blinds, rocker emulation), decodes and sends **secure
(AES/VAES)** telegrams, and auto-provisions UTE/secure devices via a LEARN button.

> ### ★ First-class Eltako support
> Beyond generic EnOcean, there's a built-in **Eltako** catalog: one-line `model: eltako/…` entries
> for FSR14 relays/lights, FUD14 dimmers, FSB14 blinds/covers (with cover-position tracking that
> survives restarts) and their Series-61 / TF61 siblings — no hand-written EEP templates.

## New here? Start with [[Getting Started]]

The step-by-step guide takes you from install to your first working Eltako device.

## All pages

- **[[Getting Started]]** — install → connect → first device, step by step.
- **[[Configuration|Configuration (devices.yaml)]]** — the add-on options and the `devices.yaml` keys.
- **[[Eltako Setup]]** — pairing Eltako actuators (PCT14 / FAM14, the pairing button).
- **[[Raspberry Pi Transceiver]]** — put the USB stick on a Pi and reach it over ser2net (TCP).
- **[[Teach In]]** — the UTE teach-in / LEARN button flow.
- **[[Supported Devices]]** — the Eltako model list and EEP-only devices.
- **[[Examples]]** — copy-paste `devices.yaml` recipes for many device types.
- **[[Troubleshooting]]** — the common problems and their fixes.
- **[[FAQ]]** — quick answers to the recurring questions.

## In one minute

1. Install the add-on + the **Mosquitto** broker.
2. Point it at your stick: set **Device** to the local serial path (e.g. `/dev/ttyUSB0`; the startup
   log lists the available ones) **or** set **TCP** to `<pi-ip>:3000` (stick on a Pi via ser2net).
3. List your devices in `/config/enocean2mqtt/devices.yaml` (each needs `name` + `address` +
   either `eep:` or `model:`).
4. For Eltako actuators, pair them once (see [[Eltako Setup]]) and give each a unique `sender`.
5. Restart — entities appear in **Settings → Devices & Services → MQTT**.
