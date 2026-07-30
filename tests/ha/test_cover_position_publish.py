"""The absolute cover position is published to a single, dedicated retained position topic.

Regression 1: the cover's ``position_topic`` used to be the ``+`` wildcard, which also matches the
``/a5`` and ``/f6`` state topics — each of which carries its own ``POS`` (from set_position and
from the F6 end-position telegrams respectively). After a full open the fresh POS=100 landed on
``/f6`` while a stale POS from the last set_position stayed retained on ``/a5``; on an HA restart
both retained messages replayed and the last one to arrive won the position restore, so the cover
could come back showing the stale (shaded) position while physically open.

Regression 2: the dedicated topic introduced for that fix was ``{device}/pos`` — a single level
below the device base, and therefore itself matched by ``+``. Every position update was delivered
to the three ``state_topic='+'`` subscribers on the same device (the cover, plus the ``rssi`` and
``last_seen`` diagnostic sensors), and none of their value templates can read ``{"POS": n}``: HA
logged "Payload is not supported" for the cover, a missing ``_RSSI_`` for one sensor and an
``as_local(None)`` crash for the other. The topic therefore sits two levels deep — ``+`` matches
exactly one level, so ``{device}/_ha/pos`` is invisible to them — and the legacy topic is cleared
on connect so the broker stops replaying it.
"""

import json
import os
import tempfile
from unittest import mock

import pytest

from enocean2mqtt.homeassistant.cover import (
    LEGACY_POSITION_SUBTOPIC,
    LEGACY_SHUT_TIME_SUBTOPIC,
    POSITION_TOPIC,
    SHUT_TIME_TOPIC,
)

CONF = {
    "mqtt_host": "x",
    "mqtt_port": "1883",
    "mqtt_prefix": "enocean2mqtt/",
    "mqtt_discovery_prefix": "homeassistant/",
    "enocean_port": "socket://127.0.0.1:3000",
}

POS_TOPIC = "enocean2mqtt/Rollo/" + POSITION_TOPIC
LEGACY_TOPIC = "enocean2mqtt/Rollo" + LEGACY_POSITION_SUBTOPIC
SHUT_TIME_FULL_TOPIC = "enocean2mqtt/Rollo/" + SHUT_TIME_TOPIC
LEGACY_SHUT_TIME_TOPIC = "enocean2mqtt/Rollo" + LEGACY_SHUT_TIME_SUBTOPIC


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
    """A full-open F6 end-position telegram (0x70) persists POS=100 and publishes it."""
    mqtt_json = {"_RAW_DATA_": "70:30"}
    await ha.before_publish(_f6(ha), mqtt_json)

    assert mqtt_json["POS"] == 100
    assert ha._devmgr.get_position(0xFF94CE9C) == 100
    assert json.loads(_published(ha)[POS_TOPIC]) == {"POS": 100}


async def test_close_end_position_publishes_zero(ha):
    mqtt_json = {"_RAW_DATA_": "50:30"}
    await ha.before_publish(_f6(ha), mqtt_json)

    assert mqtt_json["POS"] == 0
    assert json.loads(_published(ha)[POS_TOPIC]) == {"POS": 0}


async def test_running_time_telegram_publishes_accumulated_pos(ha):
    """An A5 running-time telegram accumulates onto the stored base and publishes the result."""
    ha._devmgr.set_position(0xFF94CE9C, 0)
    ha._client.publish.reset_mock()
    # 6.4 s up on 64 s travel -> +10 %
    mqtt_json = {"_RAW_DATA_": "00:40:01:00:00", "DB3": 0, "DB2": 64, "DB1": 1}
    await ha.before_publish(_a5(ha), mqtt_json)

    assert mqtt_json["POS"] == 10
    assert json.loads(_published(ha)[POS_TOPIC]) == {"POS": 10}


async def test_movement_start_telegram_does_not_touch_position(ha):
    """A movement-start telegram (0x01/0x02) carries no position: nothing persisted or published."""
    ha._devmgr.set_position(0xFF94CE9C, 37)
    ha._client.publish.reset_mock()
    mqtt_json = {"_RAW_DATA_": "01:30"}
    await ha.before_publish(_f6(ha), mqtt_json)

    assert "POS" not in mqtt_json
    assert ha._devmgr.get_position(0xFF94CE9C) == 37  # unchanged
    assert POS_TOPIC not in _published(ha)


async def test_on_connect_republishes_stored_position(ha):
    """On connect the last known position is re-published (self-heals an HA restart)."""
    ha._devmgr.set_position(0xFF94CE9C, 42)
    await ha._daemon._on_broker_connected()

    assert json.loads(_published(ha)[POS_TOPIC]) == {"POS": 42}


async def test_on_connect_without_stored_position_publishes_no_pos(ha):
    """With no stored position yet, connect must not publish a bogus position value."""
    await ha._daemon._on_broker_connected()

    assert POS_TOPIC not in _published(ha)


async def test_on_connect_clears_legacy_pos_topic(ha):
    """The 1.0.4 single-level '/pos' topic is cleared, so the broker stops replaying it into the
    cover's and the rssi/last_seen sensors' '+' subscriptions."""
    ha._devmgr.set_position(0xFF94CE9C, 42)
    await ha._daemon._on_broker_connected()

    assert _published(ha)[LEGACY_TOPIC] == ""


async def test_on_connect_moves_shut_time_off_the_wildcard(ha):
    """The travel time is a bare number, not a telegram — at '<device>/shut_time' it reached the
    same three '+' subscribers and broke their templates. It moved two levels deep too, and the
    legacy topic is cleared."""
    await ha._daemon._on_broker_connected()

    published = _published(ha)
    assert published[SHUT_TIME_FULL_TOPIC] == 64
    assert published[LEGACY_SHUT_TIME_TOPIC] == ""


@pytest.mark.parametrize("topic", [POSITION_TOPIC, SHUT_TIME_TOPIC])
def test_bridge_topics_are_invisible_to_the_state_wildcard(topic):
    """Every non-telegram topic the bridge publishes under a device must be >1 level below the
    device base: '+' matches exactly one level, and the cover / rssi / last_seen entities all
    subscribe to '<device>/+'."""
    assert "/" in topic


def test_cover_mapping_uses_dedicated_position_topic():
    """The mapping points position at the dedicated topic, not the '+' state wildcard, and stays in
    sync with what the bridge publishes."""
    from enocean2mqtt.homeassistant.mapping import MAPPING

    cover = next(e for e in MAPPING["eltako"]["fsb14"]["entities"] if e.get("component") == "cover")
    cfg = cover["config"]
    assert cfg["position_topic"] == POSITION_TOPIC
    assert cfg["json_attributes_topic"] == SHUT_TIME_TOPIC
    assert cfg["state_topic"] == "+"  # state still reads both /a5 and /f6


def test_every_cover_mapping_uses_the_bridge_topics():
    """All FSB-type cover mappings (fsb14/fsb61/fj62/tf61j, …) must use the published topics —
    a mismatch would silently leave that model's position or travel time unreadable in HA."""
    from enocean2mqtt.homeassistant.mapping import MAPPING

    found = 0
    for models in MAPPING.values():
        if not isinstance(models, dict):
            continue
        for model in models.values():
            if not isinstance(model, dict):
                continue
            for entity in model.get("entities", []) or []:
                cfg = entity.get("config", {})
                if "position_topic" in cfg:
                    found += 1
                    assert cfg["position_topic"] == POSITION_TOPIC
                    assert cfg["json_attributes_topic"] == SHUT_TIME_TOPIC
    assert found >= 3
