"""F6-10-00 window handle (e.g. Hoppe SecuSignal): discovery templates vs. the raw WIN byte.

Regression for #49: the decoder publishes WIN as the raw RPS data byte (0xF0 / 0xE0 / 0xD0 / 0xC0),
but the templates compared it against 3 and 1, so state_2p was always ON and state_3p always "on".
"""

import pytest

from enocean2mqtt.homeassistant.mapping import MAPPING
from enocean2mqtt.protocol.profiles.eep.f6 import PROFILES


def _render(entity_name, win):
    jinja2 = pytest.importorskip("jinja2")
    entities = MAPPING[0xF6][0x10][0x00]["entities"]
    entity = next(e for e in entities if e["name"] == entity_name)
    template = entity["config"]["value_template"]
    return jinja2.Environment().from_string(template).render(value_json={"WIN": win})


@pytest.mark.parametrize(
    ("win", "state_2p", "state_3p"),
    [
        (0xF0, "OFF", "closed"),  # handle down
        (0xE0, "ON", "open"),  # handle horizontal (one side)
        (0xC0, "ON", "open"),  # handle horizontal (other side)
        (0xD0, "ON", "tilt"),  # handle up
    ],
)
def test_window_handle_positions(win, state_2p, state_3p):
    assert _render("state_2p", win) == state_2p
    assert _render("state_3p", win) == state_3p


def test_low_nibble_is_ignored():
    assert _render("state_3p", 0xF1) == "closed"
    assert _render("state_2p", 0xEF) == "ON"


@pytest.mark.parametrize("win", [0x00, 0x10, 0x30, 0x70])
def test_unknown_byte_renders_empty(win):
    # An empty payload is ignored by HA, so a non-handle telegram never flips the state.
    assert _render("state_2p", win) == ""
    assert _render("state_3p", win) == ""


def test_decoder_publishes_raw_byte():
    # The templates above rely on WIN being the full 8-bit data byte at offset 0.
    (case,) = PROFILES[(0xF6, 0x10, 0x00)].cases
    (win,) = [f for f in case.fields if f.shortcut == "WIN"]
    assert (win.offset, win.size) == (0, 8)
    assert all(item.value is None for item in win.items)
