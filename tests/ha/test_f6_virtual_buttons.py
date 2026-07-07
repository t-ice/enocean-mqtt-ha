"""F6 rocker emulation: the virtual momentary press buttons encode to real PTM200 telegrams."""

import json

from enocean2mqtt.homeassistant.mapping import MAPPING
from enocean2mqtt.protocol.constants import RORG
from enocean2mqtt.protocol.packet import RadioPacket


def _press_buttons():
    virtual = MAPPING[0xF6][0x02][0x01]["virtual"]
    return {
        e["name"]: e
        for e in virtual
        if e["component"] == "button" and e["name"].endswith("(press)")
    }


def test_f6_virtual_has_momentary_press_buttons():
    btns = _press_buttons()
    assert set(btns) == {"AI (press)", "AO (press)", "BI (press)", "BO (press)"}
    for e in btns.values():
        assert e["config"]["command_topic"] == "req"


def test_f6_press_payloads_encode_to_ptm200_telegrams():
    # PTM200: a pressed rocker → F6 data byte = R1<<5 | 0x10 (EB=1), status 0x30 (T21 + NU).
    expected_data = {"AI (press)": 0x10, "AO (press)": 0x30, "BI (press)": 0x50, "BO (press)": 0x70}
    for name, e in _press_buttons().items():
        fields = json.loads(e["config"]["payload_press"])
        fields.pop("send", None)
        pkt = RadioPacket.create(
            rorg=RORG.RPS,
            rorg_func=0x02,
            rorg_type=0x01,
            **{k: int(v) for k, v in fields.items()},
        )
        assert pkt.data[0] == RORG.RPS
        assert pkt.data[1] == expected_data[name]  # the F6 rocker data byte
        assert pkt.data[-1] == 0x30  # status: T21 + NU (a valid press)
