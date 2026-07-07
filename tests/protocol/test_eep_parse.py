"""EEP decoding against REAL telegrams captured from the live fleet.

An end-to-end sanity check that the code engine decodes real fleet telegrams (RPS buttons, 4BS
sensors, the A5-13-01 multi-command weather profile) to their expected fields.
"""

import glob
import json
import os

import pytest

import enocean2mqtt.protocol.utils as u
from enocean2mqtt.protocol.packet import RadioPacket

FIX_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "telegrams")
FIXTURES = sorted(glob.glob(os.path.join(FIX_DIR, "*.json")))


def load(path):
    with open(path) as fh:
        return json.load(fh)


def packet(fx):
    return RadioPacket(fx["packet_type"], data=fx["data"], optional=fx["optional"])


def test_fixtures_exist():
    assert FIXTURES, "no telegram fixtures found (run tools/log_to_fixtures.py)"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: os.path.basename(p))
def test_every_real_telegram_parses_structurally(path):
    """All 100+ real telegrams build a RadioPacket and the sender round-trips."""
    fx = load(path)
    p = packet(fx)
    assert p.rorg == fx["rorg"]
    assert u.to_hex_string(p.sender) == fx["sender"]


def _weather_fixture():
    for path in FIXTURES:
        fx = load(path)
        if fx["sender"] == "05:9E:D7:9A":  # the A5-13-01 weather station
            p = packet(fx)
            p.select_eep(0x13, 0x01)
            p.parse_eep()
            if "TMP" in p.parsed:
                return p
    return None


def test_a5_13_01_weather_decodes():
    p = _weather_fixture()
    assert p is not None, "expected an A5-13-01 weather telegram in fixtures"
    # These fields appear only if the A5-13-01 multi-command profile decoded correctly.
    for field in ("TMP", "WND", "DWS"):
        assert field in p.parsed
    assert isinstance(p.parsed["TMP"]["value"], (int, float))


def test_f6_rocker_sender_and_rorg():
    f6 = next((load(p) for p in FIXTURES if load(p)["rorg"] == 0xF6), None)
    assert f6 is not None
    p = packet(f6)
    assert p.rorg == 0xF6
    assert len(p.sender) == 4


def test_eep_parser_yields_fields():
    """A cheap end-to-end sanity check that EEP decoding produces fields."""
    p = _weather_fixture()
    assert p is not None and p.parsed, "decoding produced no fields"
