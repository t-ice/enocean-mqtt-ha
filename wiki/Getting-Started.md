# Setup guide (start here)

Get your EnOcean and Eltako devices into Home Assistant — step by step, no prior experience needed.
Follow the steps in order. This guide is also published (with navigation) in the project
[Wiki](https://github.com/t-ice/enocean-mqtt-ha/wiki).

## 1 · Check what you need

- **Home Assistant** that can run add-ons (HA OS or Supervised).
- The **Mosquitto broker** add-on (installed in step 2) — how this add-on talks to Home Assistant.
- An **EnOcean USB stick** (USB300, FAM-USB, …) — plugged into your HA machine, or into a Raspberry
  Pi on your network ([[Pi setup|Raspberry Pi Transceiver]]).
- **For Eltako Series-14** (FSR14, FSB14, FUD14 …): the **FAM14** bus module and — recommended — a
  Windows laptop with Eltako's free **PCT14** software + a USB cable to the FAM14.

**Good to know:** sensors (buttons, contacts, weather) just need to be *listed* — no pairing.
Actuators (relays, dimmers, blinds) must be *paired* once (step 5).

### How the pieces connect (Eltako)

New to Eltako Series-14? These two boxes do different jobs — a common source of confusion:

- The **EnOcean USB stick** is Home Assistant's radio. The add-on sends and receives **over the air**
  through it. It is **not** wired into your Eltako bus.
- The **FAM14** is the Eltako **RS485-bus** radio module. Series-14 actuators (FSR14, FSB14, FUD14 …)
  have **no radio of their own** — the FAM14 receives the stick's wireless telegrams and forwards them
  onto the bus, and sends the actuators' feedback back over the air. It's also what you plug the
  **PCT14** laptop into for pairing. (On installs that use it, **FGW14 / FGW14-USB** is the equivalent
  bus gateway.)

So a command travels **Home Assistant → MQTT → add-on → USB stick (radio) → FAM14 → RS485 bus →
actuator**, and feedback returns the same way. You need *both* the stick and the FAM14 for Series-14
actuators; a stick alone can talk to battery/wireless EnOcean devices but not to bus actuators.

## 2 · Install the add-on

1. **Settings → Add-ons → Add-on Store**.
2. Top-right **⋮ → Repositories**, paste the add-on repository URL, **Add**.
3. Open **EnOcean MQTT for Home Assistant** and click **Install**.
4. Also install and start the **Mosquitto broker** add-on if you don't have it.

## 3 · Connect your USB stick

1. Open the add-on's **Configuration** tab.
2. Point the add-on at your transceiver, using one of the two fields on the Configuration tab:
   - **Device** — if the stick is plugged into the HA machine, enter its serial path (e.g.
     `/dev/ttyUSB0`). The add-on lists the available serial devices in its startup **Log**, so start
     it once and copy the right path from there.
   - **ser2net (TCP)** — if the stick is on a Raspberry Pi running ser2net, enter `192.168.1.50:3000`
     (the Pi's address). If both are filled, TCP wins.
3. Leave the MQTT fields **blank** — the add-on auto-detects the Supervisor's Mosquitto. Only fill
   them if you use a *different* external broker.
4. **Save**, then **Start** from the Info tab.

> ⚠️ **Avoid the #1 gotcha:** if Home Assistant's **built-in “EnOcean” integration** is set up,
> remove it. Two things can't share one USB stick — you'd get “Data CRC error” or no feedback.

The Log shows the transceiver's **Base ID** — keep it handy for step 5.

## 4 · Understand `devices.yaml`

Your list of devices lives at `/config/enocean2mqtt/devices.yaml`. Edit it with the **File editor**
add-on or a Samba share. Every entry needs a **name**, an **address**, and **either** an `eep`
(sensors/generic EnOcean) **or** a `model` (Eltako actuators):

| Key | Means | When |
|---|---|---|
| `name` | A label you choose (no spaces). | Always |
| `address` | The device's own ID, e.g. `0x059ED79A`. | Always |
| `eep` | An EnOcean profile like `A5-13-01`. | Sensors |
| `model` | An Eltako model like `eltako/fsb14`. | Eltako actuators |
| `sender` | Your Base ID + a unique offset per device. | With `model` |
| `shut_time` | Seconds for a full open→close. | Covers/blinds |

```yaml
devices:
  - name: Wetterstation        # a sensor, by EEP — no pairing
    address: 0x059ED79A
    eep: A5-13-01

  - name: Licht_Kueche         # an Eltako light, by model — needs a sender
    address: 0xFF94CEA0
    model: eltako/fsr14
    sender: 0xFFAE7C90

  - name: Rollo_Wohnzimmer     # a blind — add shut_time for position
    address: 0xFF94CE9C
    model: eltako/fsb14
    sender: 0xFFAE7C81
    shut_time: 64
```

> ⚠️ **Common mistakes:** spaces in `name`; setting *both* `eep` and `model`; a `model` with no
> `sender`; the same `sender` on two devices.

> 💡 **Find a device's address:** set **`log_level: debug`**, restart, trigger the device, and read the
> `received:` line in the Log (e.g. `05:9E:D7:9A` → `0x059ED79A`). Turn it back off after.

## 5 · Add an Eltako device (the important one)

An Eltako actuator only reacts to Home Assistant after you **pair** it — teach it a *sender* address
that belongs to your stick.

### 5a · Pair on the Eltako side (PCT14)

1. On the **FAM14**, the **upper** rotary (operating mode / *Betriebsart*) must be in a position that
   **forwards received radio telegrams to the bus** (positions **5–7** per the FAM14 manual; 2–4 only
   send bus events out as radio), and the **lower** rotary at its normal **AUTO** position. Otherwise
   the actuators never receive Home Assistant's commands.
2. Choose a **sender** = your **Base ID** (step 3) **+** a small **unique** offset:
   `0xFFAE7C80 + 0x01 = 0xFFAE7C81`.
3. In **PCT14**, teach that sender into the actuator's function group:

   | Device | Function group | Function |
   |---|---|---|
   | FSR14 / F4SR14 (relay) | group 2 | function 51 |
   | FSB14 (blind/cover) | group 2 | function 31 |
   | FUD14 (dimmer) | group 3 | function 31 |

> ✅ **For blinds/covers:** also enable **confirmation telegrams** in PCT14, or Home Assistant never
> learns the position.

### 5b · Add it and check Home Assistant

Add the entry with the same `sender` you paired, then restart the add-on:

```yaml
  - name: Rollo_Wohnzimmer
    address: 0xFF94CE9C
    model: eltako/fsb14
    sender: 0xFFAE7C81
    shut_time: 64
```

In **Settings → Devices & Services → MQTT** the device appears with its entities — try it.

> 💡 **No PCT14?** Put the actuator in its own pairing mode (e.g. FSB61: lower rotary MAX, upper LRN),
> press the add-on's **pairing** button on the device page, then turn learning off.

## 6 · Check it works

- `enocean2mqtt/bridge/state` should be `online`; `enocean2mqtt/bridge/stats` shows uptime + Base ID.

| Problem | Fix |
|---|---|
| Won't start; log loops “Waiting for device base ID”. | Something else holds the stick (usually HA's built-in EnOcean integration — remove it), or the **Device**/**TCP** setting is wrong. |
| “Data CRC error” / no feedback. | Disable HA's built-in EnOcean integration, or move the stick to a Raspberry Pi. |
| Firing many blinds/lights at once — some don't move. | Leave **Send interval** at 100 ms (paces radio commands). |
| A cover's position is wrong. | Position is time-based (no absolute sensor): set `shut_time` to the *measured* full travel time + enable confirmation telegrams in PCT14, then drive the blind fully open or closed once to re-sync. |
| A cover runs the wrong way (up ↔ down swapped). | The actuator is paired with the opposite direction — swap the drive direction in PCT14 (or the motor wiring), not in HA. See [[supported devices|Supported Devices]] → *Cover position & direction*. |

More in [[Troubleshooting]].

## 7 · FAQ

- **“Won't install/start on a recent HA.”** Install from this repo, install Mosquitto, and remove
  HA's built-in EnOcean integration.
- **“Pairing/learn does nothing for my sensor.”** Sensors don't pair — list them with an `eep`.
- **“Is my Eltako FSB14/FUD14/FSB61/FD62 supported?”** Yes, via `model: eltako/…` — see
  [[supported devices|Supported Devices]].
- **“My weather station/handle isn't in the model list.”** Expected — non-actuators use `eep`
  (Hoppe handle `F6-10-00`, FWG14MS weather `A5-13-01`).
- **“Is device X supported?”** Almost the whole EnOcean range — including **D2-01-11** (Omnio
  in-wall actuators), added as a standard single-channel D2-01 switch. A multi-channel/metering
  variant that misbehaves may need a telegram capture.
- **“Do I have to set up my secure/encrypted switch by hand?”** No — turn on the **LEARN** switch and
  teach it in; a secure (`SEC_TI`) device is learned (key + rolling code) and added to `devices.yaml`
  automatically, and keeps working across restarts. See [[Teach In]].

## 8 · More examples

The [[device examples cookbook|Examples]] has ready-to-paste entries for lights, dimmers,
4-channel relays, blinds, wall switches, window handles, contacts, temperature/humidity, weather,
occupancy, CO₂, meters, and the FMS61NP.
