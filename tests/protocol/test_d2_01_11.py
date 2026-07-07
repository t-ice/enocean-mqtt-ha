"""D2-01-11 is a standard single-channel D2-01 actuator (used by Omnio in-wall modules). It is not
in the core EEP profile set, so we register it modelled on the D2-01-0F command layout. These tests
pin that it resolves and behaves byte-identically to 0x0F.
"""

from enocean2mqtt.protocol.packet import RadioPacket
from enocean2mqtt.protocol.profiles import engine


def _build_set_output(type_):
    return RadioPacket.create(
        rorg=0xD2,
        rorg_func=0x01,
        rorg_type=type_,
        command=1,
        sender=[0x01, 0x02, 0x03, 0x04],
        CMD=1,
        DV=0,
        IO=0,
        OV=100,
    )


def _decode(type_, data):
    p = RadioPacket(1, data=list(data), optional=[0, 255, 255, 255, 255, 0x50, 0])
    p.select_eep(0x01, type_, command=4)
    p.parse_eep()
    return dict(p.parsed)


def test_d2_01_11_is_registered():
    assert engine.find_profile(0xD2, 0x01, 0x11) is not None


def test_d2_01_11_set_output_encodes_like_0f():
    assert _build_set_output(0x11).data == _build_set_output(0x0F).data


def test_d2_01_11_status_response_decodes_like_0f():
    raw = _build_set_output(0x0F).data  # any valid D2-01 payload
    assert _decode(0x11, raw) == _decode(0x0F, raw)
    assert "OV" in _decode(0x11, raw)  # output value is present (switch state)
