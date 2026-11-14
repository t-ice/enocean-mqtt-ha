"""ESP3 resync: a stray 0x55 or a corrupt frame must never hold back the real telegrams behind it.

Regression for the review finding of 2026-11: ``parse_msg`` trusted the length of an unchecked
header and waited for up to 64 KB before looking at the header CRC — a fake sync byte inside a
half-received frame (typical right after a ser2net connect) stalled every telegram behind it.
"""

from __future__ import annotations

import asyncio
import itertools

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.protocol import crc8
from enocean2mqtt.protocol.constants import COMMON_COMMAND_CODE, PARSE_RESULT
from enocean2mqtt.protocol.packet import Packet

# Real frames of three packet types: a radio telegram (A5-02-05), a response, a common command.
TEMPERATURE = bytes.fromhex("55000a0701eba5000055080181b7440001ffffffff2d0075")
RESPONSE_OK = bytes(Packet(0x02, data=[0x00]).build())
COMMAND = bytes(Packet.create_common_command(COMMON_COMMAND_CODE.CO_RD_VERSION).build())
FRAMES = (TEMPERATURE, RESPONSE_OK, COMMAND)


def _parse_all(buf):
    """Run parse_msg until it needs more bytes; return the produced packets + what is left."""
    packets = []
    while True:
        status, buf, packet = Packet.parse_msg(buf)
        if status == PARSE_RESULT.INCOMPLETE:
            return packets, buf
        if status == PARSE_RESULT.OK:
            packets.append(packet)


def test_fixture_frames_are_valid():
    for frame in FRAMES:
        packets, rest = _parse_all(list(frame))
        assert len(packets) == 1 and rest == []


def test_stray_sync_byte_with_huge_length_does_not_hold_back_real_frames():
    """The case reproduced in the review: 50 valid frames used to stay stuck behind it."""
    junk = [0x12, 0x55, 0xFF, 0x00, 0x07, 0x01]  # fake header claiming 0xFF00 data bytes
    packets, _ = _parse_all(junk + list(COMMAND) * 50)
    assert len(packets) == 50


def test_bad_header_crc_is_detected_after_six_bytes():
    """Header CRC is checked as soon as it is there — not after the (bogus) length arrives."""
    status, remaining, packet = Packet.parse_msg([0x55, 0xFF, 0xFF, 0xFF, 0x01, 0x00])
    assert status == PARSE_RESULT.CRC_MISMATCH and packet is None
    assert remaining == [0xFF, 0xFF, 0xFF, 0x01, 0x00]  # only the sync byte dropped


def test_partial_header_is_incomplete():
    status, remaining, _ = Packet.parse_msg([0x55, 0x00, 0x0A])
    assert status == PARSE_RESULT.INCOMPLETE and remaining == [0x55, 0x00, 0x0A]


def test_header_passing_crc_by_chance_does_not_stall_the_frames_behind_it():
    """A junk header passing its CRC (1 in 256) and claiming far more bytes than will come: as soon
    as a complete valid frame follows, the parser resyncs instead of awaiting the phantom length."""
    header = [0xF0, 0x00, 0x00, 0x01]  # claims 61440 data bytes
    fake = [0x55, *header, crc8.calc(header)]
    packets, _ = _parse_all(fake + list(COMMAND) * 3)
    assert len(packets) == 3


def test_partial_real_frame_is_still_awaited():
    """The resync must not fire on an honest partial frame (nothing valid follows yet)."""
    status, remaining, _ = Packet.parse_msg(list(TEMPERATURE[:15]))
    assert status == PARSE_RESULT.INCOMPLETE and remaining == list(TEMPERATURE[:15])


def test_header_passing_crc_by_chance_cannot_swallow_the_next_frame():
    """A junk header that passes its CRC (1 in 256) but claims a length overlapping a real frame:
    the data CRC fails, only the sync byte is skipped, and the real frame is still found."""
    header = [0x00, 0x20, 0x00, 0x01]  # claims 32 data bytes
    fake = [0x55, *header, crc8.calc(header)]
    packets, _ = _parse_all(fake + list(TEMPERATURE) + list(COMMAND) * 2)
    assert [p.packet_type for p in packets] == [0x01, 0x05, 0x05]


# --- property: arbitrary junk + arbitrary chunking through the real read loop -------------------


class _ChunkReader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _n):
        return self._chunks.pop(0) if self._chunks else b""


def _read_through_stream(data: bytes, cuts: list[int]):
    """Feed *data* split at *cuts* through StreamTransceiver.read_packets; return the packets."""
    points = sorted({c % (len(data) + 1) for c in cuts} | {0, len(data)})
    chunks = [data[a:b] for a, b in itertools.pairwise(points) if b > a]
    link = Ser2netLink("socket://127.0.0.1:3000")
    link._reader = _ChunkReader(chunks)

    async def collect():
        out = []
        try:
            async for packet in link.read_packets():
                out.append(packet)
        except ConnectionError:  # EOF after the last chunk
            pass
        return out

    return asyncio.run(collect())


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    junk=st.lists(st.sampled_from([0x55, 0x00, 0xFF, 0x0A, 0x07, 0x01]) | st.integers(0, 255)),
    frames=st.lists(st.sampled_from(FRAMES), min_size=1, max_size=8),
    cuts=st.lists(st.integers(min_value=0, max_value=10_000), max_size=12),
)
def test_every_real_frame_after_junk_is_recovered_in_order(junk, frames, cuts):
    """Whatever precedes them and however the stream is chunked, the real frames come out in order.

    Junk may itself happen to contain a CRC-valid frame (a vanishingly rare but legal outcome), so
    the real frames must form the *tail* of the output rather than all of it.
    """
    data = bytes(junk) + b"".join(frames)
    packets = _read_through_stream(data, cuts)
    got = [bytes(p.build()) for p in packets]
    assert got[len(got) - len(frames) :] == list(frames)
