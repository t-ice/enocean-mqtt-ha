"""Golden decode tests against recorded real telegrams.

Each fixture carries the decoded values it should produce; we assert the decoder reproduces them.
This validates decoding against independent references and guards the multi-command A5-13 path
(a cmd2 telegram must not be misread as cmd1).
"""

import json
import os

import pytest

from enocean2mqtt.protocol.packet import RadioPacket

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "external", "telegrams.json")
TELEGRAMS = json.load(open(FIX))["telegrams"]
_DEFAULT_OPT = [0, 255, 255, 255, 255, 64, 0]


def _decode(tg):
    # The code engine selects the command case from the telegram's own bits (no explicit command
    # extraction needed — the <condition> on the command field is evaluated during select_case).
    p = RadioPacket(1, data=list(tg["data"]), optional=list(tg.get("optional", _DEFAULT_OPT)))
    p.parse_eep(tg["func"], tg["type"], None)
    return p.parsed


@pytest.mark.parametrize("tg", TELEGRAMS, ids=[t["name"] for t in TELEGRAMS])
def test_decodes_to_cited_values(tg):
    parsed = _decode(tg)
    for shortcut, expected in tg["expect"].items():
        assert shortcut in parsed, f"{tg['name']}: missing shortcut {shortcut}"
        got = parsed[shortcut]["value"]
        if isinstance(expected, float):
            assert round(got, 2) == expected, f"{tg['name']}.{shortcut}: {got} != {expected}"
        else:
            assert got == expected, f"{tg['name']}.{shortcut}: {got!r} != {expected!r}"


def test_a5_13_cmd2_not_misread_as_cmd1():
    """Regression: a cmd2 (sun) telegram decodes to sun fields, not a garbage TMP."""
    cmd2 = next(t for t in TELEGRAMS if t["name"] == "a5_13_02_cmd2")
    parsed = _decode(cmd2)
    assert "SNE" in parsed and "SNS" in parsed and "SNW" in parsed
    assert "TMP" not in parsed  # cmd1-only field must not appear for a cmd2 telegram
