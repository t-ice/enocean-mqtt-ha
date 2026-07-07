"""PacketDecoder end-to-end decode via the code engine."""

import glob
import json
import os

from enocean2mqtt.application.decoder import PacketDecoder
from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.protocol.packet import RadioPacket

TELEGRAMS = os.path.join(os.path.dirname(__file__), "..", "fixtures", "telegrams")


def _sensor(rorg, func, type_, name="e2m/x"):
    return Sensor.from_dict({"rorg": rorg, "func": func, "type": type_, "name": name})


def _decode(sensor, data, optional):
    packet = RadioPacket(1, data=list(data), optional=list(optional))
    return PacketDecoder.decode(packet, sensor) or {}


def test_a5_02_05_decodes_temperature():
    # ESP3 4BS min-temperature telegram (DB1=0xFF → 0.0 °C for A5-02-05).
    data = [0xA5, 0x00, 0x00, 0xFF, 0x08, 0x05, 0x00, 0x00, 0x01, 0x00]
    optional = [0, 0xFF, 0xFF, 0xFF, 0xFF, 0x49, 0]
    mqtt = _decode(_sensor(0xA5, 0x02, 0x05), data, optional)
    assert mqtt["TMP"] == 0.0
    assert "LRNB" not in mqtt  # learn-bit metadata is not published
    assert "_RAW_DATA_" in mqtt


def test_fleet_fixtures_decode():
    """The real fleet telegrams (A5-10 panels via community backfill + F6 buttons) decode to their
    documented shortcuts through the code engine."""
    a5_path = sorted(glob.glob(os.path.join(TELEGRAMS, "received_a5_051E70DE_*.json")))[0]
    a5 = json.load(open(a5_path))
    mqtt = _decode(_sensor(0xA5, 0x10, 0x03), a5["data"], a5["optional"])
    assert "SP" in mqtt and "TMP" in mqtt

    f6 = json.load(open(sorted(glob.glob(os.path.join(TELEGRAMS, "received_f6_*.json")))[0]))
    mqtt = _decode(_sensor(0xF6, 0x02, 0x01), f6["data"], f6["optional"])
    # community F6-02-01 always emits the rocker layout + status bits
    assert {"R1", "EB", "R2", "SA"} <= set(mqtt)
