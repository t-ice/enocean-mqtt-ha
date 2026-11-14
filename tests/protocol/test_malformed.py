"""Malformed / truncated telegrams must not crash the parser.

Guards the "list index out of range" hardening on bad packets: a garbage buffer should be reported
as not-parsed rather than raising.
"""

import pytest

from enocean2mqtt.protocol.constants import PARSE_RESULT
from enocean2mqtt.protocol.packet import Packet, RadioPacket

# A 4BS telegram with valid framing + CRCs, used as the "good" frame in the resync tests below.
TEMPERATURE = [
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


@pytest.mark.parametrize(
    "buf",
    [
        bytearray(),
        bytearray([0x55]),  # sync byte only
        bytearray([0x55, 0x00, 0x07, 0x07]),  # truncated header
        bytearray([0x55] + [0xFF] * 20),  # garbage payload
    ],
)
def test_parse_msg_never_raises(buf):
    # Static parser: returns (parse_result, remaining_buffer, packet) and must not raise.
    result = Packet.parse_msg(buf)
    assert isinstance(result, (list, tuple))


# NOTE: parse_eep() assumes a structurally valid RadioPacket — in the daemon it is only ever
# called on packets already produced by the communicator (correct length, sender, status).
# Raw/truncated bytes are handled one layer down by parse_msg (tested above). The real risk at
# the parse_eep layer is selecting an unknown/wrong profile on an otherwise valid telegram.
VALID_A5 = [0xA5, 0x14, 0x11, 0x0A, 0x28, 0x05, 0x9E, 0xD7, 0x9A, 0x00]  # real weather telegram


@pytest.mark.parametrize("func,type_", [(0x99, 0x99), (0x13, 0x99), (0x02, 0x01)])
def test_parse_eep_unknown_profile_is_safe(func, type_):
    p = RadioPacket(1, data=list(VALID_A5), optional=[0, 255, 255, 255, 255, 73, 0])
    try:
        p.select_eep(func, type_)
        p.parse_eep()
    except (IndexError, KeyError):
        pytest.fail("parse_eep raised on a valid packet with an unknown profile")
    except Exception:
        pass  # other benign outcomes are fine; the point is no IndexError/KeyError crash


def _parse_all(buf):
    """Run parse_msg over *buf* until it needs more bytes; return the packets it produced."""
    packets = []
    while True:
        status, buf, packet = Packet.parse_msg(buf)
        if status == PARSE_RESULT.INCOMPLETE:
            return packets
        if status == PARSE_RESULT.OK:
            packets.append(packet)


def test_data_crc_error_drops_the_bad_frame_and_recovers_the_next():
    """Only the data CRC is wrong: the bad frame yields nothing and the next frame is recovered.

    The parser now skips just the sync byte (a passing header CRC can be chance), then resyncs —
    the observable outcome is unchanged: exactly the one valid telegram comes out."""
    corrupt = list(TEMPERATURE)
    corrupt[-1] ^= 0xFF  # break only the data CRC; the header (length) stays valid
    buf = corrupt + list(TEMPERATURE)

    status, remaining, _ = Packet.parse_msg(buf)
    assert status == PARSE_RESULT.CRC_MISMATCH
    assert remaining == buf[1:]  # only the sync byte consumed

    packets = _parse_all(buf)
    assert len(packets) == 1 and packets[0].rorg == 0xA5
