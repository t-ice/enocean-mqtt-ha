"""Transceiver adapters: ESP3 framing (shared base), chunk boundaries, disconnect, send, factory."""

import pytest

from enocean2mqtt.adapters.transceiver.factory import make_transceiver
from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.adapters.transceiver.serial_link import SerialLink
from enocean2mqtt.protocol.packet import RadioPacket

# A complete, valid ESP3 4BS temperature telegram (A5-02-05).
TEMPERATURE = bytes(
    [
        0x55,
        0x00,
        0x0A,
        0x07,
        0x01,
        0xEB,
        0xA5,
        0x00,
        0x00,
        0x55,
        0x08,
        0x01,
        0x81,
        0xB7,
        0x44,
        0x00,
        0x01,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0x2D,
        0x00,
        0x75,
    ]
)


class FakeReader:
    """Feeds preset byte chunks; an empty return signals EOF (connection drop)."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _n):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class FakeWriter:
    def __init__(self):
        self.written = bytearray()
        self.closed = False

    def write(self, data):
        self.written.extend(data)

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


def _transceiver():
    """A StreamTransceiver instance for framing tests (link type is irrelevant to framing)."""
    return Ser2netLink("socket://127.0.0.1:3000")


async def _collect(transport, expected):
    """Collect up to *expected* packets, tolerating the terminal ConnectionError."""
    out = []
    try:
        async for packet in transport.read_packets():
            out.append(packet)
            if len(out) >= expected:
                break
    except ConnectionError:
        pass
    return out


async def test_single_frame():
    t = _transceiver()
    t._reader = FakeReader([TEMPERATURE])
    packets = await _collect(t, 1)
    assert len(packets) == 1
    # The code engine also surfaces the 4BS learn bit (LRNB); the daemon drops it before MQTT.
    assert packets[0].parse_eep(0x02, 0x05) == ["LRNB", "TMP"]


async def test_two_frames_in_one_chunk():
    t = _transceiver()
    t._reader = FakeReader([TEMPERATURE + TEMPERATURE])
    packets = await _collect(t, 2)
    assert len(packets) == 2


async def test_frame_split_across_chunks():
    t = _transceiver()
    # Split mid-telegram: the first chunk is incomplete, the packet only completes on the second.
    t._reader = FakeReader([TEMPERATURE[:10], TEMPERATURE[10:]])
    packets = await _collect(t, 1)
    assert len(packets) == 1
    assert packets[0].rorg == 0xA5


async def test_crc_mismatch_is_skipped_then_recovers():
    corrupt = bytearray(TEMPERATURE)
    corrupt[-1] ^= 0xFF  # break the data CRC of the first frame
    t = _transceiver()
    t._reader = FakeReader([bytes(corrupt) + TEMPERATURE])
    packets = await _collect(t, 1)
    # The bad frame is dropped; the following good frame still parses.
    assert len(packets) == 1
    assert packets[0].rorg == 0xA5


async def test_disconnect_raises_connection_error():
    t = _transceiver()
    t._reader = FakeReader([])  # immediate EOF
    with pytest.raises(ConnectionError):
        async for _ in t.read_packets():
            pass


async def test_send_serialises_packet():
    t = _transceiver()
    writer = FakeWriter()
    t._writer = writer
    packet = RadioPacket.create(
        rorg=0xA5, rorg_func=0x02, rorg_type=0x05, sender=[0x01, 0x81, 0xB7, 0x44], TMP=26.7
    )
    await t.send(packet)
    assert writer.written[0] == 0x55  # ESP3 sync byte
    assert bytes(writer.written) == bytes(bytearray(packet.build()))


async def test_close_is_safe_without_connection():
    t = _transceiver()
    await t.close()  # must not raise when never connected


def test_ser2net_split_hostport():
    assert Ser2netLink._split_hostport("socket://192.168.10.8:3000") == ("192.168.10.8", 3000)
    assert Ser2netLink._split_hostport("192.168.10.8:3000") == ("192.168.10.8", 3000)


def test_factory_selects_link_by_connection():
    assert isinstance(make_transceiver("192.168.10.31:3000"), Ser2netLink)
    assert isinstance(make_transceiver("socket://host:3000"), Ser2netLink)
    assert isinstance(make_transceiver("/dev/ttyUSB0"), SerialLink)


def _dimmer_packet():
    return RadioPacket.create(
        rorg=0xA5, rorg_func=0x02, rorg_type=0x05, sender=[0x01, 0x81, 0xB7, 0x44], TMP=20.0
    )


async def test_send_pacing_spaces_bursts():
    """With a send interval, back-to-back sends are spaced; a lone/spaced-out send never waits."""
    t = Ser2netLink("socket://127.0.0.1:3000", send_interval_s=0.1)
    t._writer = FakeWriter()
    now = [0.0]
    slept = []
    t._clock = lambda: now[0]

    async def fake_sleep(d):
        slept.append(d)
        now[0] += d  # advance virtual time as a real sleep would

    t._sleep = fake_sleep
    pkt = _dimmer_packet()

    await t.send(pkt)  # first send: deadline is in the past → no wait
    assert slept == []
    await t.send(pkt)  # immediately again → must wait the interval
    assert slept == [pytest.approx(0.1)]
    now[0] += 0.5  # let enough time pass
    await t.send(pkt)  # spaced out → no further wait
    assert slept == [pytest.approx(0.1)]
    # all three telegrams were still written
    assert bytes(t._writer.written).count(0x55) == 3


async def test_send_pacing_disabled_by_default():
    """Default interval 0 → sends are never delayed."""
    t = Ser2netLink("socket://127.0.0.1:3000")
    t._writer = FakeWriter()
    slept = []

    async def fake_sleep(d):
        slept.append(d)

    t._sleep = fake_sleep
    pkt = _dimmer_packet()
    await t.send(pkt)
    await t.send(pkt)
    assert slept == []
