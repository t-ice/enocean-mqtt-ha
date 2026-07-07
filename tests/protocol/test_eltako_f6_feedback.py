"""Eltako wireless relays (FMS61NP-230V, FSR61 in RPS mode) report each relay's state as a PTM200 /
F6-02-01 rocker telegram. Pin the decode of the datasheet's DB values so the documented per-channel
mapping (docs/supported-devices.md) can't silently regress.

Datasheet: DB 0x70/0x50 = channel 1 on/off, 0x30/0x10 = channel 2 on/off.
"""

import pytest

from enocean2mqtt.protocol.packet import RadioPacket


def _decode_rps(db0):
    # F6 (RPS) telegram: data=[RORG, DB0, sender(4), status]; status 0x30 => T21=1, NU=1 (rocker).
    p = RadioPacket(
        1, data=[0xF6, db0, 0xFF, 0x80, 0x01, 0x00, 0x30], optional=[0, 255, 255, 255, 255, 0x46, 0]
    )
    p.select_eep(0x02, 0x01)
    p.parse_eep()
    return p.parsed


@pytest.mark.parametrize(
    "db0,rocker,channel_state",
    [
        (0x70, "Button BO", "ch1 on"),
        (0x50, "Button BI", "ch1 off"),
        (0x30, "Button AO", "ch2 on"),
        (0x10, "Button AI", "ch2 off"),
    ],
)
def test_fms61np_channel_feedback_decodes_as_f6_02_01(db0, rocker, channel_state):
    parsed = _decode_rps(db0)
    assert parsed["R1"]["value"] == rocker, channel_state
    assert parsed["EB"]["value"] == "pressed"
