"""Snapshot test of HA discovery output.

Discovery configs are RETAINED, so a changed unique_id / cfgtopic / device.identifiers / topic
prefix orphans or duplicates entities across the fleet. This locks the exact published topics,
unique_ids, device blocks, state-topic prefixes (incl. the model-only "+" override), the two
subscribes, and the db_upsert uid + cfgtopics — for one EEP sensor and one model sensor.
"""

import json
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
def ha(tmp_path):
    from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

    raw = [
        {
            "name": "enocean2mqtt/Switch1",
            "address": 0xFEE25DBA,
            "rorg": 0xF6,
            "func": 0x02,
            "type": 0x01,
        },
        {
            "name": "enocean2mqtt/Licht_Kueche",
            "address": 0xFF94CEA0,
            "model": "eltako/FSR14",
            "sender": 0xFFAE7C90,
        },
    ]
    com = HomeAssistantBridge(
        {**CONF, "db_file": str(tmp_path / "db.json")}, [dict(r) for r in raw]
    )
    com._client = mock.Mock()
    com._client.publish = mock.AsyncMock()
    com._client.subscribe = mock.AsyncMock()
    com._devmgr.db_upsert_device = mock.Mock()
    return com


def _capture(com):
    pubs = {c.args[0]: json.loads(c.args[1]) for c in com._client.publish.await_args_list}
    subs = [c.args[0] for c in com._client.subscribe.await_args_list]
    upsert = com._devmgr.db_upsert_device.call_args.args
    return pubs, subs, upsert


async def test_eep_discovery_snapshot(ha):
    sensor = next(s for s in ha.sensors if not s.get("model"))
    await ha._mqtt_discovery_eep(sensor)
    pubs, subs, upsert = _capture(ha)

    prefix = "homeassistant/"
    expected_topics = [
        f"{prefix}binary_sensor/enocean_F60201_FEE25DBA_NONE_{n}/config"
        for n in ("pressed", "AI_pressed", "AO_pressed", "BI_pressed", "BO_pressed")
    ] + [
        f"{prefix}sensor/enocean_F60201_FEE25DBA_NONE_rssi/config",
        f"{prefix}sensor/enocean_F60201_FEE25DBA_NONE_last_seen/config",
    ]
    assert list(pubs.keys()) == expected_topics
    for topic, cfg in pubs.items():
        assert (
            cfg["unique_id"] == topic[len(prefix) :].split("/")[1]
        )  # uid == the middle path segment
        assert cfg["device"]["identifiers"] == "FEE25DBA"
        assert cfg["device"]["manufacturer"] == "EnOcean"
        assert cfg["device"]["model"] == "F6-02-01 @FEE25DBA"
        assert cfg["state_topic"] == "enocean2mqtt/Switch1"  # topic base = full sensor name

    assert subs == [
        f"{prefix}binary_sensor/enocean_F60201_FEE25DBA_NONE_pressed/config/#",
        "enocean2mqtt/Switch1/__system/#",
    ]
    assert upsert[1] == "F60201_FEE25DBA_NONE"
    assert upsert[3] == [t[len(prefix) :] for t in expected_topics]


async def test_model_discovery_snapshot(ha):
    sensor = next(s for s in ha.sensors if s.get("model"))
    await ha._mqtt_discovery_model(sensor)
    pubs, subs, upsert = _capture(ha)

    prefix = "homeassistant/"
    expected_topics = [
        f"{prefix}button/enocean_eltako_fsr14_FF94CEA0_FFAE7C90_pairing/config",
        f"{prefix}switch/enocean_eltako_fsr14_FF94CEA0_FFAE7C90_switch/config",
        f"{prefix}light/enocean_eltako_fsr14_FF94CEA0_FFAE7C90_light/config",
        f"{prefix}sensor/enocean_eltako_fsr14_FF94CEA0_FFAE7C90_rssi/config",
        f"{prefix}sensor/enocean_eltako_fsr14_FF94CEA0_FFAE7C90_last_seen/config",
    ]
    assert list(pubs.keys()) == expected_topics
    for cfg in pubs.values():
        assert cfg["device"]["identifiers"] == "FF94CEA0"
        assert cfg["device"]["manufacturer"] == "eltako"
        assert cfg["device"]["model"] == "FSR14 @FF94CEA0"
    # topic base = the model name with the /RORG suffix stripped
    assert pubs[expected_topics[1]]["state_topic"] == "enocean2mqtt/Licht_Kueche/f6"
    # model-only override: rssi/last_seen read from the next MQTT level ("+")
    assert pubs[expected_topics[3]]["state_topic"] == "enocean2mqtt/Licht_Kueche/+"
    assert pubs[expected_topics[4]]["state_topic"] == "enocean2mqtt/Licht_Kueche/+"

    assert subs == [
        f"{prefix}button/enocean_eltako_fsr14_FF94CEA0_FFAE7C90_pairing/config/#",
        "enocean2mqtt/Licht_Kueche/__system/#",
    ]
    assert upsert[1] == "eltako_fsr14_FF94CEA0_FFAE7C90"
    assert upsert[3] == [t[len(prefix) :] for t in expected_topics]
