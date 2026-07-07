"""Gap-coverage tests for the protocol layer's low-level surface.

Pin the behaviour of the low-level modules (crc8, utils, the Packet framing state machine) that the
higher-level tests don't exercise directly.
"""

import enocean2mqtt.protocol.utils as u
from enocean2mqtt.protocol.constants import PARSE_RESULT
from enocean2mqtt.protocol.crc8 import calc as crc8
from enocean2mqtt.protocol.packet import Packet

# A complete, valid ESP3 4BS temperature telegram (A5-02-05); header CRC 0xEB, data CRC 0x75.
TEMPERATURE = bytearray(
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


def test_crc8_known_vectors():
    assert crc8([]) == 0
    assert crc8([0x00]) == 0x00
    # The header + data CRCs embedded in the telegram above.
    assert crc8([0x0A, 0x07, 0x01]) == 0xEB  # ESP3 header CRC
    assert crc8(TEMPERATURE[6:-1]) == 0x75  # data+optional CRC


def test_utils_combine_hex():
    assert u.combine_hex([0x01, 0x81, 0xB7, 0x44]) == 0x0181B744
    assert u.combine_hex([]) == 0
    assert u.combine_hex([0xFF]) == 0xFF


def test_utils_bitarray_roundtrip():
    assert u.to_bitarray(0x05, 8) == [False, False, False, False, False, True, False, True]
    assert u.from_bitarray(u.to_bitarray([0xA5])) == 0xA5
    assert u.from_bitarray(u.to_bitarray(0x00, 8)) == 0x00


def test_parse_msg_ok():
    status, _remaining, packet = Packet.parse_msg(bytearray(TEMPERATURE))
    assert status == PARSE_RESULT.OK
    assert packet is not None
    assert packet.rorg == 0xA5


def test_parse_msg_incomplete_on_short_buffer():
    status, _remaining, packet = Packet.parse_msg(bytearray(TEMPERATURE[:10]))
    assert status == PARSE_RESULT.INCOMPLETE
    assert packet is None


def test_parse_msg_crc_mismatch():
    corrupt = bytearray(TEMPERATURE)
    corrupt[-1] ^= 0xFF  # break the data CRC
    status, _remaining, _packet = Packet.parse_msg(corrupt)
    assert status == PARSE_RESULT.CRC_MISMATCH


def test_parse_msg_without_sync_byte_is_incomplete():
    status, _remaining, _packet = Packet.parse_msg(bytearray([0x00, 0x01, 0x02]))
    assert status == PARSE_RESULT.INCOMPLETE
