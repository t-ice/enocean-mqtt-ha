# Device examples (cookbook)

Copy-paste `devices.yaml` snippets for common devices. They all live under one top-level `devices:`
list — merge the entries you need into a single file at `/config/enocean2mqtt/devices.yaml`, then
restart the add-on.

**Every device needs** `name` + `address` + **either** `eep:` (any standard EnOcean profile) **or**
`model:` (an Eltako actuator from the catalog). Rules the loader enforces:

- `name`: letters/digits/`_`/`-`/`/` only — **no spaces**.
- `address`: the device's *own* EnOcean ID (find it with `log_level: debug` — see the last section).
- **exactly one** of `eep` or `model` (not both).
- `model:` actuators also need a unique **`sender`** (your transceiver Base ID + a per-device offset).
- covers add **`shut_time`** (full travel time in seconds) for position tracking.

Replace the `0x…` addresses/senders with your own. See
[[supported-devices|Supported Devices]] for the full model list and Eltako pairing.

---

## Eltako actuators (use `model:`)

### FSR14 — relay (switch + light)
```yaml
devices:
  - name: Licht_Kueche
    address: 0xFF94CEA0
    model: eltako/fsr14
    sender: 0xFFAE7C90
```

### F4SR14 — 4-channel relay (one entry per channel, each with its own address + sender)
```yaml
devices:
  - name: Licht_Flur_K1
    address: 0xFF94CEA0
    model: eltako/f4sr14
    sender: 0xFFAE7C90
  - name: Licht_Flur_K2
    address: 0xFF94CEA1
    model: eltako/f4sr14
    sender: 0xFFAE7C91
  - name: Licht_Flur_K3
    address: 0xFF94CEA2
    model: eltako/f4sr14
    sender: 0xFFAE7C92
  - name: Licht_Flur_K4
    address: 0xFF94CEA3
    model: eltako/f4sr14
    sender: 0xFFAE7C93
```

### FUD14 — dimmer (dimmable light + dim-speed)
```yaml
devices:
  - name: Licht_Wohnzimmer
    address: 0xFF94CEB0
    model: eltako/fud14
    sender: 0xFFAE7CA0
```

### TF61D — flush dimmer (same profile as FUD14)
```yaml
devices:
  - name: Licht_Schlafzimmer
    address: 0xFF94CEB1
    model: eltako/tf61d
    sender: 0xFFAE7CA1
```

### TF61L — flush switch (relay, no dimming)
```yaml
devices:
  - name: Steckdose_Buero
    address: 0xFF94CEB2
    model: eltako/tf61l
    sender: 0xFFAE7CA2
```

### FSB14 — shutter/blind cover (needs `shut_time`)
```yaml
devices:
  - name: Rollo_Wohnzimmer
    address: 0xFF94CE9C
    model: eltako/fsb14
    sender: 0xFFAE7C81
    shut_time: 64          # seconds for a full open→close; enable confirmation telegrams in PCT14
```

### FJ62 — blind with end-position sensors
```yaml
devices:
  - name: Jalousie_Bad
    address: 0xFF94CE9D
    model: eltako/fj62
    sender: 0xFFAE7C82
    shut_time: 30
```

### FHD60SB — brightness (lux) sensor
This model is sensor-only, so it needs **no `sender`** (the log may note "cannot send" — that's
expected and harmless for a read-only device).
```yaml
devices:
  - name: Helligkeit_Terrasse
    address: 0x0593A1B2
    model: eltako/fhd60sb
```

---

## Sensors & inputs (use `eep:` — no pairing, no `sender`)

### Wall rocker switch (PTM210 / Eltako FT55) — `F6-02-01`
```yaml
devices:
  - name: Taster_Wohnzimmer
    address: 0xFEE25DBA
    eep: F6-02-01
```

### Window/door handle (Hoppe FHF) — `F6-10-00` (open / tilt / closed)
```yaml
devices:
  - name: Fenstergriff_Bad
    address: 0x01A2B3C4
    eep: F6-10-00
```

### Window/door contact (Eltako FTKE) — `D5-00-01`
```yaml
devices:
  - name: Kontakt_Haustuer
    address: 0x0198ADEF
    eep: D5-00-01
```

### Temperature + humidity (Eltako FTFB / FAFT60) — `A5-04-02`
```yaml
devices:
  - name: Klima_Keller
    address: 0x05A1B2C3
    eep: A5-04-02
```

### Room operating panel (Eltako FTR / room controller) — `A5-10-03`
```yaml
devices:
  - name: Raumfuehler_Wohnzimmer
    address: 0x058E4FA7
    eep: A5-10-03
```

### Weather station (Eltako FWG14MS) — `A5-13-01`
```yaml
devices:
  - name: Wetterstation
    address: 0x059ED79A
    eep: A5-13-01
```

### Occupancy / motion — `A5-07-01`
```yaml
devices:
  - name: Bewegung_Flur
    address: 0x05C1D2E3
    eep: A5-07-01
```

### Light + temperature + occupancy — `A5-08-01`
```yaml
devices:
  - name: Praesenz_Buero
    address: 0x05C4D5E6
    eep: A5-08-01
```

### CO₂ / air quality — `A5-09-04`
```yaml
devices:
  - name: Luftguete_Schlafzimmer
    address: 0x05D1E2F3
    eep: A5-09-04
```

### Energy meter — `A5-12-01`
```yaml
devices:
  - name: Stromzaehler
    address: 0x05E1F2A3
    eep: A5-12-01
```

---

## Secure devices (AES/VAES)

Secure switches/sensors are normally learned hands-free — turn on the **LEARN** switch and teach the
device in; it's written here automatically (see [[Teach In]]). To add one **by hand**, set
`security: true` and the device's 32-hex `key:`:

```yaml
devices:
  - name: Taster_Flur
    address: 0x0512ABCD
    eep: F6-02-01
    security: true
    key: 0123456789ABCDEF0123456789ABCDEF   # the device's AES key (32 hex chars)
    # optional: rlc / slf default sensibly (slf 0x8B); key_snd / rlc_snd enable secure sending
```

For a **PSK-encrypted** teach-in, set the add-on's `secure_psk` option to the device's pre-shared key.

## Special cases

### FMS61NP-230V — 2-channel impulse switch
Its per-relay feedback is an `F6-02-01` rocker telegram (channel + on/off in `R1`); control uses the
`fsr14` profile with one paired `sender` per channel. See the detailed decode table in
[[supported-devices|Supported Devices]].
```yaml
devices:
  # State feedback for both channels (R1 distinguishes them):
  - name: FMS_Flur
    address: 0x05B1C2D3
    eep: F6-02-01
  # Control, one entry per channel (each taught its own sender):
  - name: FMS_Flur_K1
    address: 0x05B1C2D3
    model: eltako/fsr14
    sender: 0xFFAE7CB0
  - name: FMS_Flur_K2
    address: 0x05B1C2D3
    model: eltako/fsr14
    sender: 0xFFAE7CB1
```

### I don't know a device's address — find it from the log
1. In the add-on **Configuration**, set `log_level: debug` and **Restart**.
2. Trigger the device (press the switch, open the window, move the cover…).
3. Open the add-on **Log** and look for a `received:` line — the sender id shown (e.g.
   `05:9E:D7:9A`) is the `address` (write it as `0x059ED79A`).
4. Turn `log_level` back to `info` when you're done.
