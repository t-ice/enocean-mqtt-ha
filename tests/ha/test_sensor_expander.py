"""Characterization of the HA sensor expansion (model -> per-RORG entity sensors + forced flags +
EEP device_config overlay). Locks behaviour before extracting it into SensorExpander."""

import pytest

CONF = {
    "mqtt_host": "x",
    "mqtt_port": "1883",
    "mqtt_prefix": "enocean2mqtt/",
    "mqtt_discovery_prefix": "homeassistant/",
    "enocean_port": "socket://127.0.0.1:3000",
}


@pytest.fixture
def ha_factory(tmp_path):
    from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

    def make(raw):
        conf = {**CONF, "db_file": str(tmp_path / "db.json")}
        return HomeAssistantBridge(conf, [dict(r) for r in raw])

    return make


def test_model_expanded_to_per_rorg_sensors(ha_factory):
    com = ha_factory(
        [
            {
                "name": "enocean2mqtt/Rollo",
                "address": 0xFF94CE9C,
                "model": "eltako/FSB14",
                "sender": 0xFFAE7C81,
                "shut_time": 64,
            }
        ]
    )
    derived = [s for s in com.sensors if s.get("model")]
    assert derived, "model sensor should expand into at least one derived sensor"
    for s in derived:
        # manufacturer/model split + lowercased; rorg/func/type coerced to int
        assert s["manufacturer"] == "eltako" and s["model"] == "fsb14"
        assert all(isinstance(s[k], int) for k in ("rorg", "func", "type"))
        # forced HA flags
        assert s["publish_json"] == "1" and s["publish_rssi"] == "1"
        assert s["publish_date"] == "1" and s["persistent"] == "1"
        # per-RORG name + passthrough fields
        assert s["name"].startswith("enocean2mqtt/Rollo/")
        assert s["address"] == 0xFF94CE9C and s["sender"] == 0xFFAE7C81
        assert s["shut_time"] == 64


def test_eep_sensor_gets_device_config_overlay_and_flags(ha_factory):
    com = ha_factory(
        [
            {
                "name": "enocean2mqtt/Switch1",
                "address": 0xFEE25DBA,
                "rorg": 0xF6,
                "func": 0x02,
                "type": 0x01,
            }
        ]
    )
    s = next(x for x in com.sensors if not x.get("model"))
    # device_config keys are overlaid (present, even if None) and the HA flags are forced on
    for key in ("command", "channel", "log_learn", "direction", "answer"):
        assert key in s
    assert s["publish_json"] == "1" and s["persistent"] == "1"
