"""Resilience: network failure (ser2net link + MQTT broker drop) and power failure (Pi + add-on
restart), exercised by stopping/restarting containers and asserting the daemon self-heals.

Mirrors the real deployment: the transceiver is the Raspberry-Pi ser2net endpoint (emulator), the
broker is mosquitto, the daemon is the add-on. All gated behind `-m integration` (needs podman).
"""

from __future__ import annotations

import pytest
from tests.integration.conftest import Collector, wait_until

pytestmark = pytest.mark.integration

WETTER = "enocean2mqtt/Wetter"
BRIDGE = "enocean2mqtt/bridge/state"


@pytest.fixture
def mqtt_client(stack):
    c = Collector(stack["mqtt_port"])
    yield c
    c.close()


def _wait_online(mc):
    assert wait_until(lambda: mc.msgs.get(BRIDGE) == b"online", timeout=45), "bridge not online"


def _wait_state(mc):
    assert wait_until(lambda: mc.topics_matching(WETTER), timeout=45), "no Wetter state publish"


def test_network_failure_transceiver_drops_and_recovers(stack, mqtt_client):
    """Pi/ser2net link drops (emulator restart): the daemon reconnects, re-runs the base-id
    handshake, and resumes decoding replayed telegrams (transceiver reconnect loop + backoff)."""
    _wait_online(mqtt_client)
    _wait_state(mqtt_client)

    mqtt_client.forget(WETTER)  # so a fresh publish is unambiguous
    stack["podman"]("restart", "-t", "1", stack["emulator"])  # yank + restore the ser2net link

    assert wait_until(lambda: mqtt_client.topics_matching(WETTER), timeout=60), (
        "daemon did not recover the transceiver link (no state after ser2net came back)"
    )


def test_network_failure_broker_drops_and_recovers(stack, mqtt_client):
    """MQTT broker restarts: the daemon reconnects and re-announces availability (LWT → online)."""
    _wait_online(mqtt_client)

    mqtt_client.forget(BRIDGE)
    stack["podman"]("restart", "-t", "1", stack["mosquitto"])  # broker outage

    # Both the daemon and our collector reconnect; retained 'online' is re-published/re-delivered.
    assert wait_until(lambda: mqtt_client.msgs.get(BRIDGE) == b"online", timeout=60), (
        "bridge did not return to 'online' after the broker restarted"
    )


def test_power_failure_daemon_restart_recovers_and_persists(stack, mqtt_client):
    """Add-on / HA-host power-cycle (daemon container restart): the daemon reloads devices.yaml,
    reconnects to broker + transceiver, and its persisted state (sqlite on /data) survives."""
    _wait_online(mqtt_client)
    _wait_state(mqtt_client)
    db = stack["work"] / "db.sqlite"
    assert wait_until(lambda: db.exists() and db.stat().st_size > 0, timeout=30), "no device DB"
    size_before = db.stat().st_size

    mqtt_client.forget(BRIDGE)
    mqtt_client.forget(WETTER)
    stack["podman"]("restart", "-t", "3", stack["daemon"])  # power-cycle the add-on

    _wait_online(mqtt_client)  # comes back online
    assert wait_until(lambda: mqtt_client.topics_matching(WETTER), timeout=60), (
        "daemon did not resume publishing after restart"
    )
    # the persistent store survived the restart (positions/discovery bookkeeping intact)
    assert db.exists() and db.stat().st_size >= size_before
