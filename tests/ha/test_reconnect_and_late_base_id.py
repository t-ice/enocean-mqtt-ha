"""HA bridge across reconnects and a late transceiver (review 2026-11).

- After an MQTT reconnect (clean session) the bridge's own subscriptions — LEARN, discovery-delete
  detection, per-device system topics — used to be gone until the add-on restarted.
- With a Base ID later than 10 s (Pi boots slower than HA) the LEARN switch and the bridge
  diagnostics were never published or subscribed for the whole run.
- A device created by teach-in got entities but its command topic was not subscribed, so HA could
  not control it until the next restart.
"""

from __future__ import annotations

import asyncio
import json
import types
from unittest import mock

import pytest

from enocean2mqtt.application import daemon as daemon_module
from enocean2mqtt.homeassistant import ha_bridge as ha_bridge_module
from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

PREFIX = "enocean2mqtt/"
BASE = [0xFF, 0xAE, 0x7C, 0x80]
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
LEARN_REQ = PREFIX + "__system/learn/req/#"


def _client():
    client = mock.Mock()
    client.publish = mock.AsyncMock()
    client.subscribe = mock.AsyncMock()
    return client


def _subscribed(client):
    return [c.args[0] for c in client.subscribe.await_args_list]


def _published(client):
    return [c.args[0] for c in client.publish.await_args_list]


@pytest.fixture
def bridge(tmp_path):
    b = HomeAssistantBridge({**CONF, "db_file": str(tmp_path / "db.sqlite")}, [dict(ROLLO)])
    b._daemon._transport = mock.AsyncMock()
    return b


@pytest.fixture
def fast_base_id_timeout(monkeypatch):
    monkeypatch.setattr(ha_bridge_module, "_BASE_ID_TIMEOUT", 0.01)
    monkeypatch.setattr(daemon_module, "_BASE_ID_TIMEOUT", 0.01)


async def _connect(bridge, client):
    bridge._client = client
    await bridge._daemon._on_broker_connected()


# --- re-subscribe on every connect ---------------------------------------------------------------


async def test_reconnect_restores_every_subscription(bridge):
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    first, second = _client(), _client()

    await _connect(bridge, first)
    await _connect(bridge, second)  # broker restarted: fresh session, nothing remembered

    assert set(_subscribed(first)) <= set(_subscribed(second))
    topics = _subscribed(second)
    assert LEARN_REQ in topics
    assert PREFIX + "Rollo/a5/req/#" in topics and PREFIX + "Rollo/f6/req/#" in topics
    assert any(t.startswith("homeassistant/") and t.endswith("/config/#") for t in topics)
    assert PREFIX + "Rollo/__system/#" in topics
    assert len(topics) == len(set(topics))  # each topic once per connect


async def test_learn_switch_works_after_a_reconnect(bridge):
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    await _connect(bridge, _client())
    second = _client()
    await _connect(bridge, second)
    assert LEARN_REQ in _subscribed(second)

    await bridge._daemon._handle_mqtt(PREFIX + "__system/learn/req", b"ON")
    assert bridge.teach_in is True
    await bridge._set_teach_in(False)  # stop the auto-off timer


# --- late Base ID ---------------------------------------------------------------------------------


async def test_late_base_id_still_adds_the_learn_switch_and_diagnostics(
    bridge, fast_base_id_timeout
):
    client = _client()
    await _connect(bridge, client)  # Base ID times out: discovery runs without them
    assert not any("learn" in t and t.endswith("/config") for t in _published(client))
    assert LEARN_REQ not in _subscribed(client)

    bridge._daemon.enocean_sender = list(BASE)  # the Pi finally answers
    bridge._base_id_ready.set()
    await asyncio.wait_for(bridge._late_base_id_task, timeout=2)

    published = _published(client)
    assert any("enocean2mqtt_learn_" in t and t.endswith("/config") for t in published)
    assert any("enocean2mqtt_stat_uptime_s" in t for t in published)
    assert PREFIX + "__system/learn" in published  # LEARN status follows its config
    assert LEARN_REQ in _subscribed(client)


