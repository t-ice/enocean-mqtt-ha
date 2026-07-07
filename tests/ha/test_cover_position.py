"""Characterization tests for the FSB cover-position maths.

Shapes and shut_time values are taken from the live fleet (12 FSB14s, shut_time 12-64 s) and
the recorded F6 end-position telegrams (0x50 closed / 0x70 open) seen in the add-on log.
"""

import pytest

from enocean2mqtt.homeassistant.cover import update_cover_position


def a5(db3, db2, db1):
    """Build a minimal A5 running-time telegram dict + its 5-part _RAW_DATA_."""
    raw = f"{db3:02x}:{db2:02x}:{db1:02x}:00:00"
    return raw, {"DB3": db3, "DB2": db2, "DB1": db1}


@pytest.mark.parametrize(
    "prev,raw,mj,shut_time,expected",
    [
        # --- F6 end-position telegrams (absolute, self-calibrating) ---
        (0, "70:30", {}, 62, 100),  # fully open
        (100, "50:30", {}, 62, 0),  # fully closed
        (37, "70:30", {}, 62, 100),  # recalibrates regardless of prev
        (37, "01:30", {}, 62, None),  # movement-start: no position info
        # --- A5 running-time telegrams (relative accumulation) ---
        # drive = (DB3*256+DB2)/10 s; step = drive*100/shut_time; DB1=1 up (+), else down (-)
        (0, *a5(0, 62, 1), 62, 10),  # 6.2 s up on 62 s travel -> +10
        (10, *a5(0, 62, 2), 62, 0),  # 6.2 s down from 10 -> 0
        (95, *a5(0, 62, 1), 62, 100),  # clamp at 100
        (5, *a5(0, 62, 2), 62, 0),  # clamp at 0
        (0, *a5(0, 6, 1), 12, 5),  # short shut_time (12 s): 0.6 s -> +5
    ],
)
def test_update_cover_position(prev, raw, mj, shut_time, expected):
    assert update_cover_position(prev, raw, mj, shut_time) == expected


def test_zero_shut_time_falls_back_to_255():
    # A falsy shut_time (0 / None / "") falls back to 255 s via `shut_time or 255`, so there
    # is no division by zero: 6.2 s / 255 s -> +2. (Preserves the original daemon behavior.)
    raw, mj = a5(0, 62, 1)
    assert update_cover_position(0, raw, mj, 0) == 2
    assert update_cover_position(0, raw, mj, None) == 2


def test_missing_db_fields_safe():
    assert update_cover_position(0, "00:00:00:00:00", {}, 62) is None


def test_none_prev_defaults_to_zero():
    raw, mj = a5(0, 62, 1)
    assert update_cover_position(None, raw, mj, 62) == 10


def test_unknown_shape_ignored():
    assert update_cover_position(50, "aa:bb:cc", {}, 62) is None
    assert update_cover_position(50, "", {}, 62) is None
