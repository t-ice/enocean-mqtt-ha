"""Pure cover-position maths for Eltako FSB-type shutter actuators.

These actuators (FSB14/FSB61/FJ62) do not report an absolute position:
  * an A5-3F-7F telegram carries the *running time* of the last movement + direction
    (relative), encoded across DB3/DB2 (time, 1/10 s) and DB1 (direction);
  * the F6 end-position telegrams are absolute: 0x70 = fully open (100), 0x50 = closed (0).

The daemon accumulates an absolute position from these and persists it so it survives a
restart. This module is the *pure* core (no DB, no MQTT) so it can be unit-tested exhaustively
against real telegram shapes captured from the live log.
"""

from __future__ import annotations


def update_cover_position(prev_pos, raw_data, mqtt_json, shut_time):
    """Return the new absolute position (0=closed .. 100=open), or ``None`` to leave unchanged.

    Args:
        prev_pos: previously known position (int) or ``None`` (treated as 0 for accumulation).
        raw_data: the ``_RAW_DATA_`` string, colon-separated hex bytes (e.g. ``"70:30"``).
        mqtt_json: decoded telegram fields; for A5 running-time telegrams must carry
            ``DB3``/``DB2`` (running time, 1/10 s) and ``DB1`` (direction; 1 = up/open).
        shut_time: full open/close travel time in seconds (from the device config); falsy
            values fall back to 255.

    Returns:
        int in [0, 100], or ``None`` when the telegram carries no position information
        (movement-start telegrams, malformed input, ``shut_time == 0``, …).
    """
    parts = str(raw_data or "").split(":")

    if len(parts) == 2:
        # F6 end-position telegram (absolute, self-calibrating).
        if parts[0] == "70":
            return 100
        if parts[0] == "50":
            return 0
        return None  # movement start (01/02) etc.: no position information

    if len(parts) == 5:
        # A5 running-time telegram (relative): accumulate onto the current position.
        try:
            shut = float(shut_time or 255)
            drive_time_sec = (int(mqtt_json["DB3"]) * 256 + int(mqtt_json["DB2"])) / 10
            step = drive_time_sec * 100 / shut
            direction = 1 if int(mqtt_json["DB1"]) == 1 else -1
            base = prev_pos if prev_pos is not None else 0
            return max(0, min(int(base + step * direction), 100))
        except (KeyError, ValueError, TypeError, ZeroDivisionError):
            return None

    return None
