"""Regression: a commandless EEP sensor with the mapping's default empty direction must still
parse. The daemon passes device_config's direction ('') straight to parse_eep; '' is not a real
direction and would drop the telegram as 'message not interpretable' unless normalised to None.
"""

import pytest

from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.protocol.packet import RadioPacket


@pytest.fixture
def com():
    from enocean2mqtt.application.daemon import EnoceanDaemon

    # __init__ does no I/O now (the async transport connects only in run()), so no mocks needed.
    conf = {"mqtt_host": "localhost", "enocean_port": "socket://127.0.0.1:3000"}
    return EnoceanDaemon(conf, [])


def test_a5_10_03_parses_with_empty_direction(com):
    # Real ERR_EG_AZ_Meike telegram (A5-10-03) that logged "message not interpretable".
    packet = RadioPacket(
        1,
        data=[0xA5, 0x00, 0xA2, 0x76, 0x0F, 0x05, 0x8E, 0x4F, 0xA7, 0x80],
        optional=[0, 255, 255, 255, 255, 0x41, 0],
    )
    # sensor as the HA overlay builds it: empty command/direction from device_config.
    sensor = Sensor.from_dict(
        {
            "name": "enocean2mqtt/ERR",
            "rorg": 0xA5,
            "func": 0x10,
            "type": 0x03,
            "command": "",
            "direction": "",
        }
    )
    decoded = com._handle_data_packet(packet, sensor)
    assert decoded is not None, "empty direction must not make the telegram uninterpretable"
    assert "SP" in decoded and "TMP" in decoded
