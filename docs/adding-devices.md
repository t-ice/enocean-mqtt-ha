# Adding a device (EEP profile + HA mapping)

Support for an EnOcean device is split into **two independent layers**. Add to whichever you need —
both for a brand-new device, or just the mapping if the EEP already decodes.

| Layer | Answers | Lives in |
|---|---|---|
| **Decode profile** | *what the telegram bytes mean* | `src/enocean2mqtt/protocol/profiles/eep/<family>.py` |
| **HA mapping** | *which Home Assistant entities appear* | `src/enocean2mqtt/homeassistant/mapping/eep/<family>.py` |

Both are split by RORG family and merged by their package `__init__`. You edit one fragment file per
layer — no merge code, no XML, nothing else to touch.

## Which fragment file?

| EEP | Profile & mapping fragment |
|---|---|
| A5-10 (room panels) | `a5_room_panels.py` |
| A5-13 (weather) | `a5_weather.py` |
| A5-20 / A5-38 / A5-3F (HVAC + gateway) | `a5_hvac.py` |
| other A5 (02/04/05/06/07/08/09/11/12/14/30/37) | `a5_sensors.py` |
| D2-01 (switches/dimmers/meters) | `d2_switches.py` |
| other D2 | `d2_devices.py` |
| F6 (rockers) / D5 (contacts) | `f6.py` |
| Eltako model (mapping only) | `mapping/eep/eltako.py` |
| bridge RSSI/last-seen/LEARN (mapping only) | `mapping/eep/misc.py` |

## 1. Add the decode profile

In the profile fragment, add one `(rorg, func, type): profile(...)` entry with the `_build.py`
helpers (`profile`, `case`, `field`, `enum`, `cond`, and the shared `LRNB_4BS`). Pass only the kwargs
you need — the rest default.

```python
# protocol/profiles/eep/a5_sensors.py
(0xA5, 0x02, 0x30): profile(0xA5, 0x02, 0x30, "My Temperature Sensor",
    case((
        LRNB_4BS,                              # the 4BS teach-in bit, reused everywhere
        field("TMP", "Temperature", 16, 8, "value",
              unit="°C", range_min=255, range_max=0, scale_min=-40, scale_max=0),
    )),
),
```
- `field(shortcut, name, offset, size, kind, …)` — `kind` is `value` / `enum` / `bool` / `raw` /
  `fixed`. `value` with `range_*`+`scale_*` scales raw→physical; `enum` needs `items=(enum(...), …)`.
- Use `cond("data", offset, size, value)` in a `case` when the layout depends on a message-type field
  (e.g. D2-50).

## 2. Add the HA mapping

In the mapping fragment, add the entities the device should expose, with `_builders.py`
(`dcfg`, `sensor`, `binary`, `entity`, `vt`) — and reuse a `_catalog.py` group where one fits
(`temp_pair()`, `room_panel()`, `d2_metering()`, …).

```python
# homeassistant/mapping/eep/a5_sensors.py  (inside 0xA5 → 0x02 → …)
0x30: {
    "device_config": dcfg(),
    "entities": [
        sensor("tempC", vt("TMP", "round(1)"),
               device_class="temperature", state_class="measurement", unit="°C"),
    ],
},
```
- `vt("TMP")` / `vt("TMP", "round(1)")` builds the `value_json.TMP` template. **The field you
  reference must be a shortcut the profile decodes** — that link is enforced by a test (below).
- Eltako actuators go in `eltako.py` as `model: eltako/<name>` entries (control via `dcfg_gw(...)`).

### Shortcuts that aren't valid identifiers

Reference the profile's spec shortcut directly — `vt("TMP")`. Some spec shortcuts contain characters
that can't follow `value_json.` (e.g. `A/PM`, `LAT(MSB)`, `D/N`). For those, use Jinja **bracket
notation** instead of a dot, spelled exactly as the profile field:

```python
"{{ value_json['A/PM'] }}"
```

The spec shortcut is the single source of truth — there's no alias table. `test_mapping_profile_fields`
validates the dotted references; bracket references are trusted to match the spec spelling.

## 3. Run the tests

```bash
uv run pytest -q
```
No snapshots to regenerate. The guards that catch mistakes:
- **`test_certification`** — your decode matches the official EnOcean vectors (add a vector if you have
  one).
- **`test_profiles`** — the profile is well-formed and the family split stays lossless.
- **`test_mapping`** — the mapping leaf is well-formed and its `(rorg,func,type)` has a decodable
  profile (no orphan entities).
- **`test_mapping_profile_fields`** — every `value_json.<FIELD>` you referenced is a real profile
  field (catches typos).
- **`test_discovery_snapshot` / `test_discovery_build`** — the published HA discovery is correct.

Then add the device to your `devices.yaml` (`eep: A5-02-30` or `model: eltako/…`) to see it appear in
Home Assistant. See [`../wiki/Configuration-(devices.yaml).md`](../wiki/Configuration-(devices.yaml).md).
