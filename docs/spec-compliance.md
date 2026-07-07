# EEP specification compliance

Status of the EnOcean Equipment Profiles (EEP) implementation against the official EnOcean Alliance
specification.

## The engine

The add-on decodes and encodes EnOcean telegrams exclusively via the **code-defined EEP engine**
(`src/enocean2mqtt/protocol/profiles/`). Profiles are checked-in Python dict literals — a `PROFILES`
registry covering the **F6 / D5 / A5 / D2** RORG families — and `engine.py` decodes over it by
evaluating each profile case's bit-predicates against the received telegram. No XML is parsed at
runtime.

## Certification

The engine is validated against the **official EnOcean certification vectors** (checked in under
`tests/fixtures/certification/`). `tests/protocol/test_certification.py` runs every vector through
the engine and asserts a pass rate of **≥95 %** of assertable values. The residual few percent are
official-vector data quirks (e.g. bogus "mid" values, ½-step "ideal" meter readings where the engine
value is the more correct one) and a handful of composite multi-byte fields.

Encode is the **byte-exact inverse of decode**: the same profile definition drives both directions,
so a command encoded for an actuator reproduces exactly the layout the device expects. This is what
powers transmit/control — Eltako A5-38-08 switch/light + A5-3F-7F covers, D2-01 relays/dimmers, D2-05
blinds, and F6 rocker emulation all encode through the same engine. The byte-exact actuator tests
(`tests/daemon/test_send_encode.py`) guard this for the deployed fleet.

Secure (AES/VAES) telegrams wrap these EEP payloads at the ESP3 layer rather than in the profile
engine; their compliance (VAES, AES-CMAC, rolling code, teach-in) is documented in
[`esp3-compliance.md`](esp3-compliance.md).

## F6-02-01 rockers

A few profiles have two published transcriptions; where the runtime's HA mapping depends on a
specific field layout the catalog uses the community-derived layout — **F6-02-01** rocker switches,
**A5-3F-7F** generic DB fields, and **A5-13-01** weather sub-telegrams (each noted inline in
`profiles.py`). For F6-02-01 this preserves the full rocker layout (`R1`/`R2`/`SA`) that HA
templates read, including for U-messages.

## Spec-verified (not hardware-verified)

A few profiles are transcribed from the EEP spec but not yet validated against a real device or an
official vector (there are none for them) — the bit layouts come from the public EEP 2.6.x tables.
The A5-10 room panels, A5-05 barometric sensors, and the **D2-50** Heat-Recovery-Ventilation status
decode (message-type-multiplexed; exposes outdoor/supply/room/exhaust temperature, supply/exhaust air
flow and fan speed, and the operating mode) fall in this group. If a reading looks wrong on real
hardware, it is a localized profile fix.

## Out of scope

Generic Profiles (GP), ERP2 framing, MSC (D1), Signal (D0) and ADT (A6) are not implemented — the
official machine-readable profile and certification data for these are not part of the corpus the
engine is built and validated against.
