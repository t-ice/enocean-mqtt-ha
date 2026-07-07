"""Code-engine decode goldens + fleet coverage.

Guards that the fleet + command profiles decode to their known-good values, and that the fleet
profiles are present.
"""

import logging

import enocean2mqtt.protocol.utils as u
from enocean2mqtt.protocol.profiles.engine import decode, find_profile, select_case

logging.getLogger("enocean2mqtt.protocol.packet").setLevel(logging.ERROR)

# Fleet DECODE profiles, all covered by the code engine.
FLEET = {"F6-02-01", "A5-13-01", "A5-38-08", "A5-12-01", "A5-02-05", "A5-10-03", "A5-10-06"}


def _published(prof):
    import numbers

    v = prof["value"]
    return v if isinstance(v, numbers.Number) else prof["raw_value"]


def _decode(key, data, status=0):
    profile = find_profile(*key)
    bit_data = u.to_bitarray(data, 8 * len(data))
    bit_status = u.to_bitarray([status], 8)
    case = select_case(profile, bit_data, bit_status)
    return {k: _published(v) for k, v in decode(case, bit_data, bit_status).items()}


def test_fleet_profiles_covered():
    for eep in FLEET:
        r, f, t = (int(x, 16) for x in eep.split("-"))
        assert find_profile(r, f, t) is not None, f"{eep} missing from PROFILES"


def test_golden_a5_10_06_setpoint_temp_slideswitch():
    # A5-10-06: SP raw (0..255), TMP linear (raw 255→0 °C, 0→40 °C), SLSW slide switch bit.
    got = _decode((0xA5, 0x10, 0x06), [0x00, 0x50, 0x80, 0x08])
    assert got["SP"] == 80
    assert round(got["TMP"], 1) == 19.9  # raw 128 → 40*(255-128)/255
    assert got["SLSW"] == 0


def test_golden_d2_01_0a_status_response():
    # D2-01-0A CMD=4 (actuator status response), output value 100%.
    got = _decode((0xD2, 0x01, 0x0A), [0x04, 0x00, 0x64])
    assert got["CMD"] == 4 and got["OV"] == 100 and got["PF"] == 0


def test_golden_d2_05_00_blind_position():
    # D2-05-00 blind position/angle reply.
    got = _decode((0xD2, 0x05, 0x00), [0x04, 0x50, 0x00, 0x00])
    assert got["POS"] == 4 and got["ANG"] == 80
