"""End-to-end: the real add-on image against mosquitto + a ser2net/ESP3 emulator (the Pi + stick).

Exercises the whole path over the ser2net TCP topology: base-id handshake → HA discovery →
telegram replay → MQTT state publish, and an inbound MQTT command → ESP3 frame on the wire.
"""

from __future__ import annotations

import json
import time

import pytest
from tests.integration.conftest import Collector, read_capture, wait_until

pytestmark = pytest.mark.integration


@pytest.fixture
def mqtt_client(stack):
    c = Collector(stack["mqtt_port"])
    yield c
    c.close()


def test_end_to_end_discovery_state_and_command(stack, mqtt_client):
    # (1) the bridge announces availability once connected to the broker.
    assert wait_until(
        lambda: mqtt_client.msgs.get("enocean2mqtt/bridge/state") == b"online", timeout=45
    ), "bridge never published 'online' (daemon/broker/emulator link?)"

    # (2) HA MQTT-discovery configs are published (base id handshake + discovery ran).
    assert wait_until(
        lambda: (
            mqtt_client.topics_matching("homeassistant/") and mqtt_client.topics_matching("/config")
        ),
        timeout=30,
    ), "no discovery configs"

    # (3) the emulator's replayed A5-10-03 telegram becomes an MQTT state publish for 'Wetter'.
    assert wait_until(lambda: mqtt_client.topics_matching("enocean2mqtt/Wetter"), timeout=30), (
        "replayed telegram did not produce a state publish"
    )

    # (3b) the retained bridge/stats topic reports the transceiver identity learned via the
    # CO_RD_VERSION + CO_RD_IDBASE handshake (the emulator's Base ID reply carries the extra
    # write-cycles byte, so this also proves the len>=4 Base ID parse fix end-to-end).
    def _stats_ok():
        raw = mqtt_client.msgs.get("enocean2mqtt/bridge/stats")
        if not raw:
            return False
        stats = json.loads(raw)
        return stats.get("base_id") == "FF:AE:7C:80" and stats.get("stick_app_version") == "2.5.3.0"

    assert wait_until(_stats_ok, timeout=30), "bridge/stats missing base_id / stick version"

    # (4) an inbound command round-trips to an ESP3 frame captured by the emulator. The raw_data and
    # send arrive on different topics (no cross-topic ordering guarantee), so set raw_data first and
    # let it be processed before triggering the send.
    mqtt_client.publish("enocean2mqtt/Sender/req/raw_data", "01:00:00:09")
    time.sleep(1.5)
    mqtt_client.publish("enocean2mqtt/Sender/req/send", "raw_data")
    assert wait_until(
        lambda: any("01000009" in line for line in read_capture(stack["capture"])), timeout=20
    ), "the raw_data command never reached the transceiver as an ESP3 frame"
