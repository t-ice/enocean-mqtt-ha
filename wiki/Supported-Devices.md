# Supported devices

Two ways to declare a device in `devices.yaml`:

- **`model: eltako/<name>`** — a curated Eltako actuator profile (control + feedback + HA entities).
- **`eep: RORG-FUNC-TYPE`** — any device by its EnOcean Equipment Profile (sensors, window handles,
  weather stations, other manufacturers). The code-defined engine decodes the F6 / D5 / A5 / D2
  families.

## Eltako models

All Series-14/61 actuators speak Eltako's **A5-38-08** central command; feedback is **A5-02-01**
(relays/dimmers) or **A5-3F-7F** (covers). Many model names are aliases of one base profile.

| `model: eltako/…` | Aliases | Control / feedback EEP | HA entity |
|---|---|---|---|
| `fsr14` | `fsr61`, `f4sr14`, `ftn14`, `fmz14`, `fl62` | A5-38-08 / A5-02-01 | switch + light (relay) |
| `fud14` | `fud61`, `fdg14`, `fsg14`, `fd62`, `tf61d` | A5-38-08 / A5-02-01 | dimmable light (+ dim speed) |
| `fsb14` | `fsb61`, `fsb61np` | A5-3F-7F / A5-02-01 | cover (shutter/blind) |
| `fj62` | `tf61j` | A5-3F-7F / A5-02-01 | cover (+ end-position binary sensors) |
| `tf61l` | — | A5-38-08 / A5-02-01 | switch + light (+ unlock / feedback buttons) |
| `fhd60sb` | — | A5-06-01 | brightness (lux) sensor |

`tf61d` (flush dimmer) is the same profile as `fud14`, incl. dimming.

> **Why a relay shows up twice.** A relay actuator (`fsr14` & its aliases, `tf61l`) is published as
> **both a `switch` and a `light`** entity for the same channel — they track the same state, so use
> whichever fits the load and hide the other. You only ever need to control one of them.

### Pairing (PCT14)

The Eltako side must learn the add-on's *sender* (the transceiver Base ID + a unique offset you set
per device via `sender:`). Easiest with a laptop + the Eltako **PCT14** software on the FAM14 (press
"Daten übernehmen" before switching modules). Assign the `sender` address to the actuator's function
group:

| Device | Function group / function |
|---|---|
| FSR14 / F4SR14 | group 2, function 51 |
| FSB14 | group 2, function 31 |
| FUD14 | group 3, function 31 |

Covers also need **confirmation telegrams enabled** (FSB61: PC pairing mode — lower rotary MAX, upper
rotary LRN — then click the HA `pairing` button) or you get no position feedback. Set `shut_time` to
the full travel time in seconds so the cover position tracks correctly.

### Cover position & direction

An FSB14/FSB61 has **no absolute position sensor** — the position (0 = closed … 100 = open) is
**derived from travel time**, so it is only reliable once you have set `shut_time` to the *measured*
full open→close time in seconds, and after the blind has hit a real end-stop (a full open or full
close) at least once to re-synchronise. If position drifts, drive it fully open or fully closed once.
The add-on persists the tracked position across restarts, so a reboot does not lose it.

