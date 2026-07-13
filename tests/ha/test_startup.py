"""Characterization of the HA on-connect startup sequence: availability first, LEARN status only
after the LEARN button is discovered, and cover shut_time published."""

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
            "name": "enocean2mqtt/Rollo",
            "address": 0xFF94CE9C,
            "model": "eltako/FSB14",
            "sender": 0xFFAE7C81,
            "shut_time": 64,
        }
    ]
    com = HomeAssistantBridge(
        {**CONF, "db_file": str(tmp_path / "db.json")}, [dict(r) for r in raw]
    )
    com._client = mock.Mock()
    com._client.publish = mock.AsyncMock()
    com._client.subscribe = mock.AsyncMock()
    com._daemon.enocean_sender = [0xFF, 0xAE, 0x7C, 0x80]
    com._base_id_ready.set()  # so discovery proceeds immediately
    return com


async def test_on_connect_sequence(ha):
    await ha._daemon._on_broker_connected()
    topics = [c.args[0] for c in ha._client.publish.await_args_list]
    payloads = {c.args[0]: c.args[1] for c in ha._client.publish.await_args_list}

    # 1) availability announced online first of all
    assert topics[0] == "enocean2mqtt/bridge/state"
    assert payloads["enocean2mqtt/bridge/state"] == "online"

    # 2) the LEARN button's discovery config is published before its status
    learn_cfg = next(t for t in topics if t.endswith("/config") and "learn" in t)
    learn_status = "enocean2mqtt/__system/learn"
    assert topics.index(learn_cfg) < topics.index(learn_status)
    assert payloads[learn_status] == "OFF"  # teach-in disabled on startup

    # 3) the cover's configured shut_time is published (retained single source of truth)
    assert payloads["enocean2mqtt/Rollo/shut_time"] == 64

    # sanity: the LEARN system device config targets the ENOCEAN2MQTT virtual device
    assert json.loads(payloads[learn_cfg])["device"]["name"] == "ENOCEAN2MQTT"


async def test_model_actuator_discovered_once(ha):
    """An Eltako model actuator expands into two RORG sensors (/a5 + /f6) sharing one dev_uid;
    discovery must publish its config set exactly once, not twice (regression: doubled log lines /
    redundant retained publishes), while keeping every entity from both RORG halves."""
    await ha._daemon._on_broker_connected()

    dev_uid = "eltako_fsb14_FF94CE9C_FFAE7C81"  # eltako/FSB14 @ FF94CE9C, sender FFAE7C81
    publishes = [(c.args[0], c.args[1]) for c in ha._client.publish.await_args_list]
    cfg_topics = [t for t, _ in publishes if t.endswith("/config") and dev_uid in t]

    # 1) dedup: every config topic of this device is published exactly once (was twice before)
    assert cfg_topics, "no discovery config published for the model actuator"
    assert len(cfg_topics) == len(set(cfg_topics)), (
        f"model actuator config republished: {cfg_topics}"
    )

    # 2) exactly one DB upsert (one discovery round) for this device
    assert sum(1 for r in ha._devmgr.db_list_from_fields("uid") if r == dev_uid) == 1

    # 3) no entities lost by dedup: both RORG halves are present — a5 command topics (cover/pairing)
    #    and f6 state topics (end/start binary sensors)
    payloads = [p for t, p in publishes if t.endswith("/config") and dev_uid in t]
    assert any("enocean2mqtt/Rollo/a5" in p for p in payloads), "a5 (command) entities missing"
    assert any("enocean2mqtt/Rollo/f6" in p for p in payloads), "f6 (status) entities missing"
    assert any("cover/" + "enocean_" + dev_uid in t for t in cfg_topics), "cover entity missing"


async def test_on_connect_without_base_id_skips_system_entities(ha, caplog):
    """A transceiver that reported no Base ID must not crash startup — the Base-ID-keyed system
    entities (LEARN button, bridge stats) are skipped with a clear error, sensors still publish."""
    import logging

    ha._daemon.enocean_sender = None  # e.g. the configured device isn't the EnOcean stick
    with caplog.at_level(logging.ERROR):
        await ha._daemon._on_broker_connected()  # must not raise

    topics = [c.args[0] for c in ha._client.publish.await_args_list]
    # availability + per-device discovery still happen
    assert "enocean2mqtt/bridge/state" in topics
    assert "enocean2mqtt/Rollo/shut_time" in topics
    # but nothing keyed on the (missing) Base ID
    assert not any(t.endswith("/config") and "learn" in t for t in topics)
    assert "no Base ID" in caplog.text
