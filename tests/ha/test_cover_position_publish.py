"""The absolute cover position is published to a single, dedicated retained ``/pos`` topic.

Regression: the cover's ``position_topic`` used to be the ``+`` wildcard, which also matches the
``/a5`` and ``/f6`` state topics — each of which carries its own ``POS`` (from set_position and
from the F6 end-position telegrams respectively). After a full open the fresh POS=100 landed on
``/f6`` while a stale POS from the last set_position stayed retained on ``/a5``; on an HA restart
both retained messages replayed and the last one to arrive won the position restore, so the cover
could come back showing the stale (shaded) position while physically open.

The fix publishes the authoritative position to a dedicated ``{device}/pos`` topic — on every change
and, from the store, on connect — and points ``position_topic`` at it, so the restored value is
deterministic.
"""

import json
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
    com._client = mock.Mock()
    com._client.publish = mock.AsyncMock()
    com._client.subscribe = mock.AsyncMock()
    com._daemon.enocean_sender = [0xFF, 0xAE, 0x7C, 0x80]
    com._base_id_ready.set()  # so on-connect discovery proceeds immediately
    # Create the device row (as discovery would) so position get/set has something to key on;
    # use the uid discovery derives (manufacturer_model_ADDRESS_SENDER) so its later upsert merges.
    a5 = next(s for s in com._daemon.sensors if s.rorg == 0xA5)
    com._devmgr.db_upsert_device(a5, "eltako_fsb14_FF94CE9C_FFAE7C81")
    return com


def _a5(ha):
    return next(s for s in ha._daemon.sensors if s.rorg == 0xA5)


def _f6(ha):
    return next(s for s in ha._daemon.sensors if s.rorg == 0xF6)


def _published(ha):
    return {c.args[0]: c.args[1] for c in ha._client.publish.await_args_list}


async def test_end_position_telegram_publishes_absolute_pos(ha):
    """A full-open F6 end-position telegram (0x70) persists POS=100 and publishes it to /pos."""
    mqtt_json = {"_RAW_DATA_": "70:30"}
    await ha.before_publish(_f6(ha), mqtt_json)

    assert mqtt_json["POS"] == 100
    assert ha._devmgr.get_position(0xFF94CE9C) == 100
    assert json.loads(_published(ha)["enocean2mqtt/Rollo/pos"]) == {"POS": 100}


async def test_close_end_position_publishes_zero(ha):
    mqtt_json = {"_RAW_DATA_": "50:30"}
    await ha.before_publish(_f6(ha), mqtt_json)

    assert mqtt_json["POS"] == 0
    assert json.loads(_published(ha)["enocean2mqtt/Rollo/pos"]) == {"POS": 0}


async def test_running_time_telegram_publishes_accumulated_pos(ha):
    """An A5 running-time telegram accumulates onto the stored base and publishes the result."""
    ha._devmgr.set_position(0xFF94CE9C, 0)
    ha._client.publish.reset_mock()
    # 6.4 s up on 64 s travel -> +10 %
    mqtt_json = {"_RAW_DATA_": "00:40:01:00:00", "DB3": 0, "DB2": 64, "DB1": 1}
    await ha.before_publish(_a5(ha), mqtt_json)

    assert mqtt_json["POS"] == 10
    assert json.loads(_published(ha)["enocean2mqtt/Rollo/pos"]) == {"POS": 10}


async def test_movement_start_telegram_does_not_touch_position(ha):
    """A movement-start telegram (0x01/0x02) carries no position: nothing persisted or published."""
    ha._devmgr.set_position(0xFF94CE9C, 37)
    ha._client.publish.reset_mock()
    mqtt_json = {"_RAW_DATA_": "01:30"}
    await ha.before_publish(_f6(ha), mqtt_json)

    assert "POS" not in mqtt_json
    assert ha._devmgr.get_position(0xFF94CE9C) == 37  # unchanged
    assert "enocean2mqtt/Rollo/pos" not in _published(ha)


async def test_on_connect_republishes_stored_position(ha):
    """On connect the last known position is re-published to /pos (self-heals an HA restart)."""
    ha._devmgr.set_position(0xFF94CE9C, 42)
    await ha._daemon._on_broker_connected()

    assert json.loads(_published(ha)["enocean2mqtt/Rollo/pos"]) == {"POS": 42}


async def test_on_connect_without_stored_position_publishes_no_pos(ha):
    """With no stored position yet, connect must not publish a bogus /pos value."""
    await ha._daemon._on_broker_connected()

    assert "enocean2mqtt/Rollo/pos" not in _published(ha)


def test_cover_mapping_uses_dedicated_position_topic():
    """The mapping points position at the dedicated 'pos' topic, not the '+' state wildcard."""
    from enocean2mqtt.homeassistant.mapping import MAPPING

    cover = next(e for e in MAPPING["eltako"]["fsb14"]["entities"] if e.get("component") == "cover")
    cfg = cover["config"]
    assert cfg["position_topic"] == "pos"
    assert cfg["state_topic"] == "+"  # state still reads both /a5 and /f6
