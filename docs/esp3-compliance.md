# ESP3 / ERP compliance

Status of the low-level EnOcean Serial Protocol 3 (ESP3) framing and packet handling in
`protocol/packet.py` + `protocol/constants.py`, and what is intentionally out of scope. For the
*EEP profile* (decode/encode) status see [`spec-compliance.md`](spec-compliance.md).

Reference: EnOceanSerialProtocol3 (packet types, common commands) and EnOceanRadioProtocol2 (ERP2
framing). We do **not** vendor spec text — the page anchors in `constants.py` point into the ESP3 PDF.

## Packet types (ESP3 §Packet Type)

`Packet.parse_msg()` frames every ESP3 packet (sync byte, header + data CRC8) and returns a typed
object for the packet types the daemon acts on; the rest are returned as a generic `Packet` with
raw `data`/`optional` (parsed, not interpreted).

| Type | Code | Handling |
|---|---|---|
| `RADIO_ERP1` | 0x01 | **Typed** `RadioPacket` (+ `UTETeachInPacket` for UTE teach-in) — the fleet's telegrams. |
| `RESPONSE` | 0x02 | **Typed** `ResponsePacket` — answers to the common commands we send (see below). |
| `EVENT` | 0x04 | **Typed** `EventPacket` — acted on: `CO_DUTYCYCLE_LIMIT`, `CO_TRANSMIT_FAILED`, `CO_READY`. |
| `RADIO_SUB_TEL` 0x03, `COMMON_COMMAND` 0x05, `SMART_ACK_COMMAND` 0x06, `REMOTE_MAN_COMMAND` 0x07, `RADIO_MESSAGE` 0x09, `RADIO_ERP2` 0x0A, `RADIO_802_15_4` 0x10, `COMMAND_2_4` 0x11 | — | Generic raw `Packet` (received) — not interpreted. `COMMON_COMMAND` is *sent* (below). |

## Common commands (ESP3 §Common Command) — what we send

The daemon issues common commands on startup to identify the transceiver. ESP3 **responses carry no
command identifier** — they are correlated to requests purely by send order — so the daemon sends
them in a fixed sequence and records that order in a FIFO (`Communicator._pending_cmd`); each
`RESPONSE` is routed to the command it answers.

| Command | Code | Response we decode |
|---|---|---|
| `CO_RD_VERSION` | 0x03 | `return_code + app_ver(4) + api_ver(4) + chip_id(4) + chip_ver(4) + app_desc(16)` → stick app/API version + chip id (diagnostics, non-gating). |
| `CO_RD_IDBASE` | 0x08 | `return_code + base_id(4) [+ remaining_write_cycles(1)]` → the Base ID used as the default sender. |
| `CO_WR_REPEATER` | 0x09 | Sent (enable + level) when the `repeater` option is `1`/`2`; response is just a return code. |
| `CO_RD_REPEATER` | 0x0A | `return_code + enable(1) + level(1)` → the active repeater level (diagnostic). |
| `CO_RD_DUTYCYCLE_LIMIT` | 0x23 | `return_code + available(1, %) + …` → remaining TX duty-cycle budget (diagnostic). |

`Packet.create_common_command(code, *payload)` builds these; the codes live in
`COMMON_COMMAND_CODE`. Every common command yields exactly one `RESPONSE` (even `NOT_SUPPORTED`), so
the send-order FIFO stays aligned; a command the transceiver doesn't support leaves the field unset.

### Handled

- **Flexible Base ID parse.** Per ESP3 the `CO_RD_IDBASE` response may append a *remaining write
  cycles* byte (5 data bytes after the return code). The parse takes the first 4 bytes with a
  `len >= 4` check, so transceivers that append that byte are accepted.
- **`CO_RD_VERSION`.** The stick's app/API version and chip id are read at startup, logged, and
  published on the `bridge/stats` topic.
- **Controller config + diagnostics.** The repeater level and remaining TX duty-cycle are read at
  startup (and the configured repeater level applied); both are published as diagnostics.
- **Duty-cycle / transmit EVENTs.** `CO_DUTYCYCLE_LIMIT` and `CO_TRANSMIT_FAILED` events are handled
  (logged + reflected in diagnostics).
- **Order-correlated response routing.** Responses are matched to the commands we sent by order (ESP3
  has no command echo), so multiple startup commands are attributed to the right response.
- **Secure telegrams** (`SEC` 0x30 / `SEC_ENCAPS` 0x31 / `SEC_TI` 0x35), per *Security of EnOcean
  Radio Networks v3.02* — implemented in `protocol/security.py` and verified against the Annex A.4
  known-answer vectors (no hardware needed):
  - **Decode** — VAES decryption + AES-CMAC auth + rolling-code (RLC) replay protection (24/32-bit
    RLC, 3/4-byte CMAC), driven by per-device `security:`/`key:`/`rlc:`/`slf:` config. `slf` defaults
    to `0x8B` (24-bit implicit RLC + 3-byte CMAC, as PTM215 uses); teach-in-provisioned devices carry
    their own SLF. The RLC is modular over its width (§3.5) — it wraps to 0 at the max, never faults.
  - **Teach-in** — `SEC_TI` reassembly (+ the PSK path via the `secure_psk` option) auto-provisions a
    secure device in learn mode; the bridge can also *send* a teach-in (`build_teach_in`).
  - **Transmit** — outbound telegrams for a `security:` device are VAES-encrypted + MAC'd; already-
    secure/control RORGs (0x30/0x31/0x33/0x35) and signal telegrams (0xD0) are never re-wrapped.
  - **Durable RLC** — inbound/outbound rolling codes persist to the device store and restore on start.

## Out of scope (by design)

The deployed fleet uses ERP1 transceivers (USB300 / FAM-USB class), so the following are deliberately
**not** implemented:

- **ERP2 framing** (`RADIO_ERP2` 0x0A) — different header/addressing. Not decoded.
- **Smart Ack** (`SMART_ACK_COMMAND`, mailbox) and **Remote Management** (`REMOTE_MAN_COMMAND`).
- **AES-CBC / 2-byte CMAC** — not supported; the secure scheme is VAES + 3/4-byte CMAC only.

The corresponding `PACKET` / `RORG` enum members are **retained as reference** (they document the
protocol space and are pinned by the vendored characterization tests); "unused" here means
*reserved*, not *missed*.

## Known limitations

- **ERP2 decode** — not implemented; it needs a distinct frame parser, and is only relevant for an
  ERP2 transceiver.
- **Header-corruption resync.** On a data-CRC mismatch `parse_msg` drops the framed length and the
  transceiver read loop re-parses the remainder until a good frame emerges (covered by
  `tests/protocol/test_malformed.py`). A corrupt *header* (an untrustworthy length) is the harder
  case: a naive "resync to the next `0x55`" can land inside a payload that happens to contain `0x55`,
  so robust handling belongs at the streaming read-loop level rather than the single-shot parser.
