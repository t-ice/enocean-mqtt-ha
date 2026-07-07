"""EEP decode fidelity golden.

Captures the exact decoded output for the fleet's profiles. It passes on the current parser and
must keep passing after the EEP parser is migrated off BeautifulSoup — i.e. it proves the swap is
behaviour-preserving across the value / enum / boolean decode paths.
"""

import glob
import json
import os

import pytest

from enocean2mqtt.protocol.packet import RadioPacket

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "telegrams")


def decode(sender_glob, func, type_):
    path = sorted(glob.glob(os.path.join(FIX, sender_glob)))[0]
    fx = json.load(open(path))
    p = RadioPacket(fx["packet_type"], data=fx["data"], optional=fx["optional"])
    p.select_eep(func, type_)
    p.parse_eep()
    return {
        k: (round(v["value"], 4) if isinstance(v["value"], float) else v["value"])
        for k, v in p.parsed.items()
    }


GOLDENS = [
    # sender glob,                 func, type, expected decoded shortcuts
    ("received_a5_051E70DE_*.json", 0x10, 0x03, {"SP": 76.0, "TMP": 24.1569}),
    (
        "received_a5_058D07E7_*.json",
        0x10,
        0x06,
        {"SP": 76.0, "TMP": 24.0, "SLSW": "Position O / Day / On"},
    ),
    (
        "received_f6_*.json",
        0x02,
        0x01,
        {
            "R1": "Button AI",
            "EB": "released",
            "R2": "Button AI",
            "SA": "No 2nd action",
            "T21": True,
            "NU": False,
        },
    ),
]


@pytest.mark.parametrize(
    "glob_,func,type_,expected", GOLDENS, ids=[g[0].split("_")[1] + hex(g[1]) for g in GOLDENS]
)
def test_decode_matches_golden(glob_, func, type_, expected):
    assert decode(glob_, func, type_) == expected
