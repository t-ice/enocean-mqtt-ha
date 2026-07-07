"""HA overlay: LEARN/teach-in toggle + auto-off timer, discovery decoration, system messages."""

import asyncio
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

    conf = {**CONF, "db_file": os.path.join(tempfile.mkdtemp(), "db.sqlite")}
    com = HomeAssistantBridge(conf, [])
    com._daemon.publish = mock.AsyncMock()
    com._system_status_topic = {"learn": "homeassistant/button/e2m_learn/state"}
    return com


async def test_teach_in_enable_publishes_on_and_arms_timer(ha):
    await ha._set_teach_in(True)
    assert ha.teach_in is True
    ha._daemon.publish.assert_awaited_with(ha._system_status_topic["learn"], "ON", retain=True)
    assert ha._learn_timer is not None and not ha._learn_timer.done()
    await ha._set_teach_in(False)  # tidy up the timer task


async def test_teach_in_disable_publishes_off_and_cancels_timer(ha):
    await ha._set_teach_in(True)
    timer = ha._learn_timer
    await ha._set_teach_in(False)
    assert ha.teach_in is False
    ha._daemon.publish.assert_awaited_with(ha._system_status_topic["learn"], "OFF", retain=True)
    assert ha._learn_timer is None  # reference cleared
    await asyncio.sleep(0)  # let the cancellation propagate
    assert timer.cancelled()


