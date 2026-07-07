"""Discovery payloads must carry availability (LWT) + origin, per HA MQTT best practice.

Also covers the asyncio learn auto-timeout (replacing the old threading.Timer).
"""

import asyncio
import json
from unittest import mock

import pytest


@pytest.fixture
def ha(tmp_path):
    from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

    config = {
        "mqtt_host": "localhost",
        "mqtt_port": "1883",
        "mqtt_prefix": "enocean2mqtt/",
        "mqtt_discovery_prefix": "homeassistant/",
        "enocean_port": "socket://127.0.0.1:3000",
        "db_file": str(tmp_path / "db.json"),
    }
    # One F6-02-01 rocker (present in the code-defined MAPPING).
    sensors = [
        {
            "name": "enocean2mqtt/Switch1",
            "address": 0xFEE25DBA,
            "rorg": 0xF6,
            "func": 0x02,
            "type": 0x01,
        }
    ]
    # __init__ does no I/O; wire a fake async client to capture publishes/subscribes.
    com = HomeAssistantBridge(config, sensors)
    com._client = mock.Mock()
    com._client.publish = mock.AsyncMock()
    com._client.subscribe = mock.AsyncMock()
    return com


def _published_configs(com):
    """Return decoded discovery config payloads captured from client.publish()."""
    out = []
    for call in com._client.publish.await_args_list:
        topic = call.args[0] if call.args else call.kwargs.get("topic", "")
        payload = call.args[1] if len(call.args) > 1 else call.kwargs.get("payload")
        if topic.endswith("/config") and payload:
            out.append(json.loads(payload))
    return out


async def test_eep_discovery_has_availability_and_origin(ha):
    await ha._mqtt_discovery_eep(ha.sensors[0])
    configs = _published_configs(ha)
    assert configs, "expected at least one discovery config to be published"
    for cfg in configs:
        assert cfg["availability_topic"] == "enocean2mqtt/bridge/state"
        assert cfg["payload_available"] == "online"
        assert cfg["payload_not_available"] == "offline"
        assert cfg["origin"]["name"] == "EnOcean MQTT for Home Assistant"
        assert "sw_version" in cfg["origin"]


async def test_availability_topic_is_not_entity_prefixed(ha):
    """Regression: availability_topic must be the global bridge topic, not sensor-prefixed."""
    await ha._mqtt_discovery_eep(ha.sensors[0])
    for cfg in _published_configs(ha):
        assert not cfg["availability_topic"].startswith("enocean2mqtt/Switch1")


async def test_learn_arms_and_cancels_timer(ha):
    ha._system_status_topic = {"learn": "enocean2mqtt/__system/learn"}
    ha.teach_in = False

    await ha._set_teach_in(True)
    assert ha.teach_in is True
    assert ha._learn_timer is not None and not ha._learn_timer.done()  # auto-off timer armed

    await ha._set_teach_in(False)
    assert ha.teach_in is False
    assert ha._learn_timer is None  # timer cancelled/cleared


async def test_learn_auto_disables_after_timeout(ha):
    ha._system_status_topic = {"learn": "enocean2mqtt/__system/learn"}
    ha._LEARN_TIMEOUT_S = 0  # fire almost immediately

    await ha._set_teach_in(True)
    assert ha.teach_in is True
    # Let the auto-off task run.
    await asyncio.sleep(0.05)
    assert ha.teach_in is False