async def test_system_entities_are_published_only_once(bridge, fast_base_id_timeout):
    client = _client()
    await _connect(bridge, client)
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    await asyncio.wait_for(bridge._late_base_id_task, timeout=2)
    await _connect(bridge, client)  # a reconnect afterwards
    learn_configs = [t for t in _published(client) if "enocean2mqtt_learn_" in t]
    assert len(learn_configs) == 1


async def test_base_id_before_the_end_of_first_connect_is_not_lost(bridge, fast_base_id_timeout):
    """Base ID arrives while after_connect is still running (between its steps)."""
    client = _client()
    bridge._client = client
    await bridge.before_connect()  # times out, starts the late task
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    await bridge.after_connect()  # first connect sees the Base ID at its end
    await asyncio.wait_for(bridge._late_base_id_task, timeout=2)
    learn_configs = [t for t in _published(client) if "enocean2mqtt_learn_" in t]
    assert len(learn_configs) == 1


async def test_failed_publish_is_retried_on_the_next_connect(bridge):
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    bridge._first_mqtt_connect = False
    bridge._mqtt_discovery_stats = mock.AsyncMock(side_effect=[RuntimeError("broker"), None])
    with pytest.raises(RuntimeError):
        await bridge._publish_system_entities()
    assert bridge._system_entities_published is False
    await bridge._publish_system_entities()
    assert bridge._system_entities_published is True


# --- teach-in devices are controllable right away -------------------------------------------------


async def test_device_taught_in_accepts_commands_immediately(bridge):
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    client = _client()
    await _connect(bridge, client)
    bridge.teach_in = True

    ute = types.SimpleNamespace(
        sender_int=0x0194E3B9, rorg_of_eep=0xD2, rorg_func=0x01, rorg_type=0x01
    )
    await bridge.on_teach_in(ute)

    topic = PREFIX + "auto_0194E3B9"
    assert topic + "/req/#" in _subscribed(client)  # subscribed now, not at the next connect
    bridge._daemon._transport.send.reset_mock()
    command = {"CMD": 1, "DV": 0, "IO": 0, "OV": 100, "send": "clear"}
    await bridge._daemon._handle_mqtt(topic + "/req", json.dumps(command).encode())
    sent = [c.args[0] for c in bridge._daemon._transport.send.await_args_list]
    assert len(sent) == 1 and sent[0].data[0] == 0xD2

    second = _client()
    await _connect(bridge, second)
    assert topic + "/req/#" in _subscribed(second)  # and again after a reconnect


async def test_secure_device_taught_in_is_subscribed_immediately(bridge):
    from enocean2mqtt.protocol.security import TeachIn

    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    client = _client()
    await _connect(bridge, client)
    bridge.teach_in = True
    ti = TeachIn(
        info=0x24,
        slf=0x8B,
        rlc=0,
        key=bytes.fromhex("456E4F6365616E20476D62482E313300"),
        ptm=True,
        bidirectional=False,
        psk_used=False,
    )
    await bridge.on_secure_teach_in(ti, [0x01, 0x02, 0x03, 0x04])
    assert PREFIX + "secure_01020304/req/#" in _subscribed(client)


async def test_late_base_id_during_a_broker_outage_is_published_on_reconnect(
    bridge, fast_base_id_timeout
):
    """A publish while disconnected is dropped silently — it must not count as done."""
    first = _client()
    await _connect(bridge, first)
    bridge._client = None  # broker gone
    bridge._daemon.enocean_sender = list(BASE)
    bridge._base_id_ready.set()
    await asyncio.wait_for(bridge._late_base_id_task, timeout=2)
    assert bridge._system_entities_published is False

    second = _client()
    await _connect(bridge, second)
    assert any("enocean2mqtt_learn_" in t for t in _published(second))
    assert LEARN_REQ in _subscribed(second)
