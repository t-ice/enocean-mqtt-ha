# Changelog

## 1.0.4 — fix Eltako blind position wrong after a Home Assistant restart

- **Fix:** An Eltako blind/shutter (FSB14, FSB61, FSB61NP, FJ62, TF61J) could come back showing the
  wrong position after a Home Assistant restart — e.g. reporting the shaded position (10 %) while
  physically fully open. The cover's `position_topic` was the `+` wildcard, which also matches the
  device's `…/a5` and `…/f6` state topics; each carries its own retained `POS` (from set_position,
  and from the F6 end-position telegrams respectively). After a full open the fresh `POS=100` landed
  on `…/f6` while a stale `POS` from the last set_position stayed retained on `…/a5`; on a restart
  both retained messages replayed and the last one to arrive won the position restore. The absolute
  position is now published to a single dedicated retained `…/pos` topic — on every change and, from
  the store, on connect — and `position_topic` points at it, so the restored value is deterministic.
- **Fix:** `db_upsert_device` rebuilt the device row from scratch on every discovery run (each
  reconnect), wiping runtime state not part of the discovered identity — the persisted cover
  `position` and secure `rlc`/`rlc_snd`. It now merges onto the existing row, so that state survives
  a reconnect.

## 1.0.3 — fix Eltako blind opening fully when re-commanded to its current position

- **Fix:** The server-side `set_position_template` for Eltako blind/shutter actuators (FSB14,
  FSB61, FSB61NP, FJ62, TF61J) derived the movement direction from `step = target − current`. When
  the target equalled the current position (`step == 0`) it emitted an *up* command (`DB1=1`) with a
  drive time of 0 — and a zero drive time makes the actuator run to the endstop, so the blind fully
  opened instead of staying put. Re-commanding a blind to the position it already held (e.g. a
  shading automation firing while the blind was already shaded) drove it fully open. The template
  now emits a stop payload for `step == 0` and clamps the drive time to a minimum of 1 (0.1 s) so a
  tiny step can never round down to a run-to-endstop command.

## 1.0.2 — fix duplicate MQTT discovery for Eltako actuators

- **Fix:** Multi-RORG model devices (Eltako FSB14/FSR14 and their Series-61/TF61 siblings) expand
  into two derived sensors (`…/a5` + `…/f6`) that share one device id. Discovery published each
  config topic twice, producing duplicated "device database" log lines and redundant retained MQTT
  publishes on every startup. Discovery now runs once per device; entities are unchanged.

## 1.0.1

Maintenance release — no functional changes to the add-on.

- **Dependencies:** cryptography 49.0.0, ruamel.yaml 0.19.1.
- **CI / build tooling:** GitHub Actions (docker build-push v7, login/buildx/codeql v4,
  hadolint-action 3.3.0) and the uv builder image (0.11.28); pre-commit hooks refreshed
  (ruff, yamllint, hadolint, shellcheck, pre-commit-hooks v6).
- **Tests / docs:** run.sh guard-test assertions now actually fail on regression (bats SC2314) and
  the .bats file is shellchecked again; documented the VAES ECB block primitive as a CodeQL false
  positive.

## 1.0.0

A Home Assistant add-on that bridges **EnOcean** devices to **MQTT**.

- **Whole EEP range decoded** — RPS `F6`, 1BS `D5`, 4BS `A5` and VLD `D2`, from a code-defined EEP
  engine validated against the official EnOcean certification vectors. Entities auto-appear via
  **MQTT discovery**.
- **First-class Eltako support** — one-line `model: eltako/…` entries for FSR14 relays/lights, FUD14
  dimmers and FSB14 blinds/covers (plus their Series-61/TF61 siblings), including **cover-position
  tracking that survives restarts**.
- **Transmit / control** — Eltako A5-38-08 switch/light + A5-3F-7F covers, D2-05 blinds, D2-01
  relays/dimmers, and F6 rocker emulation with one-click momentary **AI / AO / BI / BO** press buttons.
- **Secure telegrams (AES/VAES)** per *Security of EnOcean Radio Networks v3.02* — decode
  (VAES + AES-CMAC + rolling-code replay protection, 24/32-bit RLC, 3/4-byte CMAC), hands-free
  **teach-in** (`SEC_TI`, incl. the PSK path via the `secure_psk` option), **transmit**, and
  **durable rolling codes** that survive restarts. Configure a device by hand with `security: true` +
  `key:`, or let learn mode provision it.
- **Transceiver connection** — a local USB stick (`device` serial path, e.g. `/dev/ttyUSB0`) **or** a
  remote ser2net endpoint (`tcp` `host:port`, e.g. a Raspberry Pi); TCP wins if both are set. No `socat`/PTY bridge; the
  daemon self-heals transceiver and MQTT drops with exponential-backoff reconnect.
- **Teach-in** via a Home Assistant LEARN button (auto-off timeout for safety): UTE and secure devices
  are auto-provisioned and appended to your `devices.yaml` (comments/formatting preserved).
- **Transceiver diagnostics** — firmware/chip-id, repeater level (with a `repeater` option), available
  TX duty-cycle % and a transmit-failures counter, published as diagnostic sensors.
- **Availability (LWT), RSSI and last-seen** per device; YAML device list with load-time validation.
- **Ships as a prebuilt multi-arch image** (`aarch64`, `amd64`) from GHCR with a signed
  build-provenance attestation, and runs confined by an **AppArmor** profile.
