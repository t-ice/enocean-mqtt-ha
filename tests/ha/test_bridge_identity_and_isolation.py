"""HA-bridge follow-ups from the second code review (2026-11). Each test failed before its fix.

- One device whose discovery raised ended the whole add-on.
- A changed sender (replaced stick, corrected sender) gave a device a new unique id: Home Assistant
  created new entities and the store lost the cover position.
- Replacing the stick left a second, orphaned bridge device behind.
- Cover positions that changed while the broker was away were never published after the reconnect.
"""

from __future__ import annotations

import json
import logging
from unittest import mock

import pytest

from enocean2mqtt.adapters.store.sqlite_store import SqliteDeviceStore
from enocean2mqtt.domain.sensor import device_base_name
from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

PREFIX = "enocean2mqtt/"
CONF = {
    "mqtt_host": "x",
    "mqtt_port": "1883",
    "mqtt_prefix": PREFIX,
    "mqtt_discovery_prefix": "homeassistant/",
    "enocean_port": "socket://127.0.0.1:3000",
}
ROLLO = {
    "name": PREFIX + "Rollo",
    "address": 0xFF94CE9C,
    "model": "eltako/FSB14",
    "sender": 0xFFAE7C81,
    "shut_time": 64,
}
LICHT = {
    "name": PREFIX + "Licht",
    "address": 0xFF94CE82,
    "model": "eltako/FSR14",
    "sender": 0xFFAE7C82,
}
OLD_BASE = [0xFF, 0xAE, 0x7C, 0x80]
NEW_BASE = [0xFF, 0xB0, 0x00, 0x00]


def _client():
    client = mock.Mock()
    client.publish = mock.AsyncMock()
    client.subscribe = mock.AsyncMock()
    return client


def _bridge(tmp_path, devices, base=OLD_BASE):
    bridge = HomeAssistantBridge(
        {**CONF, "db_file": str(tmp_path / "db.sqlite")}, [dict(d) for d in devices]
    )
    bridge._daemon._transport = mock.AsyncMock()
    bridge._daemon.enocean_sender = list(base)
    bridge._base_id_ready.set()
    return bridge


async def _connect(bridge):
    client = _client()
    bridge._client = client
    await bridge._daemon._on_broker_connected()
    return client


def _configs(client):
    """{discovery topic: config} of everything published as a (non-empty) discovery config."""
    return {
        c.args[0]: json.loads(c.args[1])
        for c in client.publish.await_args_list
        if c.args[0].startswith("homeassistant/") and c.args[1]
    }


def _unique_ids(client, device_name):
    return {
        cfg["unique_id"]
        for cfg in _configs(client).values()
        if cfg["device"]["name"] == device_name
    }


# --- one bad device ---------------------------


async def test_failing_discovery_of_one_device_spares_the_others(tmp_path, caplog):
    bridge = _bridge(tmp_path, [ROLLO, LICHT])
    publish = bridge._discovery.publish

    async def flaky(sensor, *args, **kwargs):
        if "Rollo" in sensor.name:
            raise KeyError("broken mapping entry")
        await publish(sensor, *args, **kwargs)

    bridge._discovery.publish = flaky
    with caplog.at_level(logging.ERROR):
        client = await _connect(bridge)  # must not raise

    assert "Discovery for enocean2mqtt/Rollo failed" in caplog.text
    assert _unique_ids(client, "e2m_Licht")


async def test_device_whose_discovery_failed_is_not_pruned(tmp_path):
    first = _bridge(tmp_path, [ROLLO])
    await _connect(first)

    again = _bridge(tmp_path, [ROLLO])
    again._discovery.publish = mock.AsyncMock(side_effect=KeyError("broken mapping entry"))
    client = await _connect(again)

    cleared = [
        c.args[0]
        for c in client.publish.await_args_list
        if c.args[0].startswith("homeassistant/") and c.args[1] == ""
    ]
    assert cleared == [], "a configured device must keep its entities when discovery fails once"
    assert again._devmgr.db_get_device_by_address(ROLLO["address"]) is not None


# --- identity survives a changed sender ---------------------------


async def test_changed_sender_keeps_unique_ids_and_cover_position(tmp_path):
    before = _bridge(tmp_path, [ROLLO])
    old_ids = _unique_ids(await _connect(before), "e2m_Rollo")
    before._devmgr.set_position(ROLLO["address"], 42)

    after = _bridge(tmp_path, [{**ROLLO, "sender": 0xFFB00001}], base=NEW_BASE)
    client = await _connect(after)

    assert _unique_ids(client, "e2m_Rollo") == old_ids
    assert after._devmgr.get_position(ROLLO["address"]) == 42
    assert len(after._devmgr.db_get_devices()) == 1


async def test_replaced_stick_keeps_the_bridge_device(tmp_path):
    before = _bridge(tmp_path, [ROLLO])
    old = _unique_ids(await _connect(before), "ENOCEAN2MQTT")

    after = _bridge(tmp_path, [ROLLO], base=NEW_BASE)
    client = await _connect(after)

    assert old and _unique_ids(client, "ENOCEAN2MQTT") == old
    models = {
        c["device"]["model"]
        for c in _configs(client).values()
        if c["device"]["name"] == "ENOCEAN2MQTT"
    }
    assert models == {"Virtual @FFB00000"}  # the model line still shows the real Base ID


def test_stable_uid_rules(tmp_path):
    store = SqliteDeviceStore({"db_file": str(tmp_path / "db.sqlite")})
    assert store.stable_uid("A50205_01020304_NONE") == "A50205_01020304_NONE"  # unknown device

    store.db_upsert_device(
        {"address": 0x01020304, "name": "t", "rorg": 0xA5, "func": 2, "type": 5},
        "A50205_01020304_NONE",
    )
    assert store.stable_uid("A50205_01020304_FFAE7C81") == "A50205_01020304_NONE"
    assert store.stable_uid("A50206_01020304_FFAE7C81") == "A50206_01020304_FFAE7C81"  # other EEP

    # Virtual devices share the address FFFFFFFF; only the sender tells them apart.
    store.db_upsert_device(
        {"address": 0xFFFFFFFF, "name": "v", "rorg": 0xF6, "func": 2, "type": 1},
        "F60201_FFFFFFFF_FFAE7C90",
    )
    assert store.stable_uid("F60201_FFFFFFFF_FFAE7C91") == "F60201_FFFFFFFF_FFAE7C91"


def test_bridge_id_is_the_first_base_id_seen(tmp_path):
    path = str(tmp_path / "db.sqlite")
    assert SqliteDeviceStore({"db_file": path}).bridge_id("FFAE7C80") == "FFAE7C80"
    assert SqliteDeviceStore({"db_file": path}).bridge_id("FFB00000") == "FFAE7C80"


# --- reconnect ---------------------------


async def test_cover_position_is_published_again_after_a_broker_reconnect(tmp_path):
    bridge = _bridge(tmp_path, [ROLLO])
    await _connect(bridge)
    bridge._devmgr.set_position(ROLLO["address"], 37)  # moved while the broker was away

    client = await _connect(bridge)

    position = [c.args[1] for c in client.publish.await_args_list if c.args[0].endswith("/_ha/pos")]
    assert position == [json.dumps({"POS": 37})]


@pytest.mark.parametrize(
    ("name", "base"),
    [
        ("enocean2mqtt/Rollo/a5", "enocean2mqtt/Rollo"),
        ("enocean2mqtt/og/bad/Rollo/f6", "enocean2mqtt/og/bad/Rollo"),
    ],
)
def test_device_base_name(name, base):
    assert device_base_name(name) == base
