#!/usr/bin/env python3
"""A fake ser2net / EnOcean-stick endpoint for integration tests.

Runs INSIDE the add-on image (so it frames ESP3 with the real ``Packet.build``), presenting a raw
TCP port exactly like the Raspberry Pi's ser2net does. On each client (the daemon) connection it:

  1. answers the daemon's startup common commands *by command code* — ``CO_RD_VERSION`` (0x03) with
     a version RESPONSE and ``CO_RD_IDBASE`` (0x08) with a Base-ID RESPONSE — so the daemon learns
     its sender id and unblocks HA discovery. The Base-ID reply deliberately appends the optional
     "remaining write cycles" byte, reproducing the transceivers that broke the old length-4 parser.
  2. replays the configured captured telegrams (``received_*.json`` fixtures) as ESP3 frames, and
  3. keeps reading, appending every ESP3 frame the daemon SENDS to a capture file (hex per line),
     so a test can assert an inbound MQTT command produced the expected telegram on the wire.

Config via env: EMU_PORT (3000), EMU_BASE_ID (hex, e.g. FFAE7C80), EMU_TELEGRAMS (comma-separated
fixture paths), EMU_CAPTURE (path to append sent frames), EMU_REPLAY_DELAY (seconds before replay).
"""

from __future__ import annotations

import asyncio
import json
import os

from enocean2mqtt.protocol.constants import COMMON_COMMAND_CODE, PACKET, PARSE_RESULT
from enocean2mqtt.protocol.packet import Packet

PORT = int(os.environ.get("EMU_PORT", "3000"))
BASE_ID = [int(os.environ.get("EMU_BASE_ID", "FFAE7C80")[i : i + 2], 16) for i in (0, 2, 4, 6)]
TELEGRAMS = [p for p in os.environ.get("EMU_TELEGRAMS", "").split(",") if p]
CAPTURE = os.environ.get("EMU_CAPTURE", "/tmp/emu_capture.hex")
REPLAY_DELAY = float(os.environ.get("EMU_REPLAY_DELAY", "1.5"))


def _base_id_frame() -> bytes:
    # CO_RD_IDBASE RESPONSE: [RETURN_CODE.OK, <4-byte base id>, <remaining write cycles>].
    # The trailing 0xFF is the optional byte real sticks append — it must not confuse the parser.
    data = [0x00, *BASE_ID, 0xFF]
    return bytes(bytearray(Packet(PACKET.RESPONSE, data=data, optional=[]).build()))


def _version_frame() -> bytes:
    # CO_RD_VERSION RESPONSE: RETURN_CODE.OK + app(4) + api(4) + chip id(4) + chip ver(4) + desc(16)
    desc = list(b"EMU300".ljust(16, b"\x00"))
    data = [0x00, 2, 5, 3, 0, 1, 8, 0, 0, 0x01, 0x2D, 0x8C, 0x9F, 3, 1, 0, 0, *desc]
    return bytes(bytearray(Packet(PACKET.RESPONSE, data=data, optional=[]).build()))


_COMMAND_RESPONSES = {
    COMMON_COMMAND_CODE.CO_RD_VERSION: _version_frame,
    COMMON_COMMAND_CODE.CO_RD_IDBASE: _base_id_frame,
}


def _telegram_frame(path: str) -> bytes:
    fx = json.load(open(path, encoding="utf-8"))
    pkt = Packet(fx["packet_type"], data=list(fx["data"]), optional=list(fx["optional"]))
    return bytes(bytearray(pkt.build()))


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    print("emulator: daemon connected", flush=True)

    async def replay() -> None:
        await asyncio.sleep(REPLAY_DELAY)  # (2) let discovery settle, then replay telegrams
        for path in TELEGRAMS:
            writer.write(_telegram_frame(path))
            await writer.drain()
            print(f"emulator: replayed {os.path.basename(path)}", flush=True)

    # Fire-and-forget: the task stays referenced by the loop below for the connection's lifetime.
    asyncio.create_task(replay())  # noqa: RUF006

    buf: list[int] = []
    while True:  # read the daemon's frames
        chunk = await reader.read(1024)
        if not chunk:
            break
        buf.extend(chunk)
        while True:
            status, buf, pkt = Packet.parse_msg(buf)
            if status == PARSE_RESULT.INCOMPLETE:
                break
            if status != PARSE_RESULT.OK or pkt is None:
                continue
            if pkt.packet_type == PACKET.COMMON_COMMAND and pkt.data:
                # (1) answer the startup handshake by command code, in the order received.
                make_response = _COMMAND_RESPONSES.get(pkt.data[0])
                if make_response is not None:
                    writer.write(make_response())
                    await writer.drain()
                    print(f"emulator: answered common command 0x{pkt.data[0]:02X}", flush=True)
                continue
            # (3) capture radio frames the daemon sends, for command round-trip asserts.
            frame = bytes(bytearray(pkt.build()))
            with open(CAPTURE, "a", encoding="utf-8") as fh:
                fh.write(frame.hex() + "\n")
            print(f"emulator: captured sent frame {frame.hex()}", flush=True)


async def main() -> None:
    open(CAPTURE, "w", encoding="utf-8").close()  # truncate
    server = await asyncio.start_server(_handle, "0.0.0.0", PORT)
    print(f"emulator: listening on :{PORT} (base id {bytes(BASE_ID).hex()})", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
