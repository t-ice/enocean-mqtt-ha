# Eltako Setup

An Eltako actuator (relay, dimmer, blind) only reacts to Home Assistant after you **pair** it — teach
it a *sender* address that belongs to your USB stick. Sensors don't need any of this.

## The idea: sender = Base ID + offset

Your stick has a **Base ID** (shown in the add-on **Log** at startup, e.g. `0xFFAE7C80`). For each
actuator you pick a **unique** `sender` = Base ID **+** a small offset:

```
0xFFAE7C80  (Base ID)
       + 1  (offset for this device)
= 0xFFAE7C81  (sender)
```

Use a different offset per actuator (`…81`, `…82`, `…83`, …). Never reuse a `sender`.

> **The offset has a limit.** A transceiver can only transmit from its **Base ID + 0 … 127** — 128
> addresses in total. Offset 0 is the Base ID itself (used for devices without a `sender`), so pick
> offsets **1 … 127** (`0x01`–`0x7F`) for your actuators. A large or arbitrary value is not a valid
> sender — from version 1.1.0 the add-on warns at startup about every `sender` outside the range.
> And the `sender` is **not** the actuator's own address and **not** the chip ID a wall switch
> broadcasts — it is a *new* address (belonging to your stick) that you teach the actuator to obey.
> See [[Base ID vs Chip ID|FAQ]].

## Let the add-on pick the sender (`sender: auto`)

> **Requires add-on version 1.1.0 or newer.** Older versions refuse to start with `sender: auto`.

Don't want to keep track of the offsets yourself? Write `auto` instead of an address:

```yaml
  - name: Rollo_Wohnzimmer
    address: 0xFF94CE9C
    model: eltako/fsb14
    sender: auto             # the add-on picks a free address once
    shut_time: 64
```

1. Restart the add-on. It picks the next free address and **writes it into your `devices.yaml`**,
   replacing `auto` (your comments and formatting are kept). The entry then looks exactly like a
   hand-written one, e.g. `sender: 0xFFAE7C86`.
2. Read the address from the add-on **Log** — look for
   `Assigned sender 0xFFAE7C86 to Rollo_Wohnzimmer` — or from your `devices.yaml`. If the file is
   open in an editor, reload it before you edit it again, otherwise you overwrite the new address.
3. Pair the actuator with that address as described below (PCT14 or the pairing button).

How the address is chosen — and why:

- It is assigned **once** and never changes afterwards: from then on it is an ordinary fixed
  `sender` in your file. Devices that already have a `sender` are never touched.
- It is always **one above the highest address ever used** (by any device, including ones you have
  since removed). Gaps are deliberately **not** filled: an actuator you deleted from `devices.yaml`
  still obeys its old sender, and handing that address to a new device would switch both.
- Until the address is saved to `devices.yaml`, the device stays **inactive** (no entities, no
  commands). That is the case if the file is read-only or the stick didn't report its Base ID — see
  [[Troubleshooting]].

`sender: auto` only picks the address. Teaching it into the actuator stays a manual step.

## Pair with PCT14 (recommended)

You don't need to fiddle with the rotary wheels on the modules if you have a laptop and Eltako's
**PCT14** software (free from the Eltako website). It's not the most intuitive tool, but it works —
and it lets you **back up your whole Eltako bus config**. Connect the laptop to the **FAM14** with a
(micro-)USB cable.

> 💡 In PCT14, always press **"Daten übernehmen"** before you switch to another module — otherwise
> your edits to the current one are discarded.

1. On the **FAM14**, set the **upper** rotary (operating mode) to a position that **forwards received
   radio telegrams to the bus** (positions **5–7** per the FAM14 manual; 2–4 only send bus events out
   as radio) and leave the **lower** rotary at **AUTO** — otherwise commands never reach the actuators.
2. Open the actuator and enter your chosen `sender` (the `sender` from your `devices.yaml`) into the
   correct **function group / function**:

   | Device | Function group | Function |
   |---|---|---|
   | FSR14 / F4SR14 (relay) | group 2 | function 51 |
   | FSB14 (blind/cover) | group 2 | function 31 |
   | FUD14 (dimmer) | group 3 | function 31 |
   | F4HK14 (heating actuator) | group 3 | function 65 (virtual switches use function 2) |

> ✅ **For blinds/covers:** also enable **confirmation telegrams** in PCT14 — without them Home
> Assistant never learns the blind's position.

Inside a module the sender IDs live in per-function-group **ID tables** — the `sender` you teach
appears as an `ID (Hex)` entry in the module's function group (the one from the table above).

## No PCT14? Use the pairing button

1. Put the actuator into its own pairing mode (e.g. an **FSB61**: lower rotary to **MAX**, upper to
   **LRN** — the LED blinks).
2. Add the device to `devices.yaml` (with a fixed `sender` or `sender: auto`) and restart, then open
   its device page in Home Assistant and press the **pairing** button entity.
3. Turn learning off again afterwards.

## Then add it to devices.yaml

Use the **same** `sender` you paired:

```yaml
  - name: Rollo_Wohnzimmer
    address: 0xFF94CE9C      # the actuator's own id (read it in PCT14 / the add-on log)
    model: eltako/fsb14
    sender: 0xFFAE7C81       # the sender you taught it
    shut_time: 64            # covers only: full open→close in seconds
```

Restart the add-on; the device appears under **Settings → Devices & Services → MQTT**. See
[[supported devices|Supported Devices]] for the full model list and
[[troubleshooting|Troubleshooting]] if a cover's position looks wrong.