If **up/down are reversed** (closing when Home Assistant says open, or the position runs the wrong
way), the actuator is wired/paired with the opposite travel direction. Correct it at the source — swap
the drive direction in PCT14 (or the motor's up/down wiring) — rather than in Home Assistant; that
keeps position tracking consistent. `shut_time` too short shows the blind as fully open/closed before
it physically arrives; too long, the opposite.

## Devices configured by EEP (no model needed)

> Most of these are **decode-only** (read-only) — the add-on listens and publishes their state, so
> they need no `sender` and no pairing. Two D2 families are the exception: **`D2-01` relays/dimmers**
> and **`D2-05` blinds** are *controllable* — they get switch/light/cover entities and send commands
> (give them a `sender` for the outbound telegrams). Eltako actuators are controlled via a `model:`
> entry (see the table above). For anything not listed, try the generic profile for its family
> (`eep: F6-…` / `D5-…` / `A5-…` / `D2-…`) and watch the log — most of the EnOcean range decodes out
> of the box.

> **Still not decoded or mapped?** **[Open a device support request](https://github.com/t-ice/enocean-mqtt-ha/issues/new/choose)**
> with a telegram capture (procedure below) — the device is then added to the shipped catalog, so
> everyone with that device benefits.

> **How to find your device's EEP.** EnOcean telegrams (except UTE teach-in) carry **no** self-describing
> profile, so there is **no automatic device discovery** — you must declare the EEP, or the log shows
> `message not interpretable`. Find it in this order: (1) the device **datasheet / label** usually
> prints the EEP (e.g. `A5-13-01`); (2) failing that, set `log_level: debug`, trigger the device, and
> read the first byte of the raw telegram — `F6` = RPS rocker, `D5` = 1BS contact, `A5` = 4BS sensor,
> `D2` = VLD — then pick the matching `FUNC-TYPE` from the [EnOcean EEP viewer](https://tools.enocean-alliance.org/EEPViewer/);
> (3) as a fallback, try the generic profile for the family and watch the decoded fields.

| Device | `eep:` | Notes |
|---|---|---|
| Hoppe **FHF** window handle | `F6-10-00` | 3-position (open / tilt / closed) |
| Eltako **FWG14MS** weather station | `A5-13-01` | wind / rain / brightness / temperature |
| **Omnio** in-wall actuator (UPS230/UPH230 …) | `D2-01-11` | standard single-channel D2-01 switch |
| Room operating panels (Thermokon, Eltako FTR, Thanos, Kieback+Peter …) | `A5-10-01`…`A5-10-23` | temperature / set point / humidity / fan / occupancy, per type |
| Barometric sensors | `A5-05-01` | air pressure 500–1150 hPa |
| Electronic switches / dimmers / metering plugs (NodOn, Permundo, PEHA, Omnio …) | `D2-01-00`…`D2-01-14` | full D2-01 range: on/off, dimming, energy metering, 1–2 channels |
| Blind / shutter actuators (Becker, OPUS …) | `D2-05-00/01/02/04/05` | position + angle cover control |
| Window / mechanical handles | `D2-03-10` | open / tilted / closed |
| Multi-function sensor (temp/humidity/lux/acceleration) | `D2-14-40` | e.g. STM550-class |
| HVAC fan / ventilation (Maico …) | `D2-20-00` | fan speed + humidity + operating mode |
| Window / lock handles (HOPPE, Soda, Siegenia) | `D2-06-01/40/50` | position, lock, temperature/humidity/illumination — **read-only** |
| Room control panels (Kieback+Peter, Thermokon Thanos) | `D2-10-00/01/02`, `D2-11-01`…`D2-11-08` | temperature / set point / humidity / fan / occupancy — **read-only** |
| Thermokon **SRW01** and other sensors | per datasheet EEP | any decodable F6/D5/A5/D2 profile |

> **Note — the D2-06/10/11 panels & handles are read (decode) only.** These profiles are
> bidirectional and stateful in the wild; this add-on decodes the sensor/status telegram they emit
> (so their values appear in Home Assistant) but does **not** implement the return-channel control
> handshake. `D2-10-01` is validated against a real Kieback+Peter capture; the rest are spec-verified
> only — please send a capture (procedure below) if a value looks wrong for your device.

> **Note — A5-10 / A5-05 decoders are spec-verified, not hardware-verified.** The bit layouts
> come from the public EnOcean EEP v2.6.7 spec. The only
> A5-10 type validated against a real capture is `A5-10-06` (Eltako FTR55H). If a reading looks wrong
> for your panel, please capture a telegram (procedure below) and open an issue. Note the temperature
> encoding differs by type (types `01`–`0D`,`15`–`17`,`1F` are inverted; `10`–`14`,`18`–`1D`,`20`–`23`
> are not) — a mismatch usually means the wrong `A5-10-xx` type is configured.

## Secure devices (AES/VAES)

Devices that encrypt their telegrams per *Security of EnOcean Radio Networks v3.02* (VAES + AES-CMAC
with a rolling code) are fully supported — decode, teach-in, and transmit:

- **Auto-provisioned:** with the **LEARN** switch on, a secure teach-in (`SEC_TI` — e.g. a PTM
  secure switch) is learned automatically (key + rolling code) and written to `devices.yaml`; a
  PSK-protected teach-in needs the add-on's `secure_psk` option. See [[Teach In]].
- **By hand:** add `security: true` + `key:` (the 32-hex AES key) to any device entry; `rlc`/`slf`
  default sensibly (`slf` = `0x8B`, what PTM215 uses), and `key_snd`/`rlc_snd` enable secure *sending*.
- **Durable:** rolling codes persist across restarts, so a secure device isn't rejected after a reboot.

## Sending to devices (transmit / control)

Beyond Eltako, the add-on can *drive* devices, not just read them: **D2-01** relays/dimmers, **D2-05**
blinds, and **F6 rocker emulation** — an F6 virtual device exposes a rocker `action` select plus
one-click momentary **AI / AO / BI / BO** press buttons for driving actuators paired to a rocker.

## More Eltako devices

### FSB61NP (wireless blind actuator)

Add it as `model: eltako/fsb61np` — an alias of the `fsb14` cover profile. It gets a cover entity;
set `shut_time` to the full travel time as for any FSB. (The FWG14MS weather station is configured
by EEP — see `A5-13-01` in the [EEP table](#devices-configured-by-eep-no-model-needed) above.)

### FMS61NP-230V (2-channel impulse switch)

Researched from the Eltako datasheet. Unlike the FSR/FSB **-14** actuators
(which return an `A5-02-01` confirmation via the FAM14), the wireless FMS61NP reports each relay's
state as a **PTM200 / `F6-02-01`** rocker telegram — which this add-on **decodes correctly** (the
`R1` field carries the channel + on/off). Verified decode:

| Feedback telegram `R1` (RPS DB `0x_0`) | Meaning |
|---|---|
| `Button BO` (`0x70`) | channel 1 **on** |
| `Button BI` (`0x50`) | channel 1 **off** |
| `Button AO` (`0x30`) | channel 2 **on** |
| `Button AI` (`0x10`) | channel 2 **off** |

Recipe (until a turnkey `fms61np` model with 2-sender control is verified on hardware):

```yaml
devices:
  # State feedback (both channels arrive here as F6 rocker events; R1 distinguishes them):
  - name: FMS_Flur
    address: 0x05XXXXXX          # the FMS61NP's own EnOcean id
    eep: F6-02-01
  # Optional control — one entry per channel, each taught its own sender (A5-38-08, like FSR):
  - name: FMS_Flur_K1
    address: 0x05XXXXXX
    model: eltako/fsr14
    sender: 0xFFYYYYYY           # base id + a unique offset, paired to channel 1
```

In HA, template a `binary_sensor` per channel off `R1` (e.g. `on` when `value_json.R1` is `Button BO`).
A capture confirming the control addressing would let us ship a single turnkey model.

### How to capture a telegram (to add / fix a device)

1. Set `log_level: debug` in the add-on options and restart.
2. Actuate the device (press its switch / trigger each channel / open+close the cover).
3. Collect the `received: …` lines and the `_RAW_DATA_` values from the log for each distinct action.
4. Open an issue with the model, the raw telegrams, and what each action was — that's enough to pin
   the EEP and add a verified mapping.
