# Teach-in & commissioning

Teach-in comes in **two opposite directions**, and one switch gates all of it:

- **A device teaches itself *to* the bridge** — a sensor/switch announces what it is, and the add-on
  can add it to Home Assistant automatically.
- **The bridge teaches its *sender* to an actuator** — an Eltako relay/blind learns to obey the
  add-on. Here the device is already in your `devices.yaml`; pairing just makes it listen.

## The LEARN switch (the gate)

Teach-in is **off at startup**. Turn on the **LEARN** switch (published by the add-on as an MQTT
entity) to accept teach-ins; it **auto-disables after 5 minutes** so a forgotten-on learn mode can't
keep mass-accepting stray telegrams. Nothing is accepted or auto-created while it's off. Teach-in /
pairing telegrams are only ever sent in response to an explicit action — never on a timer.

![Teach-in state diagram: from Idle, turning the LEARN switch ON enters Learning; it returns to Idle
when the switch is turned OFF or after a 5-minute auto-timeout. While in Learning the pairing button
sends a learn telegram from the sender, and only in this state are teach-in telegrams accepted or
emitted.](https://raw.githubusercontent.com/t-ice/enocean-mqtt-ha/master/docs/img/teach-in-state.png)

## Direction A — a device teaches itself to the bridge

With **LEARN** on, teaching in a device makes the add-on create it automatically — *if* the teach-in
carries a decodable **EEP** (the profile that says what the device is). Whether it does depends on the
family:

| Device family | With LEARN on, the add-on… | `devices.yaml` |
|---|---|---|
| **UTE** (D2 — e.g. NodOn / D2-05 blinds) | answers the handshake and creates the device from the EEP it carries — appears in HA right away | **auto-created** |
| **Secure** (`SEC_TI` — e.g. a PTM switch) | reassembles the encrypted teach-in and learns the device's **key + rolling code**. A **PTM switch** is auto-created as a secure `F6-02-01`; for an **already-listed device** the key is attached to it; an **unknown non-PTM** device can't be typed automatically, so add it by hand first and the key attaches on the next teach-in | auto (PTM) / manual (other) |
| **4BS** (A5) | auto-creates **only if** the teach-in includes its EEP (some 4BS sensors set that flag, many don't) | auto *if* EEP present, else manual |
| **RPS** (F6 rockers) / **1BS** (D5 contacts) | can't auto-create — these teach-in telegrams carry **no EEP**, so the add-on can't tell what the device is | **manual** |

Notes:
- Auto-created devices are **appended to your `devices.yaml`** (comments and formatting preserved), so
  they load normally after a restart and you can rename/edit them like any other entry.
- Re-teaching a device that's already known is a **no-op** — it won't be added twice.
- **Secure rolling codes persist** across restarts, so a secure device isn't rejected after a reboot.
- If a device sends a **PSK-protected** secure teach-in, set the add-on's advanced **`secure_psk`**
  option to its pre-shared key.
- For the **manual** cases, add the device by hand — see [[Configuration (devices.yaml)]] and
  [[Examples]] (a plain rocker is `eep: F6-02-01`, a contact `eep: D5-00-01`, etc.).

## Direction B — the bridge teaches its sender to an actuator (Eltako pairing)

Eltako Series-14/61 actuators (FSR14/FSB14/FUD14/…) are commanded from a `sender = base_id + offset`,
and each actuator channel must first learn that sender:

1. Give the device a unique `sender` in your `devices.yaml`.
   The daemon logs an **error at startup if two devices share a sender** (a hard-to-debug failure).
2. Put the actuator into LRN mode (rotary switch or PCT14).
3. Press the device's HA **pairing** button — the add-on emits the learn telegram from `sender`.
4. Verify the actuator now reports state (an F6 status telegram arrives), then return it to normal.

Model-specific pairing byte patterns are recorded per device in the shipped Eltako catalog. This
pairing is independent of Direction A — the device is configured by `model:` + `sender:`, not
auto-created.

### Sending a secure teach-in to a device

The bridge can also teach a secure device **its own** key: send the **`secure_teachin`** action to the
device's request topic and the add-on emits a secure teach-in pair, so the device learns the bridge's
key (bidirectional secure pairing).

## UTE (D2 / bidirectional devices)

Non-Eltako D2 devices (e.g. D2-05-00 blinds) use UTE — the modern D2 handshake — which the add-on
parses and answers automatically (Direction A above). Eltako Series-14 devices do **not** use UTE;
they use Eltako's A5-38-08 / A5-3F-7F commands and the sender pairing in Direction B.
