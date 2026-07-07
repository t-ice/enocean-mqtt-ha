"""M5: DiscoveryPublisher.build_discovery is pure — the exact HA discovery configs a device would
publish can be asserted without an MQTT broker (no client, no awaits)."""

from enocean2mqtt.homeassistant.discovery.mapping_lookup import EepMappingLookup
from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

CONF = {
    "mqtt_host": "x",
    "mqtt_prefix": "enocean2mqtt/",
    "mqtt_discovery_prefix": "homeassistant/",
    "enocean_port": "socket://127.0.0.1:3000",
}


def test_build_discovery_is_broker_free(tmp_path):
    com = HomeAssistantBridge(
        {**CONF, "db_file": str(tmp_path / "db.json")},
        [
            {
                "name": "enocean2mqtt/Switch1",
                "address": 0xFEE25DBA,
                "rorg": 0xF6,
                "func": 0x02,
                "type": 0x01,
            }
        ],
    )
    sensor = com.sensors[0]
    lookup = EepMappingLookup(sensor, com._ha_mapping, com.conf.mqtt_prefix)

    # No client, no await — build the configs directly.
    dev_uid, configs = com._discovery.build_discovery(sensor, lookup)

    assert dev_uid == "F60201_FEE25DBA_NONE"
    topics = [cfgtopic for cfgtopic, _ in configs]
    assert topics == [
        "binary_sensor/enocean_F60201_FEE25DBA_NONE_pressed/config",
        "binary_sensor/enocean_F60201_FEE25DBA_NONE_AI_pressed/config",
        "binary_sensor/enocean_F60201_FEE25DBA_NONE_AO_pressed/config",
        "binary_sensor/enocean_F60201_FEE25DBA_NONE_BI_pressed/config",
        "binary_sensor/enocean_F60201_FEE25DBA_NONE_BO_pressed/config",
        "sensor/enocean_F60201_FEE25DBA_NONE_rssi/config",
        "sensor/enocean_F60201_FEE25DBA_NONE_last_seen/config",
    ]
    for cfgtopic, cfg in configs:
        assert cfg["unique_id"] == cfgtopic.split("/")[1]
        assert cfg["device"]["identifiers"] == "FEE25DBA"
        assert cfg["state_topic"] == "enocean2mqtt/Switch1"  # topic base = full sensor name
