"""Regression: FSB14 cover commands from HA must reach the transceiver as the correct telegram.

Covers/blinds broke because the command path uses property-based encoding (set_eep with
DB3/DB2/DB1/DB0) — not the raw_data path that test_send_encode covers — and the FSB14 device_config
carries `direction: ""`, which (unfixed) selected no EEP profile and made set_eep a silent no-op, so
the movement-direction byte DB1 was never encoded. Raw-data commands (FSR14 lights) were unaffected.
"""

import os
import tempfile
from unittest import mock

import pytest

CONF = {
    "mqtt_host": "x",
    "mqtt_port": "1883",
    "mqtt_prefix": "enocean2mqtt/",
    "mqtt_discovery_prefix": "homeassistant/",
    "enocean_port": "socket://127.0.0.1:3000",
}


@pytest.fixture
def ha():
    from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

    conf = {**CONF, "db_file": os.path.join(tempfile.mkdtemp(), "db.json")}
    com = HomeAssistantBridge(
        conf,
        [
            {
                "name": "enocean2mqtt/Rollo",
                "address": 0xFF94CE9C,
                "model": "eltako/FSB14",
                "sender": 0xFFAE7C81,
                "shut_time": 64,
            }
        ],
    )
    com._daemon.enocean_sender = [0xFF, 0xAE, 0x7C, 0x81]
    com._daemon._transport.send = mock.AsyncMock()
    return com


async def _send(ha, payload):
    ha._daemon._transport.send.reset_mock()
    await ha._daemon._handle_mqtt("enocean2mqtt/Rollo/a5/req", payload)
    assert ha._daemon._transport.send.called, "cover command did not reach the transceiver"
    return ha._daemon._transport.send.call_args.args[0]


@pytest.mark.parametrize(
    "payload,db1,name",
    [
        (b'{"DB3":"0","DB2":"0","DB1":"1","DB0":"8","send":"clear"}', 0x01, "open"),
        (b'{"DB3":"0","DB2":"0","DB1":"2","DB0":"8","send":"clear"}', 0x02, "close"),
        (b'{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}', 0x00, "stop"),
    ],
)
async def test_cover_movement_commands(ha, payload, db1, name):
    pkt = await _send(ha, payload)
    # 4BS data payload = data[1:5] = DB3 DB2 DB1 DB0; DB1 (data[3]) carries the movement direction.
    assert pkt.data[1:5] == [0x00, 0x00, db1, 0x08], f"{name}: wrong DB bytes {pkt.data[1:5]}"
    assert pkt.data[5:9] == [0xFF, 0xAE, 0x7C, 0x81]  # sender


async def test_cover_set_position(ha):
    # HA set_position_template for +N% up: DB3/DB2 = drive-time (1/10 s), DB1=1, DB0=10.
    pkt = await _send(ha, b'{"DB3":"1","DB2":"44","DB1":"1","DB0":"10","send":"clear"}')
    assert pkt.data[1:5] == [0x01, 0x2C, 0x01, 0x0A]  # 0x012C = 300 -> 30.0 s drive time, up
