# FAQ

**"The add-on won't install or won't start on a recent Home Assistant."**
Install it from **this** add-on repository, make sure **Mosquitto** is installed, and remove Home
Assistant's **built-in EnOcean integration** (it grabs the USB stick). See
[[Troubleshooting]].

**"Pairing / 'learn' does nothing for my sensor."**
Sensors don't pair — just list them with an `eep`. Only actuators (relays, dimmers, blinds) are
paired; see [[Eltako Setup]].

**"Is my Eltako FSB14 / FUD14 / FSB61 / FD62 supported?"**
Yes — use `model: eltako/…` (see [[Supported Devices]]).

**"My weather station / window handle isn't in the model list."**
That's expected — non-actuators are added by `eep`, not `model` (a Hoppe handle is `eep: F6-10-00`,
an FWG14MS weather station is `eep: A5-13-01`).

**"Is device X supported?"**
Almost the whole EnOcean range decodes out of the box — including **D2-01-11** (Omnio in-wall
actuators), added as a standard single-channel D2-01 switch. If a specific multi-channel or metering
variant misbehaves, capture a telegram (see [[Configuration (devices.yaml)]]) and open an issue.

**"Do I have to configure my secure / encrypted switch by hand?"**
No — turn on the **LEARN** switch and teach it in. A secure (`SEC_TI`) device is learned automatically
(its key + rolling code) and appended to `devices.yaml`. You can also add one by hand with
`security: true` + `key:` — see [[Configuration (devices.yaml)]]. For a PSK-protected teach-in, set the
`secure_psk` add-on option.

**"Will a secure device stop working after I restart?"**
No — rolling codes are persisted, so a secure device keeps working across restarts (no re-sync needed).

**"Where do I see the transceiver's status (repeater, duty-cycle)?"**
On the **bridge** device: it exposes firmware/chip-id, repeater level, available TX duty-cycle % and a
transmit-failures counter as diagnostic sensors.

**"What's the difference between Chip ID and Base ID — and which one is the `sender`?"**
The **Chip ID** is the stick's fixed, unique factory identity. The **Base ID** is a separate,
(re-)writable range the stick may **transmit** from: its Base ID plus an offset of **1–127** (128
addresses total). A device's `sender` is always **Base ID + offset** — never the Chip ID, never the
actuator's own address, and never the ID a wall switch broadcasts. When you pair an actuator you teach
it that `sender` address to obey. See [[Eltako Setup]].

**"Can I use this without Mosquitto?"**
No — an MQTT broker (Mosquitto or another) is required; it's how the add-on talks to Home Assistant.

**"Some commands are lost when I trigger many blinds/lights at once."**
Leave the **Send interval** option at its default (100 ms) — it spaces radio commands so none are
dropped. See [[Troubleshooting]].
