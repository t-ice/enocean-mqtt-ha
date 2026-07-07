"""Encode tests: the daemon's command/raw_data send path must produce the exact bytes the Eltako
documentation specifies.

Command bytes (authoritative): FSR14 ON=01:00:00:09 / OFF=01:00:00:08;
FSB14 shutter up=00:00:01:08 / down=00:00:02:08 / stop=00:00:00:08 (A5-3F-7F DB1 direction).
"""

from unittest import mock

import pytest

from enocean2mqtt.protocol.packet import RadioPacket


@pytest.fixture
def com():
    from enocean2mqtt.application.daemon import EnoceanDaemon

    conf = {"mqtt_host": "localhost", "enocean_port": "socket://127.0.0.1:3000"}
    c = EnoceanDaemon(conf, [])
    # The async transport is the send sink; capture packets instead of doing I/O.
    c._transport.send = mock.AsyncMock()
    return c


def _sent_packet(com):
    assert com._transport.send.called, "no packet was sent"
    return com._transport.send.call_args.args[0]


SENDER = 0xFFAE7C90
DEST = [0xFF, 0x94, 0xCE, 0x98]


@pytest.mark.parametrize(
    "rorg,func,type_,raw,expected_payload",
    [
        (0xA5, 0x38, 0x08, "01:00:00:09", [0x01, 0x00, 0x00, 0x09]),  # FSR14 ON
        (0xA5, 0x38, 0x08, "01:00:00:08", [0x01, 0x00, 0x00, 0x08]),  # FSR14 OFF
        (0xA5, 0x3F, 0x7F, "00:00:01:08", [0x00, 0x00, 0x01, 0x08]),  # FSB14 UP
        (0xA5, 0x3F, 0x7F, "00:00:02:08", [0x00, 0x00, 0x02, 0x08]),  # FSB14 DOWN
        (0xA5, 0x3F, 0x7F, "00:00:00:08", [0x00, 0x00, 0x00, 0x08]),  # FSB14 STOP
    ],
)
async def test_raw_data_encoding_and_sender(com, rorg, func, type_, raw, expected_payload):
    sensor = {"rorg": rorg, "func": func, "type": type_, "sender": SENDER, "raw_data": raw}
    await com._send_packet(sensor, DEST)
    pkt = _sent_packet(com)
    assert pkt.data[0] == rorg
    assert pkt.data[1:5] == expected_payload  # payload = exact command bytes
    assert pkt.data[5:9] == [0xFF, 0xAE, 0x7C, 0x90]  # sender = base_id + offset, placed correctly


async def test_default_data_int_path(com):
    """default_data as an int literal writes the 4 payload bytes verbatim (no EEP encoding)."""
    sensor = {
        "name": "enocean2mqtt/X",
        "rorg": 0xA5,
        "func": 0x38,
        "type": 0x08,
        "sender": SENDER,
        "default_data": "0xDEADBEEF",
    }
    await com._send_packet(sensor, DEST)
    pkt = _sent_packet(com)
    assert pkt.data[1:5] == [0xDE, 0xAD, 0xBE, 0xEF]
    assert pkt.data[5:9] == [0xFF, 0xAE, 0x7C, 0x90]


async def test_default_data_property_path(com):
    """default_data as a JSON object is EEP-encoded (set_eep) and the status byte is applied."""
    sensor = {
        "name": "enocean2mqtt/X",
        "rorg": 0xA5,
        "func": 0x02,
        "type": 0x05,
        "sender": SENDER,
        "default_data": '{"TMP": 21.5}',
    }
    await com._send_packet(sensor, DEST)
    pkt = _sent_packet(com)
    # 21.5 °C EEP-encodes to raw byte 117 (A5-02-05 scaling), placed in DB3; status byte applied.
    assert pkt.parsed["TMP"]["raw_value"] == 117
    assert pkt.data[3] == 117
    assert pkt.data[-1] == pkt.status


async def test_reply_packet_learn_response(com):
    """A learn-response copies the incoming EEP/manufacturer bytes and sets the 0xF0 ack flag."""
    in_packet = RadioPacket(
        1,
        data=[0xA5, 0x08, 0x28, 0x46, 0x80, 0x01, 0x8A, 0x7B, 0x30, 0x00],  # a 4BS teach-in
        optional=[0, 255, 255, 255, 255, 0x49, 0],
    )
    assert in_packet.learn is True
    sensor = {"rorg": 0xA5, "func": 0x02, "type": 0x05, "sender": SENDER}
    await com._reply_packet(in_packet, sensor)
    pkt = _sent_packet(com)
    assert pkt.data[1:4] == [0x08, 0x28, 0x46]  # EEP/manufacturer bytes copied from the request
    assert pkt.data[4] == 0xF0  # learn-ack flag
    assert pkt.destination == in_packet.sender


async def test_learn_flag_only_when_requested(com):
    base = {"rorg": 0xA5, "func": 0x38, "type": 0x08, "sender": SENDER, "raw_data": "01:00:00:09"}
    await com._send_packet(dict(base), DEST)
    normal = _sent_packet(com)

    com._transport.send.reset_mock()
    await com._send_packet({**base, "learn": True}, DEST)
    learned = _sent_packet(com)

    # A learn telegram differs from a normal data telegram (LRN bit handling in RadioPacket.create).
    assert getattr(normal, "learn", False) is False
    assert getattr(learned, "learn", True) is True
