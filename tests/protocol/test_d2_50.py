"""D2-50 Heat-Recovery-Ventilation status decode (spec-verified per EEP 2.6.x).

The status telegram (message type MT == 2) is selected by its MT bits and yields the temperatures /
air flows / fan speeds / operating mode the HA mapping reads.
"""

import pytest

from enocean2mqtt.protocol.profiles import PROFILES
from enocean2mqtt.protocol.profiles.engine import decode, select_case


def _bits(data: list[int]) -> list[int]:
    return [(b >> (7 - i)) & 1 for b in data for i in range(8)]


@pytest.mark.parametrize("typ", [0x00, 0x01, 0x10, 0x11])
def test_d2_50_status_decodes(typ):
    # 14-byte status telegram: byte0 = 0x41 -> MT nibble 4 (>>1 == 2, status) + OMS low nibble 1;
    # byte5 (db8) = 0x82 -> outdoor-temp raw 65 -> 1 °C. All other bytes 0.
    data = [0x41, 0, 0, 0, 0, 0x82, 0, 0, 0, 0, 0, 0, 0, 0]
    bits = _bits(data)
    case = select_case(PROFILES[(0xD2, 0x50, typ)], bits, [], None, None)
    out = decode(case, bits, [])

    # every field the mapping reads is present
    assert {"OMS", "OUTT", "SPLYT", "SPLYFF", "EXHFF", "SPLYFS", "EXHFS"} <= set(out)
    assert out["OMS"]["value"] == 1  # raw operating-mode code (mapping maps it to a label)
    assert out["OUTT"]["value"] == 1.0  # 65 - 64 °C
    assert out["SPLYT"]["value"] == -64.0  # raw 0 - 64 °C