async def test_auto_disable_turns_learn_off_after_timeout(ha, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", mock.AsyncMock())  # skip the 300s wait
    ha.teach_in = True
    await ha._auto_disable_learn()
    assert ha.teach_in is False
    ha._daemon.publish.assert_awaited_with(ha._system_status_topic["learn"], "OFF", retain=True)


def test_decorate_discovery_adds_availability_and_origin(ha):
    cfg = ha._decorate_discovery({"name": "x"})
    assert cfg["availability_topic"] == ha._daemon.bridge_state_topic
    assert cfg["payload_available"] == "online" and "origin" in cfg


async def test_system_learn_request_toggles_teach_in(ha):
    topic = "enocean2mqtt/__system/learn/req"
    await ha._handle_system_msg(topic, b"ON")
    assert ha.teach_in is True
    await ha._handle_system_msg(topic, b"OFF")
    assert ha.teach_in is False


async def test_system_delete_removes_device_from_store(ha):
    ha._devmgr = mock.Mock()
    await ha._handle_system_msg("homeassistant/sensor/e2m_x/config", b"", delete=True)
    ha._devmgr.db_remove_device_by_field.assert_called_once_with("cfgtopics", "sensor/e2m_x/config")


async def test_stats_discovery_publishes_diagnostic_sensors(ha):
    import json

    ha._daemon.enocean_sender = [0xFF, 0xAE, 0x7C, 0x80]
    await ha._mqtt_discovery_stats()
    calls = ha._daemon.publish.await_args_list
    topics = [c.args[0] for c in calls]
    assert any("enocean2mqtt_stat_uptime_s" in t for t in topics)
    assert any("enocean2mqtt_stat_base_id" in t for t in topics)
    cfgs = [json.loads(c.args[1]) for c in calls]
    up = next(c for c in cfgs if "uptime_s" in c["unique_id"])
    assert up["entity_category"] == "diagnostic"
    assert up["state_topic"].endswith("bridge/stats")
    assert "value_json.uptime_s" in up["value_template"]
    assert "origin" in up  # decorated with availability + origin


async def test_stats_discovery_skipped_without_base_id(ha):
    ha._daemon.enocean_sender = None
    await ha._mqtt_discovery_stats()
    ha._daemon.publish.assert_not_awaited()


def _fake_ute(address=0x0194E3B9, rorg=0xD2, func=0x01, type_=0x01):
    import types

    return types.SimpleNamespace(
        sender_int=address, rorg_of_eep=rorg, rorg_func=func, rorg_type=type_
    )


async def test_on_teach_in_provisions_new_device(ha):
    ha.teach_in = True
    before = len(ha._daemon.sensors)

    await ha.on_teach_in(_fake_ute())

    assert len(ha._daemon.sensors) == before + 1
    new = ha._daemon.sensors[-1]
    assert new.address == 0x0194E3B9
    assert (new.rorg, new.func, new.type) == (0xD2, 0x01, 0x01)
    # discovery + a provisioned announcement were published
    topics = [c.args[0] for c in ha._daemon.publish.await_args_list]
    assert any(t.endswith("bridge/last_provisioned") for t in topics)


async def test_on_teach_in_noop_when_learn_off(ha):
    ha.teach_in = False
    before = len(ha._daemon.sensors)

    await ha.on_teach_in(_fake_ute())

    assert len(ha._daemon.sensors) == before
    ha._daemon.publish.assert_not_awaited()


async def test_on_teach_in_idempotent_for_known_address(ha):
    ha.teach_in = True
    await ha.on_teach_in(_fake_ute())
    n = len(ha._daemon.sensors)

    await ha.on_teach_in(_fake_ute())  # same address again → not re-added

    assert len(ha._daemon.sensors) == n


async def test_on_teach_in_persists_to_devices_yaml(ha):
    from enocean2mqtt.devices import load_devices_yaml

    devices_yaml = os.path.join(tempfile.mkdtemp(), "devices.yaml")
    ha._daemon.conf._raw["device_file"] = devices_yaml
    ha.teach_in = True

    await ha.on_teach_in(_fake_ute())

    persisted = load_devices_yaml(devices_yaml, ha._daemon.conf.mqtt_prefix)
    assert len(persisted) == 1
    assert persisted[0].address == 0x0194E3B9
    assert persisted[0].name == ha._daemon.conf.mqtt_prefix + "auto_0194E3B9"


async def test_on_secure_teach_in_provisions_ptm(ha):
    from enocean2mqtt.protocol.security import TeachIn

    ha.teach_in = True
    ti = TeachIn(
        info=0x24,
        slf=0x8B,
        rlc=0x3E2D00,
        key=bytes.fromhex("456E4F6365616E20476D62482E313300"),
        ptm=True,
        bidirectional=False,
        psk_used=False,
    )
    before = len(ha._daemon.sensors)

    await ha.on_secure_teach_in(ti, [0x01, 0x02, 0x03, 0x04])

    assert len(ha._daemon.sensors) == before + 1
    new = ha._daemon.sensors[-1]
    assert new.address == 0x01020304
    assert new.rorg == 0xF6
    assert new.security and new.key == "456E4F6365616E20476D62482E313300"


def test_load_secure_rlc_restores_from_store(ha):
    """Persisted rolling codes are restored into a configured secure sensor at startup."""
    from enocean2mqtt.domain.sensor import Sensor

    sensor = Sensor.from_dict(
        {
            "name": "sec",
            "address": 0x05000009,
            "rorg": 0xA5,
            "func": 0x07,
            "type": 0x01,
            "security": True,
            "key": "0" * 32,
        }
    )
    ha._daemon.sensors.append(sensor)
    ha._devmgr.db_add_device(sensor, "uid-sec")  # so the store has a row to update
    ha._devmgr.set_rlc(0x05000009, rlc=0x123456, rlc_snd=0x0000AA)

    ha._load_secure_rlc()

    assert sensor["rlc"] == 0x123456
    assert sensor["rlc_snd"] == 0x0000AA


def test_persist_secure_state_logs_on_store_failure(ha, caplog):
    """A failed rolling-code persist is logged (not silently suppressed) and never raises."""
    import logging

    ha._devmgr = mock.Mock()
    ha._devmgr.set_rlc.side_effect = RuntimeError("db locked")
    sensor = mock.Mock(address=0x05000009, rlc=0x10, rlc_snd=0x20)
    with caplog.at_level(logging.ERROR):
        ha._persist_secure_state(sensor)  # must not raise
    assert "Failed to persist rolling code" in caplog.text


def test_bridge_mapping_is_isolated_copy(ha):
    """The bridge works on a deep copy of the code MAPPING, never the shared constant."""
    from enocean2mqtt.homeassistant.mapping import MAPPING

    ha._ha_mapping["__probe__"] = object()
    assert "__probe__" not in MAPPING
