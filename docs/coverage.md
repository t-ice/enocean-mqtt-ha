# Device coverage

> Static snapshot of catalogued Eltako device coverage.

**25/26** catalogued devices are mapped in the code-defined `MAPPING`. Verification tiers: 6 verified, 19 manual, 1 generic.

- **verified** — in the live fleet / confirmed from the captured telegram log
- **manual** — modelled from datasheet/EEP spec, not hardware-tested here
- **generic** — standard EEP, no Eltako-specific quirks

| Device | Category | EEP(s) | Mapped | Verification |
|---|---|---|---|---|
| FJ62 (shutter/blind) | cover | A5-3F-7F / F6-02-01 | ✅ | manual |
| FSB14 (blind/shutter actuator) | cover | A5-3F-7F / F6-02-01 | ✅ | verified |
| FSB61 (wireless shutter) | cover | A5-3F-7F / F6-02-01 | ✅ | manual |
| TF61J (Tap-radio shutter) | cover | A5-3F-7F | ✅ | manual |
| FD62 (wireless dimmer) | dimmer | A5-38-08 | ✅ | manual |
| FDG14 (DALI gateway) | dimmer | A5-38-08 | ✅ | manual |
| FSG14/1-10V (1-10V control dimmer) | dimmer | A5-38-08 | ✅ | manual |
| FUD14 (universal dimmer) | dimmer | A5-38-08 / F6-02-01 | ✅ | manual |
| FUD61NP(N) (wireless dimmer) | dimmer | A5-38-08 | ✅ | manual |
| FTS14EM (10-input module) | input | D5-00-01 | ✅ | manual |
| Air quality (CO2 + temperature + humidity) | sensor | A5-09-0C | ⬜ | manual |
| Window/door contact (FTKE, FFTE, ...) | sensor | D5-00-01 | ✅ | generic |
| FHD60SB (hand transmitter) | sensor | - | ✅ | manual |
| FSDG14 (energy/metering gateway) | sensor | A5-12-01 | ✅ | manual |
| FWG14MS (weather data gateway) | sensor | A5-13-01 | ✅ | verified |
| F4HK14 floor heating / room panel (temp + setpoint + day/night) | sensor | A5-10-06 | ✅ | verified |
| Wall rocker switch (FT55, F4T55, ...) | sensor | F6-02-01 | ✅ | verified |
| Room operating panel (temperature + setpoint) | sensor | A5-10-03 | ✅ | verified |
| Temperature + humidity sensor (FTFB, FAFT60, ...) | sensor | A5-04-02 | ✅ | manual |
| Window/door sensor with vibration/handle | sensor | A5-14-09 | ✅ | manual |
| F4SR14-LED / F4SR14 (4-channel relay) | switch | A5-38-08 / F6-02-01 | ✅ | manual |
| FL62 (wireless impulse relay) | switch | A5-38-08 / F6-02-01 | ✅ | manual |
| FMZ14 (multifunction timer, 10 channels) | switch | A5-38-08 / F6-02-01 | ✅ | manual |
| FSR14-2x / FSR14-4x / FSR14SSR | switch | A5-38-08 / F6-02-01 | ✅ | verified |
| FSR61 (wireless impulse relay) | switch | A5-38-08 / F6-02-01 | ✅ | manual |
| FTN14 (staircase off-delay timer) | switch | A5-38-08 / F6-02-01 | ✅ | manual |
